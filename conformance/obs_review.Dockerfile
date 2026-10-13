# Development correction over the exact separately relinked native candidate.
ARG NATIVE_IMAGE
FROM ${NATIVE_IMAGE}
USER root
RUN cp -a /opt/obs-conformance-patch /opt/obs-review-baseline
COPY source_port/obs_patches.py /opt/obs-conformance-patch/obs_patches.py
COPY conformance/obs_review.Dockerfile /opt/obs-conformance-patch/obs_review.Dockerfile
RUN python -c "from pathlib import Path; import sys; sys.path.insert(0,'/opt/obs-conformance-patch'); import obs_patches; site=Path('/usr/local/lib/python3.13/site-packages'); [(site/name).write_bytes((Path('/opt/obs-review-baseline/original')/name).read_bytes()) for name in obs_patches.PREIMAGES]; obs_patches.apply_tree(site, '/opt/obs-conformance-patch')"
USER 10003:10003
