ARG BASE_IMAGE
FROM ${BASE_IMAGE}
COPY host_runtime/python/adapter.py host_runtime/python/children.py /opt/host/
