ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
COPY source_port/event_text_patches.py conformance/event_text_build.py conformance/installed_provenance.py /opt/event-text-patch/
RUN python /opt/event-text-patch/event_text_build.py
USER 10003:10003
