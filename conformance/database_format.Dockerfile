ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
COPY conformance/database_format_provenance.py conformance/database_format.Dockerfile /opt/database-format-patch/
RUN python /opt/database-format-patch/database_format_provenance.py --freeze-base
COPY source_port/database_format_patches.py /opt/database-format-patch/
RUN python /opt/database-format-patch/database_format_patches.py /usr/local/lib/python3.13/site-packages /opt/database-format-patch
RUN python /opt/database-format-patch/database_format_provenance.py > /opt/database-format-build-check.json
USER 10003:10003
