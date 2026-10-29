"""Generate/check the native header carrying the tracked comparison helper."""

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def generated(source):
    if b')v08_legacy"' in source or b"\x00" in source:
        raise ValueError("Legacy helper cannot use the native raw-string delimiter")
    return (
        b"// SPDX-License-Identifier: GPL-3.0-or-later\n"
        b"// Generated from source_port/legacy_compare_syntax.py; checked byte-for-byte.\n"
        b"#ifndef OPENBEXI_V08_LEGACY_SYNTAX_H\n"
        b"#define OPENBEXI_V08_LEGACY_SYNTAX_H\n"
        b'static constexpr char v08LegacySyntax[] = R"v08_legacy('
        + source
        + b')v08_legacy";\n#endif\n'
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = generated((ROOT / "source_port/legacy_compare_syntax.py").read_bytes())
    header = ROOT / "host_runtime/native/legacy_syntax.H"
    if args.check:
        if header.read_bytes() != expected:
            raise ValueError("Native legacy helper header is stale")
    else:
        header.write_bytes(expected)


if __name__ == "__main__":
    main()
