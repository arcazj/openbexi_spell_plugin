ARG BASE=openbexi-spell-dss:v06-integrated-3743ea8c7a3f
FROM ${BASE}
ARG APPLY_SCDB=1
USER root
COPY source_port/scdb_patches.py source_port/database_import_patches.py conformance/scdb_build.py conformance/installed_provenance.py /opt/scdb-input/
RUN APPLY_SCDB=${APPLY_SCDB} python -I /opt/scdb-input/scdb_build.py
USER 10003:10003
