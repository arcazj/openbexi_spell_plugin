FROM python:3.13-slim@sha256:eb43ff125d8d58d7449dcba7d336c23bcac412f526d861db493b9994d8010280 AS probe
RUN apt-get update && apt-get install -y --no-install-recommends g++ libxerces-c-dev liblog4cplus-dev zlib1g-dev
COPY docs/reference/SPELL2.6.10-src.zip /input/SPELL2.6.10-src.zip
COPY source_port/native_probe.py /input/native_probe.py
RUN python -I /input/native_probe.py

FROM scratch AS evidence
COPY --from=probe /out /
