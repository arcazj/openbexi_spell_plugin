# Isolated Python display correction; the native runtime remains byte-identical.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
COPY conformance/installed_provenance.py conformance/display_provenance.py conformance/display.Dockerfile /opt/display-patch/
RUN python /opt/display-patch/display_provenance.py --freeze-base
COPY source_port/display_patches.py /opt/display-patch/
COPY driver_plugin/src/openbexi_spell_dss/displays.py driver_plugin/src/openbexi_spell_dss/display_viewer.py /opt/display-patch/modules/openbexi_spell_dss/
RUN python /opt/display-patch/display_patches.py /usr/local/lib/python3.13/site-packages /opt/display-patch
RUN cp /opt/display-patch/modules/openbexi_spell_dss/*.py /usr/local/lib/python3.13/site-packages/openbexi_spell_dss/
RUN python /opt/display-patch/display_provenance.py > /opt/display-build-check.json
USER 10003:10003
