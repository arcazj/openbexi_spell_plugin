ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
COPY conformance/command_catalog_provenance.py conformance/command_catalog.Dockerfile /opt/command-catalog-patch/
RUN python /opt/command-catalog-patch/command_catalog_provenance.py --freeze-base
COPY source_port/command_catalog_patches.py /opt/command-catalog-patch/
COPY driver_plugin/src/openbexi_spell_dss/command_catalog.py /opt/command-catalog-patch/modules/openbexi_spell_dss/
COPY driver_plugin/src/openbexi_dss_proxy/command_catalog.py /opt/command-catalog-patch/modules/openbexi_dss_proxy/
RUN python /opt/command-catalog-patch/command_catalog_patches.py /usr/local/lib/python3.13/site-packages /opt/command-catalog-patch
RUN cp /opt/command-catalog-patch/modules/openbexi_spell_dss/*.py /usr/local/lib/python3.13/site-packages/openbexi_spell_dss/ && cp /opt/command-catalog-patch/modules/openbexi_dss_proxy/*.py /usr/local/lib/python3.13/site-packages/openbexi_dss_proxy/
RUN python /opt/command-catalog-patch/command_catalog_provenance.py > /opt/command-catalog-build-check.json
USER 10003:10003
