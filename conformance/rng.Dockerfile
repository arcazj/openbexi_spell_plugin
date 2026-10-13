# Isolated diagnostic Python overlay; inherited original native bytes stay exact.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
COPY conformance/installed_provenance.py conformance/rng_provenance.py conformance/rng.Dockerfile /opt/rng-patch/
RUN python /opt/rng-patch/rng_provenance.py --freeze-base
COPY source_port/rng_patches.py /opt/rng-patch/
RUN python /opt/rng-patch/rng_patches.py /usr/local/lib/python3.13/site-packages /opt/rng-patch
RUN python /opt/rng-patch/rng_provenance.py > /opt/rng-build-check.json
USER 10003:10003
