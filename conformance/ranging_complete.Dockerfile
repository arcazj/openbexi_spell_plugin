ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
COPY conformance/ranging_complete_provenance.py conformance/installed_provenance.py conformance/ranging_complete.Dockerfile /opt/ranging-complete-patch/
RUN python /opt/ranging-complete-patch/ranging_complete_provenance.py --freeze-base
COPY source_port/ranging_complete_patches.py /opt/ranging-complete-patch/
COPY driver_plugin/src/openbexi_spell_dss/ranging_complete.py /opt/ranging-complete-patch/modules/openbexi_spell_dss/
COPY driver_plugin/src/openbexi_dss_proxy/ranging_complete.py /opt/ranging-complete-patch/modules/openbexi_dss_proxy/
RUN python /opt/ranging-complete-patch/ranging_complete_patches.py /usr/local/lib/python3.13/site-packages /opt/ranging-complete-patch
RUN cp /opt/ranging-complete-patch/modules/openbexi_spell_dss/ranging_complete.py /usr/local/lib/python3.13/site-packages/openbexi_spell_dss/ && cp /opt/ranging-complete-patch/modules/openbexi_dss_proxy/ranging_complete.py /usr/local/lib/python3.13/site-packages/openbexi_dss_proxy/
RUN python /opt/ranging-complete-patch/ranging_complete_provenance.py > /opt/ranging-complete-build-check.json
USER 10003:10003
