FROM python:3.13.15-slim@sha256:7c61056e61ac89e852de05f3dc6fa51a6dd2181797bceed46aa725dd7cb2cd3b AS probe
RUN apt-get update && apt-get install -y --no-install-recommends g++ libxerces-c-dev liblog4cplus-dev zlib1g-dev
COPY docs/reference/SPELL2.6.10-src.zip /input/SPELL2.6.10-src.zip
COPY source_port/native_probe.py /input/native_probe.py
RUN python -I /input/native_probe.py

FROM scratch AS evidence
COPY --from=probe /out /
