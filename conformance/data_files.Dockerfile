FROM openbexi-spell-host:v05-common
USER root
COPY .qualification/v0.5/data-files-port /opt/data-files-conformance-patch
COPY .qualification/v0.5/data-files-port/patched/spell /usr/local/lib/python3.13/site-packages/spell
USER 10003:10003
