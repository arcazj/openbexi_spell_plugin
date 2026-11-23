# The frozen runtime supplies its original wheel and source provenance.
# Existing prepared images may supply both the toolchain and the runtime.
ARG TOOLCHAIN_IMAGE
ARG RUNTIME_IMAGE=${TOOLCHAIN_IMAGE}
FROM ${RUNTIME_IMAGE} AS runtime
FROM ${TOOLCHAIN_IMAGE} AS build
USER root
ARG NATIVE_PROFILE=optimized
ARG SOURCE_DATE_EPOCH
ENV SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH}
COPY --from=runtime /usr/local/lib/python3.13/site-packages/spell_native/ /usr/local/lib/python3.13/site-packages/spell_native/
COPY --from=runtime /usr/local/lib/python3.13/site-packages/libSPELL_DTA_v3.py /usr/local/lib/python3.13/site-packages/
COPY host_runtime/native/*.H host_runtime/native/private_bridge.cpp /candidate/
COPY host_runtime/build_native_profile.py host_runtime/build_admission_context.py host_runtime/native_prompt_patch.py host_runtime/native_terminal_patch.py host_runtime/native_startup_ack_patch.py host_runtime/python/epoch_connection.py /candidate/
RUN python /candidate/build_native_profile.py --profile "${NATIVE_PROFILE}" --native-prompts --native-terminal

FROM runtime
USER root
COPY --from=build /opt/v08-native-home /opt/v08-native-home
COPY --from=build /usr/local/lib/python3.13/site-packages/libSPELL_DTA_v3.py /usr/local/lib/python3.13/site-packages/
COPY --from=build /candidate/ /candidate/
USER 10003:10003
LABEL org.openbexi.release-scope="unqualified-native-candidate"
