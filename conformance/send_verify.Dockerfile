ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
COPY source_port/send_verify_patches.py conformance/send_verify_provenance.py conformance/send_verify.Dockerfile conformance/installed_provenance.py /opt/send-verify-patch/
RUN python /opt/send-verify-patch/send_verify_patches.py /usr/local/lib/python3.13/site-packages /opt/send-verify-patch
RUN python /opt/send-verify-patch/send_verify_provenance.py > /opt/send-verify-build-check.json
USER 10003:10003
