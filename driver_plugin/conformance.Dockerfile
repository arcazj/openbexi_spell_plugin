# Development qualification only; preserve the accepted v0.4 image and wheels.
FROM openbexi-spell-dss:0.4.0
USER root
COPY .qualification/v0.5/time-port /opt/time-conformance-patch
COPY .qualification/v0.5/time-port/utctime.py /usr/local/lib/python3.13/site-packages/spell/lib/adapter/utctime.py
COPY driver_plugin/src/openbexi_dss_proxy /usr/local/lib/python3.13/site-packages/openbexi_dss_proxy
USER 10003:10003
