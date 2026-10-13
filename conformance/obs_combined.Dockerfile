# Frozen native DTA/TIME changes over the preserved driver-enabled DSS host.
ARG DTA_BASE=openbexi-spell-host:v05-dta-time-context-development
ARG DSS_BASE=openbexi-spell-dss:v05-ui-flow-data-final
FROM ${DTA_BASE} AS native
FROM ${DSS_BASE}
USER root
COPY --from=native /usr/local/lib/python3.13/site-packages/spell /usr/local/lib/python3.13/site-packages/spell
COPY --from=native /usr/local/lib/python3.13/site-packages/spell_native/bin /usr/local/lib/python3.13/site-packages/spell_native/bin
COPY --from=native /opt/dta-native-patch /opt/dta-native-patch
COPY source_port/obs_patches.py /opt/obs-conformance-patch/obs_patches.py
RUN python /opt/obs-conformance-patch/obs_patches.py /usr/local/lib/python3.13/site-packages /opt/obs-conformance-patch
COPY driver_plugin/src/openbexi_dss_proxy/tm.py /opt/obs-conformance-patch/proxy/tm.py
COPY driver_plugin/src/openbexi_dss_proxy/common.py /opt/obs-conformance-patch/proxy/common.py
COPY driver_plugin/src/openbexi_spell_dss/transport.py /opt/obs-conformance-patch/driver/transport.py
RUN cp /usr/local/lib/python3.13/site-packages/openbexi_dss_proxy/tm.py /opt/obs-conformance-patch/proxy/original_tm.py
RUN cp /usr/local/lib/python3.13/site-packages/openbexi_dss_proxy/common.py /opt/obs-conformance-patch/proxy/original_common.py
RUN cp /usr/local/lib/python3.13/site-packages/openbexi_spell_dss/transport.py /opt/obs-conformance-patch/driver/original_transport.py
COPY driver_plugin/src/openbexi_dss_proxy/tm.py /usr/local/lib/python3.13/site-packages/openbexi_dss_proxy/tm.py
COPY driver_plugin/src/openbexi_dss_proxy/common.py /usr/local/lib/python3.13/site-packages/openbexi_dss_proxy/common.py
COPY driver_plugin/src/openbexi_spell_dss/transport.py /usr/local/lib/python3.13/site-packages/openbexi_spell_dss/transport.py
COPY conformance/obs_combined.Dockerfile /opt/obs-conformance-patch/obs_combined.Dockerfile
USER 10003:10003
