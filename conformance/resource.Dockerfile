ARG RUNTIME_BASE=openbexi-spell-dss:v05-dta-time-obs-development
FROM ${RUNTIME_BASE}
USER root
RUN mkdir -p /opt/resource-conformance-patch/original/openbexi_dss_proxy && cp /usr/local/lib/python3.13/site-packages/openbexi_dss_proxy/resources.py /opt/resource-conformance-patch/original/openbexi_dss_proxy/resources.py
COPY driver_plugin/src/openbexi_dss_proxy/resources.py /usr/local/lib/python3.13/site-packages/openbexi_dss_proxy/resources.py
RUN python -c "from pathlib import Path; import hashlib,json; name='openbexi_dss_proxy/resources.py'; root=Path('/opt/resource-conformance-patch'); report={name:{'preimage':hashlib.sha256((root/'original'/name).read_bytes()).hexdigest(),'sha256':hashlib.sha256((Path('/usr/local/lib/python3.13/site-packages')/name).read_bytes()).hexdigest()}}; (root/'manifest.json').write_text(json.dumps(report,indent=2))"
COPY source_port/resource_patches.py /opt/resource-conformance-patch/resource_patches.py
RUN python /opt/resource-conformance-patch/resource_patches.py /usr/local/lib/python3.13/site-packages /opt/resource-conformance-patch
USER 10003:10003
