FROM python:3.13.15-slim@sha256:7c61056e61ac89e852de05f3dc6fa51a6dd2181797bceed46aa725dd7cb2cd3b AS bridge
RUN apt-get update && apt-get install -y --no-install-recommends g++ nlohmann-json3-dev liblog4cplus-dev libxerces-c-dev libncurses-dev zlib1g-dev
COPY .qualification/v0.3/native-package-05/distribution/a/*.whl /distribution/
COPY source_port/distribution/runtime.lock /runtime.lock
RUN python -m pip download --require-hashes --only-binary=:all: --dest /distribution -r /runtime.lock
RUN python -m pip install --no-index --find-links=/distribution /distribution/openbexi_spell_source-0.3.0-cp313-cp313-linux_x86_64.whl
COPY host_runtime/native_bridge.cpp host_runtime/build_bridge.py /bridge/
RUN python /bridge/build_bridge.py

FROM python:3.13.15-slim@sha256:7c61056e61ac89e852de05f3dc6fa51a6dd2181797bceed46aa725dd7cb2cd3b
RUN apt-get update && apt-get install -y --no-install-recommends libasan8 libubsan1 liblog4cplus-dev libxerces-c-dev libncurses-dev libstdc++6 zlib1g && rm -rf /var/lib/apt/lists/*
COPY --from=bridge /distribution /distribution
RUN python -m pip install --no-index --find-links=/distribution /distribution/openbexi_spell_source-0.3.0-cp313-cp313-linux_x86_64.whl && rm -rf /distribution
COPY --from=bridge /bridge/spell-host-ipc /bridge/build.json /bridge/
COPY host_runtime/python /opt/host
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 ASAN_OPTIONS=detect_leaks=0:abort_on_error=1 UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1
RUN mkdir /workspace && chown 10003:10003 /workspace
USER 10003:10003
WORKDIR /workspace
ENTRYPOINT ["python", "-I", "/opt/host/adapter.py"]
