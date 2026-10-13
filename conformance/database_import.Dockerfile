FROM openbexi-spell-dss:v05-resource-development
USER root
COPY source_port/database_import_patches.py /opt/database-import-patch/database_import_patches.py
RUN python /opt/database-import-patch/database_import_patches.py /usr/local/lib/python3.13/site-packages /opt/database-import-patch
USER 10003:10003
