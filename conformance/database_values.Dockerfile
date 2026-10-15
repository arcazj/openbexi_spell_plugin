ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
COPY conformance/installed_provenance.py conformance/database_values_provenance.py conformance/database_values.Dockerfile /opt/database-values-patch/
RUN python /opt/database-values-patch/database_values_provenance.py --freeze-base
COPY source_port/database_values_patches.py /opt/database-values-patch/
RUN python /opt/database-values-patch/database_values_patches.py /usr/local/lib/python3.13/site-packages /opt/database-values-patch
RUN python /opt/database-values-patch/database_values_provenance.py > /opt/database-values-build-check.json
USER 10003:10003
