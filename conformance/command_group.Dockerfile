ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
COPY conformance/command_group_provenance.py conformance/command_group.Dockerfile /opt/command-group-patch/
RUN python /opt/command-group-patch/command_group_provenance.py --freeze-base
COPY source_port/command_group_patches.py /opt/command-group-patch/
COPY driver_plugin/src/openbexi_spell_dss/command_groups.py driver_plugin/src/openbexi_spell_dss/command_blocks.py driver_plugin/src/openbexi_spell_dss/command_results.py driver_plugin/src/openbexi_spell_dss/command_group_rpc.py /opt/command-group-patch/modules/openbexi_spell_dss/
COPY driver_plugin/src/openbexi_dss_proxy/command_group.py /opt/command-group-patch/modules/openbexi_dss_proxy/
RUN python /opt/command-group-patch/command_group_patches.py /usr/local/lib/python3.13/site-packages /opt/command-group-patch
RUN cp /opt/command-group-patch/modules/openbexi_spell_dss/*.py /usr/local/lib/python3.13/site-packages/openbexi_spell_dss/ && cp /opt/command-group-patch/modules/openbexi_dss_proxy/*.py /usr/local/lib/python3.13/site-packages/openbexi_dss_proxy/
RUN python /opt/command-group-patch/command_group_provenance.py > /opt/command-group-build-check.json
USER 10003:10003
