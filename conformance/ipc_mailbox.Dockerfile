ARG NATIVE_BASE
ARG RUNTIME_BASE
FROM ${NATIVE_BASE} AS native
COPY source_port/ipc_mailbox_patches.py conformance/ipc_mailbox_build.py conformance/ipc_mailbox_race.cpp distribution/incremental_native.py /ipc-recipe/
RUN python /ipc-recipe/ipc_mailbox_build.py

FROM ${RUNTIME_BASE}
USER root
COPY --from=native /ipc-mailbox-patch /opt/ipc-mailbox-patch
COPY conformance/installed_provenance.py conformance/ipc_mailbox_install.py /ipc-install/
RUN python /ipc-install/ipc_mailbox_install.py
USER 10003:10003
