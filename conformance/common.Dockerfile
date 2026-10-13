# Original accepted host and source/notices are preserved in this development image.
FROM openbexi-spell-host:0.3.0
USER root
COPY .qualification/v0.5/common-port /opt/common-conformance-patch
COPY .qualification/v0.5/common-port/patched/spell /usr/local/lib/python3.13/site-packages/spell
USER 10003:10003
