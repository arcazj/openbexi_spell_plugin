# Prepared toolchain must contain the verified frozen spell_native wheel,
# GIL CPython 3.13.15+ and native development headers. No online install here.
ARG TOOLCHAIN_IMAGE
FROM ${TOOLCHAIN_IMAGE}
USER root
ARG NATIVE_PROFILE=optimized
ARG SOURCE_DATE_EPOCH
ENV SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH}
COPY host_runtime/native/*.H host_runtime/native/private_bridge.cpp /candidate/
COPY host_runtime/build_native_profile.py host_runtime/build_admission_context.py host_runtime/native_prompt_patch.py host_runtime/native_terminal_patch.py host_runtime/python/epoch_connection.py /candidate/
RUN python /candidate/build_native_profile.py --profile "${NATIVE_PROFILE}" --native-prompts --native-terminal
USER 10003:10003
LABEL org.openbexi.release-scope="unqualified-native-candidate"
