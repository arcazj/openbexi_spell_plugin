ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
COPY conformance/telemetry_features_provenance.py conformance/telemetry_features.Dockerfile /opt/telemetry-features-patch/
RUN python /opt/telemetry-features-patch/telemetry_features_provenance.py --freeze-base
COPY source_port/telemetry_feature_patches.py /opt/telemetry-features-patch/
COPY driver_plugin/src/openbexi_spell_dss/telemetry_budget.py /opt/telemetry-features-patch/modules/openbexi_spell_dss/
RUN python /opt/telemetry-features-patch/telemetry_feature_patches.py /usr/local/lib/python3.13/site-packages /opt/telemetry-features-patch
RUN cp /opt/telemetry-features-patch/modules/openbexi_spell_dss/telemetry_budget.py /usr/local/lib/python3.13/site-packages/openbexi_spell_dss/
RUN python /opt/telemetry-features-patch/telemetry_features_provenance.py > /opt/telemetry-features-build-check.json
USER 10003:10003
