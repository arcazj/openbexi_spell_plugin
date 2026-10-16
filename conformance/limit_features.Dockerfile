ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
COPY conformance/limit_features_provenance.py conformance/installed_provenance.py conformance/limit_features.Dockerfile /opt/limit-features-patch/
RUN python /opt/limit-features-patch/limit_features_provenance.py --freeze-base
COPY source_port/limit_feature_patches.py /opt/limit-features-patch/
COPY driver_plugin/src/openbexi_spell_dss/limit_definitions.py driver_plugin/src/openbexi_spell_dss/limit_algorithm.py driver_plugin/src/openbexi_spell_dss/limits.py /opt/limit-features-patch/modules/openbexi_spell_dss/
COPY driver_plugin/src/openbexi_spell_dss/limit_files/normal.json /opt/limit-features-patch/modules/openbexi_spell_dss/limit_files/
COPY driver_plugin/src/openbexi_dss_proxy/limit_arguments.py driver_plugin/src/openbexi_dss_proxy/limit_profile.py /opt/limit-features-patch/modules/openbexi_dss_proxy/
RUN python /opt/limit-features-patch/limit_feature_patches.py /usr/local/lib/python3.13/site-packages /opt/limit-features-patch
RUN cp -r /opt/limit-features-patch/modules/openbexi_spell_dss/. /usr/local/lib/python3.13/site-packages/openbexi_spell_dss/ && cp /opt/limit-features-patch/modules/openbexi_dss_proxy/*.py /usr/local/lib/python3.13/site-packages/openbexi_dss_proxy/
RUN python /opt/limit-features-patch/limit_features_provenance.py > /opt/limit-features-build-check.json
USER 10003:10003
