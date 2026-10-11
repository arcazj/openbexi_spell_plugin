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

COPY source_port/context_build.py source_port/context_peer.cpp source_port/qualify_context.py source_port/qualify_process.cpp source_port/server_peer.cpp source_port/qualify_service_bindings.cpp source_port/qualify_service_bindings.py source_port/controller_peer.cpp source_port/controller_fixtures.py source_port/service_recovery_peer.cpp source_port/service_recovery_fixtures.py source_port/cif_fixtures.py source_port/qualify_ipc_ownership.cpp source_port/qualify_context_ownership.cpp /context/
COPY source_port/context-build.Dockerfile source_port/context-build.Dockerfile.dockerignore /context/
RUN python /context/context_build.py

COPY source_port /recipe/source_port
COPY docs/reference/SPELL2.6.10-src.zip /recipe/docs/reference/SPELL2.6.10-src.zip
RUN python /recipe/source_port/package_native.py --output /package-a
RUN python /recipe/source_port/package_native.py --output /package-b
RUN python -m pip download --require-hashes --only-binary=:all: --dest /wheelhouse -r /recipe/source_port/distribution/runtime.lock

FROM python:3.13.15-slim@sha256:7c61056e61ac89e852de05f3dc6fa51a6dd2181797bceed46aa725dd7cb2cd3b AS installed
RUN apt-get update && apt-get install -y --no-install-recommends libasan8 libubsan1 liblog4cplus-dev libxerces-c-dev libncurses-dev libstdc++6 zlib1g
COPY --from=native /package-a/wheels /distribution
COPY --from=native /wheelhouse /wheelhouse
COPY source_port/qualify_package.py /qualification-input/qualify_package.py
RUN python -I /qualification-input/qualify_package.py

FROM scratch AS evidence
COPY --from=native /out /native
COPY --from=native /package-a/wheels /distribution/a
COPY --from=native /package-b/wheels /distribution/b
COPY --from=native /package-a/package-result.json /distribution/package-a.json
COPY --from=native /package-b/package-result.json /distribution/package-b.json
COPY --from=installed /qualification /installed
