ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
COPY conformance/command_provenance.py conformance/command.Dockerfile /opt/command-patch/
RUN python /opt/command-patch/command_provenance.py --freeze-base
COPY source_port/command_feature_patches.py /opt/command-patch/
COPY driver_plugin/src/openbexi_spell_dss/command_execution.py driver_plugin/src/openbexi_spell_dss/command_rpc.py driver_plugin/src/openbexi_spell_dss/command_budget.py /opt/command-patch/modules/openbexi_spell_dss/
COPY driver_plugin/src/openbexi_dss_proxy/command_settings.py /opt/command-patch/modules/openbexi_dss_proxy/
RUN python /opt/command-patch/command_feature_patches.py /usr/local/lib/python3.13/site-packages /opt/command-patch
RUN cp /opt/command-patch/modules/openbexi_spell_dss/*.py /usr/local/lib/python3.13/site-packages/openbexi_spell_dss/ && cp /opt/command-patch/modules/openbexi_dss_proxy/*.py /usr/local/lib/python3.13/site-packages/openbexi_dss_proxy/
RUN python /opt/command-patch/command_provenance.py > /opt/command-build-check.json
USER 10003:10003
