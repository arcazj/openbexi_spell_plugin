# Isolated command development overlay; accepted checkpoint remains unchanged.
FROM openbexi-spell-dss:v05-dta-time-obs-development
USER root
COPY source_port/cmd_patches.py /opt/cmd-conformance-patch/cmd_patches.py
RUN python /opt/cmd-conformance-patch/cmd_patches.py /usr/local/lib/python3.13/site-packages /opt/cmd-conformance-patch
RUN mkdir /opt/cmd-conformance-patch/proxy && cp /usr/local/lib/python3.13/site-packages/openbexi_dss_proxy/tc.py /opt/cmd-conformance-patch/proxy/original_tc.py
COPY driver_plugin/src/openbexi_dss_proxy/tc.py /usr/local/lib/python3.13/site-packages/openbexi_dss_proxy/tc.py
COPY driver_plugin/src/openbexi_dss_proxy/tc.py /opt/cmd-conformance-patch/proxy/tc.py
COPY conformance/cmd.Dockerfile /opt/cmd-conformance-patch/cmd.Dockerfile
USER 10003:10003
