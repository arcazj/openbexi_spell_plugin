# Development qualification overlay. The original accepted image is preserved.
FROM openbexi-spell-host:0.3.0
USER root
COPY .qualification/v0.5/time-port /opt/time-conformance-patch
COPY .qualification/v0.5/time-port/utctime.py /usr/local/lib/python3.13/site-packages/spell/lib/adapter/utctime.py
USER 10003:10003
