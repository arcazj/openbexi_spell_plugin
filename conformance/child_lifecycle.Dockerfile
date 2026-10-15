ARG NATIVE_BASE
ARG RUNTIME_BASE
FROM ${NATIVE_BASE} AS native
COPY source_port/child_lifecycle_patches.py conformance/child_lifecycle_build.py distribution/incremental_native.py /child-recipe/
RUN python /child-recipe/child_lifecycle_build.py

FROM ${RUNTIME_BASE}
USER root
COPY --from=native /child-lifecycle-patch /opt/child-lifecycle-patch
COPY conformance/installed_provenance.py conformance/child_lifecycle_install.py /child-install/
RUN python /child-install/child_lifecycle_install.py
USER 10003:10003
