# A diagnostic overlay on the exact independently reproduced422 checkpoint.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
COPY conformance/installed_provenance.py conformance/timing_provenance.py conformance/timing.Dockerfile /opt/timing-patch/
RUN python /opt/timing-patch/timing_provenance.py --freeze-base
COPY source_port/limit_patches.py driver_plugin/src/openbexi_dss_proxy/limit_support.py /opt/limit-patch/
COPY driver_plugin/src/openbexi_dss_proxy/limit_support.py /usr/local/lib/python3.13/site-packages/openbexi_dss_proxy/limit_support.py
RUN python /opt/limit-patch/limit_patches.py /usr/local/lib/python3.13/site-packages /opt/limit-patch
COPY source_port/timing_patches.py /opt/timing-patch/
RUN python /opt/timing-patch/timing_patches.py /usr/local/lib/python3.13/site-packages /opt/timing-patch
RUN python /opt/timing-patch/timing_provenance.py > /opt/timing-build-check.json
USER 10003:10003
