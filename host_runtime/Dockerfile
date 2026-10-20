# A frozen complete toolchain supplies the compiler, runtime libraries and locked
# wheelhouse. No apt or package-index access occurs in this diagnostic host build.
ARG TOOLCHAIN_IMAGE
ARG RUNTIME_IMAGE=${TOOLCHAIN_IMAGE}
FROM ${TOOLCHAIN_IMAGE} AS bridge
ARG NATIVE_WHEEL=.runtime-input/native/*.whl
COPY ${NATIVE_WHEEL} /distribution/
RUN python -m pip install --no-index --find-links=/wheelhouse /distribution/*.whl
COPY host_runtime/native_bridge.cpp host_runtime/build_bridge.py /bridge/
RUN python /bridge/build_bridge.py

FROM ${RUNTIME_IMAGE}
COPY --from=bridge /distribution /distribution
RUN python -m pip install --no-index --find-links=/wheelhouse /distribution/*.whl && rm -rf /distribution
COPY --from=bridge /bridge/spell-host-ipc /bridge/build.json /bridge/
COPY host_runtime/python /opt/host
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 ASAN_OPTIONS=detect_leaks=0:abort_on_error=1 UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1
RUN mkdir /workspace && chown 10003:10003 /workspace
USER 10003:10003
WORKDIR /workspace
ENTRYPOINT ["python", "-I", "/opt/host/adapter.py"]
