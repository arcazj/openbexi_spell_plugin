"""Original WS storage integrity/ownership checks. SPDX-License-Identifier: GPL-3.0-or-later."""
import gc
import importlib.util
import json
import marshal
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import weakref
import zlib

spec = importlib.util.spec_from_file_location('_spell_storage_qualification', next(Path('/out').glob('_spell_storage_qualification*.so')))
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
signature = f'OPENBEXI_SPELL_WS/1|CPython/{sys.version.split()[0]}|marshal/4\n'.encode()


class Storage(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name)/'checkpoint_通信.bin'

    def writer(self):
        return native.create(str(self.path), 1)

    def reader(self):
        return native.create(str(self.path), 0)

    def roundtrip(self, values):
        writer = self.writer()
        for value in values: native.store(writer, value)
        del writer
        reader = self.reader()
        return [native.load(reader) for _ in values]

    def malformed(self, body):
        self.path.write_bytes(signature + body)
        reader = self.reader()
        with self.assertRaises(RuntimeError): native.load(reader)

    def test_builtin_values_unicode_and_binary(self):
        values = [None, True, 42, -(2**200), 1.25, complex(2,3), '通信\0value', b'\0\n\xff', [1,2], {'value':(3,4)}, {5,6}]
        self.assertEqual(self.roundtrip(values), values)
        self.assertTrue(self.path.read_bytes().startswith(signature))

    def test_large_record_exceeds_old_fixed_buffer(self):
        value = bytes(range(256))*4096
        self.assertEqual(self.roundtrip([value]), [value])

    def test_code_object_restores_and_executes(self):
        code = compile('result = sum(range(10))\n', 'persisted.py', 'exec')
        restored, = self.roundtrip([code])
        namespace = {}
        exec(restored, namespace)
        self.assertEqual(namespace['result'], 45)
        self.assertEqual(restored.co_filename, 'persisted.py')

    def test_fresh_interpreter_loads_native_checkpoint(self):
        writer = self.writer()
        native.store(writer, {'value': 41})
        native.store(writer, compile("result = value + 1\n", 'fresh.py', 'exec'))
        del writer
        script = '''import importlib.util, json, sys
spec = importlib.util.spec_from_file_location('_spell_storage_qualification', sys.argv[2])
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
reader = native.create(sys.argv[1], 0)
namespace = native.load(reader)
code = native.load(reader)
exec(code, namespace)
print(json.dumps({'result': namespace['result'], 'filename': code.co_filename}))
'''
        child = subprocess.run([sys.executable, '-I', '-c', script, str(self.path), spec.origin],
                               capture_output=True, text=True, timeout=30, check=True)
        self.assertEqual(json.loads(child.stdout), {'result':42, 'filename':'fresh.py'})

    def test_recursive_values_and_aliases_within_record(self):
        shared = [1,2]
        graph = [shared, shared]
        graph.append(graph)
        restored, = self.roundtrip([graph])
        self.assertIs(restored[0], restored[1])
        self.assertIs(restored[2], restored)

    def test_long_none_and_error_conversion(self):
        writer = self.writer()
        native.store_long(writer, -987654321)
        native.store_none(writer)
        native.store(writer, 'not a long')
        native.reset(writer, 0)
        self.assertEqual(native.load_long(writer), -987654321)
        self.assertIsNone(native.load(writer))
        with self.assertRaises(RuntimeError): native.load_long(writer)

    def test_read_write_modes_and_reset_after_eof(self):
        handle = self.writer()
        native.store(handle, 123)
        with self.assertRaises(RuntimeError): native.load(handle)
        native.reset(handle, 0)
        with self.assertRaises(RuntimeError): native.store(handle, 456)
        self.assertEqual(native.load(handle), 123)
        with self.assertRaises(RuntimeError): native.load(handle)
        native.reset(handle, 0)
        self.assertEqual(native.load(handle), 123)
        native.reset(handle, 1)
        native.store(handle, 789)
        native.reset(handle, 0)
        self.assertEqual(native.load(handle), 789)

    def test_missing_file_and_unwritable_path(self):
        with self.assertRaises(RuntimeError): self.reader()
        with self.assertRaises(RuntimeError): native.create(str(self.path/'missing'/'file'), 1)

    def test_header_rejects_legacy_and_different_interpreter(self):
        for content in [b'', b'1\x01str\x013\nabc\n', signature.replace(b'/1|', b'/2|'), signature.replace(b'CPython/', b'OtherVM/')]:
            self.path.write_bytes(content)
            with self.assertRaises(RuntimeError): self.reader()

    def test_failed_reset_cannot_bypass_version_check(self):
        handle = self.writer()
        native.store(handle, 123)
        data = self.path.read_bytes()
        self.path.write_bytes(data.replace(b'/1|', b'/9|', 1))
        with self.assertRaisesRegex(RuntimeError, 'Incompatible'): native.reset(handle, 0)
        with self.assertRaisesRegex(RuntimeError, 'not readable'): native.load(handle)

    def test_malformed_fields_and_bounded_lengths(self):
        for header in [b'1', b'1\x01bytes', b'1\x01bytes\x01-1\x010', b'1\x01bytes\x019999999999999999999999999\x010',
                       b'1\x01bytes\x0116777217\x010', b'1\x01bytes\x010\x010', b'2\x01bytes\x011\x010',
                       b'1\x01bytes\x01x\x010', b'1\x01bytes\x011\x014294967296', b'1\x01bytes\x011\x010\x01extra', b'x'*1025]:
            self.malformed(header+b'\n')

    def test_every_truncated_prefix_is_rejected(self):
        self.roundtrip([b'payload'*20])
        data = self.path.read_bytes()
        for length in range(len(data)):
            self.path.write_bytes(data[:length])
            with self.assertRaises(RuntimeError):
                reader = self.reader()
                native.load(reader)
                del reader

    def test_corrupt_payload_and_type_are_rejected(self):
        self.roundtrip(['payload'])
        data = self.path.read_bytes()
        self.path.write_bytes(data[:-3]+bytes([data[-3]^1])+data[-2:])
        with self.assertRaisesRegex(RuntimeError, 'checksum'): native.load(self.reader())
        self.path.write_bytes(data.replace(b'\1str\1', b'\1int\1'))
        with self.assertRaisesRegex(RuntimeError, 'type'): native.load(self.reader())

    def test_invalid_marshal_is_an_error(self):
        payload = b'!invalid-marshal'
        header = f'1\x01str\x01{len(payload)}\x01{zlib.crc32(payload)}\n'.encode()
        self.malformed(header+payload+b'\n')

    def test_oversized_or_unsupported_write_does_not_add_record(self):
        writer = self.writer()
        with self.assertRaises(RuntimeError): native.store(writer, object())
        with self.assertRaises(RuntimeError): native.store(writer, b'x'*(16*1024*1024))
        native.store(writer, 321)
        native.reset(writer, 0)
        self.assertEqual(native.load(writer), 321)

    def test_loaded_code_has_no_extra_owned_reference(self):
        code = compile('value = 123\n', 'reference.py', 'exec')
        writer = self.writer()
        for _ in range(1000): native.store(writer, code)
        native.reset(writer, 0)
        refs = []
        for _ in range(1000):
            restored = native.load(writer)
            refs.append(weakref.ref(restored))
            del restored
        gc.collect()
        self.assertTrue(all(ref() is None for ref in refs))

    def test_trace_contains_metadata_without_values(self):
        self.roundtrip(['secret-test-value'])
        for suffix in ['_READ','_WRITE']:
            trace = Path(str(self.path)+suffix).read_text()
            self.assertIn('str', trace)
            self.assertNotIn('secret-test-value', trace)


result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Storage))
Path('/out/storage-runtime.json').write_text(json.dumps({'tests':result.testsRun,'failures':len(result.failures),
    'errors':len(result.errors),'skips':len(result.skipped),'address_sanitizer':True,'undefined_behavior_sanitizer':True,
    'leak_sanitizer':False,'full_spell_warm_start_qualified':False},indent=2)+'\n')
raise SystemExit(0 if result.wasSuccessful() else 1)
