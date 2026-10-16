ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
COPY conformance/send_complete_provenance.py conformance/send_complete.Dockerfile /opt/send-complete-patch/
RUN python /opt/send-complete-patch/send_complete_provenance.py --freeze-base
COPY source_port/send_complete_patches.py /opt/send-complete-patch/
RUN python /opt/send-complete-patch/send_complete_patches.py /usr/local/lib/python3.13/site-packages /opt/send-complete-patch
RUN python /opt/send-complete-patch/send_complete_provenance.py > /opt/send-complete-build-check.json
USER 10003:10003
