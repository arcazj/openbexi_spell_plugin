ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
COPY conformance/manoeuvre_database_provenance.py conformance/installed_provenance.py conformance/manoeuvre_database.Dockerfile /opt/manoeuvre-database-patch/
RUN python /opt/manoeuvre-database-patch/manoeuvre_database_provenance.py --freeze-base
COPY source_port/manoeuvre_database_patches.py /opt/manoeuvre-database-patch/
RUN python /opt/manoeuvre-database-patch/manoeuvre_database_patches.py /usr/local/lib/python3.13/site-packages /opt/manoeuvre-database-patch
RUN python /opt/manoeuvre-database-patch/manoeuvre_database_provenance.py > /opt/manoeuvre-database-build-check.json
USER 10003:10003
