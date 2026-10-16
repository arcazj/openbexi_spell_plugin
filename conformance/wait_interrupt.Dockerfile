ARG NATIVE_BASE
ARG RUNTIME_BASE
FROM ${NATIVE_BASE} AS native
COPY source_port/wait_interrupt_patches.py /recipe/source_port/
COPY conformance/wait_interrupt_build.py conformance/wait_interrupt_probe.py /recipe/conformance/
COPY distribution/incremental_native.py /recipe/distribution/
RUN python /recipe/conformance/wait_interrupt_build.py

FROM ${RUNTIME_BASE}
USER root
COPY --from=native /wait-interrupt-patch /opt/wait-interrupt-patch
COPY conformance/installed_provenance.py conformance/wait_interrupt_install.py /snapshot-install/
RUN python /snapshot-install/wait_interrupt_install.py
USER 10003:10003
