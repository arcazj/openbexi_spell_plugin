ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
COPY build-input /build-input
COPY evidence /opt/procedure-library-patch
RUN python /opt/procedure-library-patch/procedure_library_build.py
RUN python /opt/procedure-library-patch/procedure_library_provenance.py > /opt/procedure-library-build-check.json
USER 10003:10003
