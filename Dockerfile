FROM python:3.13-slim@sha256:eb43ff125d8d58d7449dcba7d336c23bcac412f526d861db493b9994d8010280 AS zlib-build
COPY scripts/build_zlib.sh /tmp/build_zlib.sh
RUN sh /tmp/build_zlib.sh

FROM python:3.13-slim@sha256:eb43ff125d8d58d7449dcba7d336c23bcac412f526d861db493b9994d8010280 AS wheel-build
WORKDIR /build
COPY build-requirements.lock .
RUN python -m pip install --require-hashes --only-binary=:all: -r build-requirements.lock
COPY pyproject.toml README.md LICENSE NOTICE ./
COPY src ./src
RUN python -m pip wheel --no-build-isolation --no-deps --wheel-dir /wheels .

FROM python:3.13-slim@sha256:eb43ff125d8d58d7449dcba7d336c23bcac412f526d861db493b9994d8010280
COPY --from=zlib-build /tmp/zlib-fixed.deb /tmp/zlib-fixed.deb
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       libc6=2.41-12+deb13u4 libssl3t64=3.5.7-1~deb13u3 \
       libpcre2-8-0=10.46-1~deb13u3 libsqlite3-0=3.46.1-7+deb13u2 \
    && dpkg -i /tmp/zlib-fixed.deb && ldconfig \
    && rm -f /tmp/zlib-fixed.deb && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10003 dss \
    && useradd --uid 10003 --gid 10003 --no-create-home --shell /usr/sbin/nologin dss \
    && mkdir -p /var/lib/dss && chown 10003:10003 /var/lib/dss
COPY --from=wheel-build /wheels /tmp/wheels
RUN python -m pip install --no-cache-dir --no-deps /tmp/wheels/*.whl && rm -rf /tmp/wheels
LABEL org.opencontainers.image.title="openbexi_spell_plugin DSS" \
      org.opencontainers.image.version="0.1.0" \
      org.openbexi.scope="deterministic-local-test"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /var/lib/dss
USER 10003:10003
EXPOSE 8085
ENTRYPOINT ["python", "-I", "-m", "dss.local"]
CMD ["--port", "8085", "--database", "/var/lib/dss/dss.sqlite"]
