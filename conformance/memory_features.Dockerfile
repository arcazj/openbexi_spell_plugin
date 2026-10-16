ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
COPY conformance/memory_features_provenance.py conformance/memory_features.Dockerfile /opt/memory-features-patch/
RUN python /opt/memory-features-patch/memory_features_provenance.py --freeze-base
COPY source_port/memory_feature_patches.py /opt/memory-features-patch/
COPY driver_plugin/src/openbexi_spell_dss/memory_images.py /opt/memory-features-patch/modules/openbexi_spell_dss/
COPY driver_plugin/src/openbexi_dss_proxy/memory_support.py /opt/memory-features-patch/modules/openbexi_dss_proxy/
RUN python /opt/memory-features-patch/memory_feature_patches.py /usr/local/lib/python3.13/site-packages /opt/memory-features-patch
RUN cp /opt/memory-features-patch/modules/openbexi_spell_dss/memory_images.py /usr/local/lib/python3.13/site-packages/openbexi_spell_dss/ && cp /opt/memory-features-patch/modules/openbexi_dss_proxy/memory_support.py /usr/local/lib/python3.13/site-packages/openbexi_dss_proxy/
RUN python /opt/memory-features-patch/memory_features_provenance.py > /opt/memory-features-build-check.json
USER 10003:10003
