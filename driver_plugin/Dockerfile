# Both runtime images are new candidates; no accepted historical tag is changed.
ARG HOST_IMAGE
FROM ${HOST_IMAGE}
USER root
ARG DRIVER_WHEEL=.runtime-input/driver/*.whl
COPY ${DRIVER_WHEEL} /opt/driver-wheels/
RUN python -m pip install --no-index --no-deps /opt/driver-wheels/*.whl
COPY host_runtime/python /opt/host
USER 10003:10003
