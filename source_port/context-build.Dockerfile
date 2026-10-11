FROM python:3.13.15-slim@sha256:7c61056e61ac89e852de05f3dc6fa51a6dd2181797bceed46aa725dd7cb2cd3b AS native
RUN apt-get update && apt-get install -y --no-install-recommends g++ libxerces-c-dev liblog4cplus-dev libncurses-dev zlib1g-dev
COPY source_port/native/continuation-requirements.txt /requirements.txt
RUN python -m pip install --no-cache-dir --require-hashes --only-binary=:all: -r /requirements.txt
COPY docs/reference/SPELL2.6.10-src.zip /input/SPELL2.6.10-src.zip
COPY source_port/native /input/native
COPY source_port/native_patches.py source_port/native_manifest.py source_port/native_build.py /input/
COPY source_port/native-build.Dockerfile source_port/native-build.Dockerfile.dockerignore /input/
RUN python /input/native_build.py
COPY source_port/experiments /experiment
RUN python -m pip install --no-cache-dir --require-hashes --only-binary=:all: -r /experiment/persistent-requirements.txt
RUN python /experiment/build_probe.py
COPY source_port/executor-build.lock /executor/executor-build.lock
RUN python -m pip install --no-cache-dir --require-hashes --only-binary=:all: -r /executor/executor-build.lock
COPY source_port/executor_build.py source_port/qualify_executor.py source_port/patches.py /executor/
COPY source_port/executor-build.Dockerfile source_port/executor-build.Dockerfile.dockerignore /executor/
RUN python /executor/executor_build.py

COPY source_port/context_build.py source_port/context_peer.cpp source_port/qualify_context.py source_port/qualify_process.cpp source_port/server_peer.cpp source_port/qualify_service_bindings.cpp source_port/qualify_service_bindings.py /context/
COPY source_port/context-build.Dockerfile source_port/context-build.Dockerfile.dockerignore /context/
RUN python /context/context_build.py

FROM scratch AS evidence
COPY --from=native /out /
