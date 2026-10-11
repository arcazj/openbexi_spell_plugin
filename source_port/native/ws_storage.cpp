// SPDX-License-Identifier: GPL-3.0-or-later
// Original SPELLwsStorage interface; versioned, bounded CPython 3.13 records.
namespace {
constexpr size_t maxRecordBytes = 16 * 1024 * 1024;
const std::string storageSignature = "OPENBEXI_SPELL_WS/1|CPython/" PY_VERSION "|marshal/4";

std::string readHeader(std::fstream& stream, size_t limit) {
    std::string line;
    char value;
    while (stream.get(value)) {
        if (value == '\n') return line;
        if (line.size() == limit)
            THROW_EXCEPTION("Invalid checkpoint", "Record header exceeds limit", SPELL_ERROR_WSTART);
        line += value;
    }
    THROW_EXCEPTION("Invalid checkpoint", "Missing or truncated header", SPELL_ERROR_WSTART);
}
template<typename Integer> Integer parseUnsigned(const std::string& value) {
    Integer result{};
    auto parsed = std::from_chars(value.data(), value.data() + value.size(), result);
    if (value.empty() || parsed.ec != std::errc{} || parsed.ptr != value.data() + value.size())
        THROW_EXCEPTION("Invalid checkpoint", "Invalid unsigned record field", SPELL_ERROR_WSTART);
    return result;
}
}

SPELLwsStorage::SPELLwsStorage(std::string filename, Mode mode)
    : m_filename(filename), m_opCounter(0), m_mode(mode)
{
    std::string runtime(Py_GetVersion());
    if (runtime.substr(0, runtime.find(' ')) != PY_VERSION)
        THROW_EXCEPTION("Incompatible runtime", "Checkpoint backend must match CPython build version", SPELL_ERROR_WSTART);
    reset();
}
SPELLwsStorage::~SPELLwsStorage() { m_trace.close(); m_file.close(); }
SPELLwsStorage::Mode SPELLwsStorage::getMode() { return m_mode; }
void SPELLwsStorage::reset(const Mode& mode) { m_mode = mode; reset(); }
void SPELLwsStorage::reset()
{
    if (m_mode != MODE_READ && m_mode != MODE_WRITE)
        THROW_EXCEPTION("Unable to setup persistent storage", "Mode is not set", SPELL_ERROR_WSTART);
    m_file.close(); m_file.clear();
    m_trace.close(); m_trace.clear();
    m_file.open(m_filename.c_str(), std::ios_base::binary |
        (m_mode == MODE_READ ? std::ios_base::in : std::ios_base::out | std::ios_base::trunc));
    if (!m_file.is_open())
        THROW_EXCEPTION("Unable to open checkpoint", m_filename, SPELL_ERROR_FILESYSTEM);
    m_opCounter = 0;
    if (m_mode == MODE_READ) {
        try {
            if (readHeader(m_file, 256) != storageSignature)
                THROW_EXCEPTION("Incompatible checkpoint", "Format or CPython version differs", SPELL_ERROR_WSTART);
        } catch (...) { m_file.close(); throw; }
    } else {
        m_file << storageSignature << '\n';
        m_file.flush();
        if (!m_file.good())
            THROW_EXCEPTION("Unable to write checkpoint", "Header write failed", SPELL_ERROR_FILESYSTEM);
    }
    m_traceFilename = m_filename + (m_mode == MODE_READ ? "_READ" : "_WRITE");
    m_trace.open(m_traceFilename.c_str(), std::ios_base::out | std::ios_base::trunc);
}

