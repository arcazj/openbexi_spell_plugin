ARG NATIVE_BASE
FROM ${NATIVE_BASE}
COPY source_port/shutdown_pause_patches.py conformance/shutdown_pause.cpp conformance/shutdown_pause_build.py distribution/incremental_native.py /shutdown-recipe/
RUN python /shutdown-recipe/shutdown_pause_build.py
