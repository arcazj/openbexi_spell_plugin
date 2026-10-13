FROM openbexi-spell-native:v06-integrated-diagnostic-97f9a6 AS native
COPY source_port/scheduler_patches.py conformance/scheduler_native_build.py distribution/incremental_native.py /scheduler-recipe/
RUN python /scheduler-recipe/scheduler_native_build.py

FROM openbexi-spell-dss:v05-cmd-02
USER root
COPY --from=native /scheduler-native-patch /opt/scheduler-native-patch
COPY --from=native /usr/local/lib/python3.13/site-packages/spell /usr/local/lib/python3.13/site-packages/spell
COPY --from=native /scheduler-native-patch/runtime-bin/ /usr/local/lib/python3.13/site-packages/spell_native/bin/
RUN chmod +x /usr/local/lib/python3.13/site-packages/spell_native/bin/SPELL-*
USER 10003:10003
