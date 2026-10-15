ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
COPY conformance/installed_provenance.py conformance/rng_provenance.py conformance/rng_state_provenance.py conformance/rng_state.Dockerfile /opt/rng-state-patch/
RUN python /opt/rng-state-patch/rng_state_provenance.py --freeze-base
COPY source_port/rng_state_patches.py /opt/rng-state-patch/
RUN python /opt/rng-state-patch/rng_state_patches.py /usr/local/lib/python3.13/site-packages /opt/rng-state-patch
RUN python /opt/rng-state-patch/rng_state_provenance.py > /opt/rng-state-build-check.json
USER 10003:10003
