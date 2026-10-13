# The accepted local host image stays unchanged. This is a separate driver image.
FROM openbexi-spell-host:0.3.0
USER root
COPY .qualification/v0.4/release-wheels/openbexi_spell_dss-0.4.0-*.whl /opt/driver-wheels/
RUN python -m pip install --no-index --no-deps /opt/driver-wheels/*.whl
COPY host_runtime/python /opt/host
USER 10003:10003
