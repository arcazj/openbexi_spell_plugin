ARG BASE=openbexi-spell-dss:v06-integrated-3743ea8c7a3f
FROM ${BASE}
USER root
COPY source_port/notification_patches.py conformance/notification_build.py conformance/installed_provenance.py /opt/notification-input/
RUN python -I /opt/notification-input/notification_build.py
USER 10003:10003
