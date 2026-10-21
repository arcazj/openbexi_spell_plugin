# OpenBEXI SPELL v0.6

Native, DSS driver, host and shared packages are versioned 0.6.0, alongside the
0.6.0 JetBrains plugin ZIP. Independent offline builds match byte for byte;
clean installation, versioned upgrades and removal pass on the declared platforms.

All **763 original language requirements remain qualified, with none open**.
Validation passes 61 native suites (2,157 raw checks), 1,530 repository test cases,
49 installed DSS integration tests and repeated prompt/child recovery controls.
Installed OpenBEXI, IntelliJ and PyCharm workflows pass, including preference and
project preservation across upgrades and removal.

Atomic execution-count snapshots prevent background trace reads from racing trace
destruction or acquiring the GIL under the display lock. Oversized timeout
integers now receive the expected bounds error before numeric conversion.

Scope: Linux x86_64, Debian 13, GIL-enabled CPython 3.13.15 and the diagnostic
ASan/UBSan GENERIC simulator runtime; Windows OpenBEXI IDE 1.1.0, IntelliJ IDEA
2026.2.3 and PyCharm 2026.1.2. Leak sanitizer remains disabled. Operational security,
capacity and mission-specific qualification remain v0.7 work; stable v1.0 is not
accepted. The bounded simulator SDK retains its separate 0.1.0 version.

See the [installation and platform matrix](https://github.com/arcazj/openbexi_spell_plugin/blob/v0.6/docs/V06_INSTALLATION.md)
and [exact acceptance manifest](V06_QUALIFICATION.json). Release assets include
runtime images, locked build images, offline inputs and portable qualification
evidence. Failed diagnostics remain retained; the portable manifest identifies
unavailable source snapshots from older diagnostics separately from current
acceptance evidence.
