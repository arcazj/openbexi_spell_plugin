# Native shared service provider 0.6.0

This optional GPL plugin connects the neutral IDE's durable shared service to
the original native SPELL runtime through DAP. It requires
`openbexi-spell-host==0.6.0` and a local Linux Docker engine. The optional `dss`
extra installs `openbexi-spell-dss[service]==0.6.0` for original-driver integration.

Development, read-only Monitoring and approved immutable Execution retain their
mode and authority boundaries. Persisted older provider bindings remain supported;
package upgrade and removal preserve project files and settings.

See [the v0.6 installation matrix](../docs/V06_INSTALLATION.md) and
[acceptance manifest](../docs/V06_QUALIFICATION.json) for tested artifacts and
platforms. [Driver runtime documentation](../docs/DRIVER_RUNTIME.md) describes
the GENERIC simulator. Operational qualification remains separate v0.7 work.
