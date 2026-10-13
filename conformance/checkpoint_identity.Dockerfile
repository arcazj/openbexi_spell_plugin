ARG NATIVE_BASE
ARG RUNTIME_BASE
FROM ${NATIVE_BASE} AS native
COPY source_port/checkpoint_error_patches.py source_port/checkpoint_identity_patches.py source_port/checkpoint_context_patches.py conformance/checkpoint_identity_build.py distribution/incremental_native.py /checkpoint-recipe/
RUN python /checkpoint-recipe/checkpoint_identity_build.py

FROM ${RUNTIME_BASE}
USER root
COPY --from=native /checkpoint-identity-patch /opt/checkpoint-identity-patch
COPY conformance/installed_provenance.py conformance/checkpoint_identity_install.py /checkpoint-install/
RUN python /checkpoint-install/checkpoint_identity_install.py
USER 10003:10003
