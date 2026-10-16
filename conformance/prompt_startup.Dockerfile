ARG NATIVE_BASE
ARG RUNTIME_BASE
FROM ${NATIVE_BASE} AS native
COPY source_port/prompt_startup_patches.py /recipe/source_port/
COPY conformance/prompt_startup_build.py conformance/prompt_startup_probe.py /recipe/conformance/
COPY distribution/incremental_native.py /recipe/distribution/
RUN python /recipe/conformance/prompt_startup_build.py

FROM ${RUNTIME_BASE}
USER root
COPY --from=native /prompt-startup-patch /opt/prompt-startup-patch
COPY conformance/installed_provenance.py conformance/prompt_startup_install.py /snapshot-install/
RUN python /snapshot-install/prompt_startup_install.py
USER 10003:10003
