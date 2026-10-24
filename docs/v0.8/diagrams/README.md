# Editable architecture figures

* `legacy_reference.dot`: 2.4.4 manual-backed roles, explicit protocol uncertainty.
* `v07_as_is.dot`: source-verified v0.7 service paths and native process chain.
* `v08_target.dot`: proposed v0.8 boundaries, ownership and deployment choices.
* `v08_docker_compose.png`: original supplied diagram, preserved unchanged.

Render from the repository root with Graphviz 2.42.4 and CPython 3.13:

```powershell
python scripts/render_v08_diagrams.py
```

The script exports high-resolution PNG and scalable SVG, renders each twice,
requires identical bytes within that renderer environment, and records version
and SHA-256 in `manifest.json` / `SHA256SUMS`. Font/package differences on another
host may change output bytes; keep sources and record the actual environment.
The captured render used Debian Graphviz 2.42.4-3 with DejaVu fonts 2.37-8 in a
disposable container, with no host Graphviz installation or production change.
PNG dimensions are recorded in `../evidence/review-integrity.json`.

All three exports were visually inspected. The v0.8 figure is a proposal,
not an as-built release claim. Update DOT sources and regenerate exports when
the approved or implemented architecture changes; do not edit PNG pixels.
