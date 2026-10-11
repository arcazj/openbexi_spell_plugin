FROM python:3.13.15-slim@sha256:7c61056e61ac89e852de05f3dc6fa51a6dd2181797bceed46aa725dd7cb2cd3b AS probe
RUN apt-get update && apt-get install -y --no-install-recommends g++ libxerces-c-dev liblog4cplus-dev zlib1g-dev
COPY source_port/experiments /input
COPY source_port/native/continuation.cpp source_port/native/SPELLcontinuation313.H /input/native/
RUN python /input/build_probe.py

FROM scratch AS evidence
COPY --from=probe /out /
