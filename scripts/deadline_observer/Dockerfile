FROM python:3.13.15-slim@sha256:7c61056e61ac89e852de05f3dc6fa51a6dd2181797bceed46aa725dd7cb2cd3b
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev openssl \
    && rm -rf /var/lib/apt/lists/*
COPY server/requirements-test.lock /tmp/requirements-test.lock
RUN python -m pip install --no-cache-dir -r /tmp/requirements-test.lock
RUN useradd --uid 10003 --create-home tester && mkdir /evidence && chown tester /evidence
USER 10003:10003
ENV PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 QT_QPA_PLATFORM=offscreen TMPDIR=/tmp
WORKDIR /workspace