void SPELLwsStorage::storeObject(PyObject* object)
{
    SPELLpython313::GIL gil;
    if (!m_file.is_open() || !m_file.good() || m_mode != MODE_WRITE)
        THROW_EXCEPTION("Unable to store object", "Checkpoint is not writable", SPELL_ERROR_WSTART);
    if (!object)
        THROW_EXCEPTION("Unable to store object", "Null reference given", SPELL_ERROR_WSTART);
    SPELLpython313::Owned encoded(PyMarshal_WriteObjectToString(object, 4));
    if (!encoded.get()) SPELLpythonHelper::instance().checkError();
    Py_ssize_t size = PyBytes_GET_SIZE(encoded.get());
    if (size < 0 || static_cast<size_t>(size) > maxRecordBytes)
        THROW_EXCEPTION("Unable to store object", "Record exceeds 16 MiB", SPELL_ERROR_WSTART);
    const char* bytes = PyBytes_AS_STRING(encoded.get());
    const char* type = Py_TYPE(object)->tp_name;
    uint32_t checksum = crc32(0, reinterpret_cast<const Bytef*>(bytes), static_cast<uInt>(size));
    m_file << (m_opCounter + 1) << '\1' << type << '\1' << size << '\1' << checksum << '\n';
    m_file.write(bytes, size);
    m_file.put('\n');
    m_file.flush();
    if (!m_file.good())
        THROW_EXCEPTION("Unable to write checkpoint", "Record write failed", SPELL_ERROR_FILESYSTEM);
    ++m_opCounter;
    // Metadata only: diagnostics do not duplicate procedure values.
    m_trace << m_opCounter << " STORE " << type << " " << size << '\n';
    m_trace.flush();
}
void SPELLwsStorage::storeLong(long value)
{
    SPELLpython313::GIL gil;
    SPELLpython313::Owned number(PyLong_FromLong(value));
    if (!number.get()) SPELLpythonHelper::instance().checkError();
    storeObject(number.get());
}
void SPELLwsStorage::storeObjectOrNone(PyObject* object) { storeObject(object ? object : Py_None); }

PyObject* SPELLwsStorage::loadObject()
{
    SPELLpython313::GIL gil;
    try {
    if (!m_file.is_open() || !m_file.good() || m_mode != MODE_READ)
        THROW_EXCEPTION("Unable to load object", "Checkpoint is not readable", SPELL_ERROR_WSTART);
    const std::string header = readHeader(m_file, 1024);
    std::vector<std::string> fields;
    size_t start = 0, separator;
    while ((separator = header.find('\1', start)) != std::string::npos) {
        fields.push_back(header.substr(start, separator - start));
        start = separator + 1;
    }
    fields.push_back(header.substr(start));
    if (fields.size() != 4 || fields[1].empty())
        THROW_EXCEPTION("Invalid checkpoint", "Malformed record header", SPELL_ERROR_WSTART);
    unsigned long sequence = parseUnsigned<unsigned long>(fields[0]);
    size_t size = parseUnsigned<size_t>(fields[2]);
    uint32_t expected = parseUnsigned<uint32_t>(fields[3]);
    if (sequence != m_opCounter + 1 || size == 0 || size > maxRecordBytes)
        THROW_EXCEPTION("Invalid checkpoint", "Record sequence or size is invalid", SPELL_ERROR_WSTART);
    std::vector<char> bytes(size);
    m_file.read(bytes.data(), size);
    if (m_file.gcount() != static_cast<std::streamsize>(size) || m_file.get() != '\n')
        THROW_EXCEPTION("Invalid checkpoint", "Truncated record or missing delimiter", SPELL_ERROR_WSTART);
    uint32_t actual = crc32(0, reinterpret_cast<const Bytef*>(bytes.data()), static_cast<uInt>(size));
    if (actual != expected)
        THROW_EXCEPTION("Invalid checkpoint", "Record checksum differs", SPELL_ERROR_WSTART);
    SPELLpython313::Owned decoded(PyMarshal_ReadObjectFromString(bytes.data(), size));
    if (!decoded.get()) SPELLpythonHelper::instance().checkError();
    if (fields[1] != Py_TYPE(decoded.get())->tp_name)
        THROW_EXCEPTION("Invalid checkpoint", "Record type differs", SPELL_ERROR_WSTART);
    ++m_opCounter;
    m_trace << m_opCounter << " LOAD " << fields[1] << " " << size << '\n';
    m_trace.flush();
    return Py_NewRef(decoded.get());
    } catch (...) { m_file.close(); throw; }
}
long SPELLwsStorage::loadLong()
{
    SPELLpython313::GIL gil;
    SPELLpython313::Owned number(loadObject());
    long result = PyLong_AsLong(number.get());
    SPELLpythonHelper::instance().checkError();
    return result;
}
