ARG BASE=openbexi-spell-dss:v05-database-import-development
FROM ${BASE}
USER root
COPY source_port/user_database_patches.py /opt/user-database-patch/user_database_patches.py
RUN python /opt/user-database-patch/user_database_patches.py /usr/local/lib/python3.13/site-packages /opt/user-database-patch
USER 10003:10003
