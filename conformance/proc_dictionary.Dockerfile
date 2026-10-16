ARG NATIVE_BASE
ARG RUNTIME_BASE
FROM ${NATIVE_BASE} AS native
COPY source_port/proc_dictionary_patches.py /recipe/source_port/
COPY conformance/proc_dictionary_build.py /recipe/conformance/
COPY distribution/incremental_native.py /recipe/distribution/
RUN python /recipe/conformance/proc_dictionary_build.py

FROM ${RUNTIME_BASE}
USER root
COPY --from=native /proc-dictionary-patch /opt/proc-dictionary-patch
COPY conformance/installed_provenance.py conformance/proc_dictionary_install.py /snapshot-install/
RUN python /snapshot-install/proc_dictionary_install.py
USER 10003:10003
