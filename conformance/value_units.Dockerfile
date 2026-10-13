# A diagnostic overlay on the exact independently reproduced422 checkpoint.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
COPY conformance/installed_provenance.py conformance/value_units_provenance.py conformance/value_units.Dockerfile /opt/value-units-patch/
RUN python /opt/value-units-patch/value_units_provenance.py --freeze-base
COPY source_port/limit_patches.py driver_plugin/src/openbexi_dss_proxy/limit_support.py /opt/limit-patch/
COPY driver_plugin/src/openbexi_dss_proxy/limit_support.py /usr/local/lib/python3.13/site-packages/openbexi_dss_proxy/limit_support.py
RUN python /opt/limit-patch/limit_patches.py /usr/local/lib/python3.13/site-packages /opt/limit-patch
COPY source_port/value_units_patches.py /opt/value-units-patch/
RUN python /opt/value-units-patch/value_units_patches.py /usr/local/lib/python3.13/site-packages /opt/value-units-patch
RUN python /opt/value-units-patch/value_units_provenance.py > /opt/value-units-build-check.json
USER 10003:10003
