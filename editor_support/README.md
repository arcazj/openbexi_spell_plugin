# Native SPELL editor definitions

`scripts/export_spell_editor.py` is a standalone standard-library CLI which the
IntelliJ plugin can bundle. It reads the installed Python sources from the exact
configured Docker image, pins its immutable image ID, and generates `.pyi` files
for editor indexing. It does not install a Python package or import SPELL.

```powershell
python scripts/export_spell_editor.py --image openbexi-spell-host:0.3.0 --output C:/my-project/.openbexi/editor/current
python -m unittest discover -s editor_support -p 'test_*.py'
```

The last stdout line is JSON containing `root`, `image_id`, `modules`, and
`manifest`. `manifest.json` records the original source SHA-256 values, generated
stub SHA-256 values, generator identity, and dynamic bindings. The native runtime
definitions expose only source-backed `Step`, `Goto`, `ARGS`, `IVARS`, and `PROC`,
plus the `DataContainer` and `Var` types. Unexpected native provenance fails
without replacing existing definitions. Unknown names remain unresolved.

Register `root` as an editor library. Avoid adding it to runtime `PYTHONPATH`:
although `.pyi` files are not executable, their directories can be treated as
namespace packages when no real SPELL package is installed. SPELL procedures
continue to execute with the configured host and native image.

The native `spell.lang` package initializer is empty. These definitions do not
pretend it re-exports the separate browser SDK. Procedures targeting both
backends should import that SDK using its own `openbexi_spell` namespace.
