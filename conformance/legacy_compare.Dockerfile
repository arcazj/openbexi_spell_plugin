ARG NATIVE_BASE
ARG RUNTIME_BASE
FROM ${NATIVE_BASE} AS native
COPY source_port/legacy_compare_patches.py source_port/legacy_compare_syntax.py conformance/legacy_compare_build.py distribution/incremental_native.py /legacy-recipe/
RUN python /legacy-recipe/legacy_compare_build.py

FROM ${RUNTIME_BASE}
USER root
COPY --from=native /legacy-compare-patch /opt/legacy-compare-patch
COPY conformance/installed_provenance.py conformance/legacy_compare_provenance.py conformance/legacy_compare_install.py /legacy-install/
RUN python /legacy-install/legacy_compare_install.py
USER 10003:10003
