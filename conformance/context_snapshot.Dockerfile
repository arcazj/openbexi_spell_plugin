ARG NATIVE_BASE
ARG RUNTIME_BASE
FROM ${NATIVE_BASE} AS native
COPY source_port/context_snapshot_patches.py /recipe/source_port/
COPY conformance/context_snapshot_build.py conformance/context_snapshot_probe.py /recipe/conformance/
COPY distribution/incremental_native.py /recipe/distribution/
RUN python /recipe/conformance/context_snapshot_build.py

FROM ${RUNTIME_BASE}
USER root
COPY --from=native /context-snapshot-patch /opt/context-snapshot-patch
COPY conformance/installed_provenance.py conformance/context_snapshot_install.py /snapshot-install/
RUN python /snapshot-install/context_snapshot_install.py
USER 10003:10003
