# Separate later increment over the exact qualified TIME/OBS native runtime.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
COPY source_port/limit_patches.py conformance/limit_runtime.Dockerfile /opt/limit-patch/
COPY driver_plugin/src/openbexi_dss_proxy/limit_support.py /usr/local/lib/python3.13/site-packages/openbexi_dss_proxy/limit_support.py
RUN python /opt/limit-patch/limit_patches.py /usr/local/lib/python3.13/site-packages /opt/limit-patch
USER 10003:10003
