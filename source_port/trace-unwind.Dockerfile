# SPDX-License-Identifier: GPL-3.0-or-later
ARG PYTHON_BASE=python:3.13.15-slim@sha256:7c61056e61ac89e852de05f3dc6fa51a6dd2181797bceed46aa725dd7cb2cd3b
FROM ${PYTHON_BASE} AS probe
RUN apt-get update && apt-get install -y --no-install-recommends g++ libxerces-c-dev liblog4cplus-dev libncurses-dev zlib1g-dev
COPY source_port/trace_unwind_probe.cpp /probe.cpp
RUN c++ $(python3-config --includes) /probe.cpp $(python3-config --embed --ldflags) -o /probe && (/probe > /trace-result.txt 2>&1; echo $? > /trace-exit.txt)
FROM scratch
COPY --from=probe /trace-result.txt /trace-exit.txt /
