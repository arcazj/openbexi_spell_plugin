ARG NATIVE_BASE
ARG RUNTIME_BASE
FROM ${NATIVE_BASE} AS native
ARG CHECKPOINT_PATCH_MODE=audit
ENV CHECKPOINT_PATCH_MODE=${CHECKPOINT_PATCH_MODE}
COPY source_port/checkpoint_error_patches.py conformance/checkpoint_error_build.py distribution/incremental_native.py /checkpoint-recipe/
RUN python /checkpoint-recipe/checkpoint_error_build.py

FROM ${RUNTIME_BASE}
USER root
COPY --from=native /checkpoint-error-patch /opt/checkpoint-error-patch
COPY conformance/installed_provenance.py conformance/checkpoint_error_install.py /checkpoint-install/
RUN python /checkpoint-install/checkpoint_error_install.py
USER 10003:10003
