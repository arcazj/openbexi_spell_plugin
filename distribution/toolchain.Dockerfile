# The orchestrator resolves BASE_IMAGE to an exact local image identity.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
RUN apt-get update && apt-get install -y --no-install-recommends g++ gdb nlohmann-json3-dev libxerces-c-dev liblog4cplus-dev libncurses-dev zlib1g-dev
COPY source_port/executor-build.lock /locks/executor-build.lock
COPY source_port/distribution/runtime.lock /locks/runtime.lock
COPY source_port/native/continuation-requirements.txt /locks/continuation-requirements.txt
COPY source_port/experiments/persistent-requirements.txt /locks/persistent-requirements.txt
RUN python -m pip install --no-cache-dir --require-hashes --only-binary=:all: -r /locks/executor-build.lock -r /locks/continuation-requirements.txt -r /locks/persistent-requirements.txt
RUN python -m pip download --require-hashes --only-binary=:all: --dest /wheelhouse -r /locks/runtime.lock
RUN mkdir /toolchain && dpkg-query -W > /toolchain/debian-packages.txt && python -m pip freeze --all > /toolchain/python-packages.txt && c++ --version > /toolchain/compiler.txt
