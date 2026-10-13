# Development OBS overlay; accepted parent and original source remain preserved.
ARG OBS_BASE=openbexi-spell-dss:v05-ui-flow-data-final
FROM ${OBS_BASE}
USER root
COPY source_port/obs_patches.py /opt/obs-conformance-patch/obs_patches.py
RUN python /opt/obs-conformance-patch/obs_patches.py /usr/local/lib/python3.13/site-packages /opt/obs-conformance-patch
COPY driver_plugin/src/openbexi_dss_proxy/tm.py /opt/obs-conformance-patch/proxy/tm.py
RUN cp /usr/local/lib/python3.13/site-packages/openbexi_dss_proxy/tm.py /opt/obs-conformance-patch/proxy/original_tm.py
COPY driver_plugin/src/openbexi_dss_proxy/tm.py /usr/local/lib/python3.13/site-packages/openbexi_dss_proxy/tm.py
COPY driver_plugin/src/openbexi_spell_dss/transport.py /opt/obs-conformance-patch/driver/transport.py
RUN cp /usr/local/lib/python3.13/site-packages/openbexi_spell_dss/transport.py /opt/obs-conformance-patch/driver/original_transport.py
COPY driver_plugin/src/openbexi_spell_dss/transport.py /usr/local/lib/python3.13/site-packages/openbexi_spell_dss/transport.py
COPY driver_plugin/src/openbexi_dss_proxy/common.py /opt/obs-conformance-patch/proxy/common.py
RUN cp /usr/local/lib/python3.13/site-packages/openbexi_dss_proxy/common.py /opt/obs-conformance-patch/proxy/original_common.py
COPY driver_plugin/src/openbexi_dss_proxy/common.py /usr/local/lib/python3.13/site-packages/openbexi_dss_proxy/common.py
USER 10003:10003
