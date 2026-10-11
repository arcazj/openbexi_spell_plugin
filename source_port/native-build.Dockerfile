FROM python:3.13.15-slim@sha256:7c61056e61ac89e852de05f3dc6fa51a6dd2181797bceed46aa725dd7cb2cd3b AS native
RUN apt-get update && apt-get install -y --no-install-recommends g++ libxerces-c-dev liblog4cplus-dev libncurses-dev zlib1g-dev
COPY source_port/native/continuation-requirements.txt /requirements.txt
RUN python -m pip install --no-cache-dir --require-hashes --only-binary=:all: -r /requirements.txt
COPY docs/reference/SPELL2.6.10-src.zip /input/SPELL2.6.10-src.zip
COPY source_port/native /input/native
COPY source_port/native_patches.py source_port/native_manifest.py source_port/native_build.py /input/
COPY source_port/native-build.Dockerfile source_port/native-build.Dockerfile.dockerignore /input/
RUN python /input/native_build.py

FROM scratch AS evidence
COPY --from=native /out /
