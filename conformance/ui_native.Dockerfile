ARG NATIVE_BASE=openbexi-spell-native:v06-diagnostic-6a340659e519
ARG RUNTIME_BASE=openbexi-spell-host:v05-data-files-native
FROM ${NATIVE_BASE} AS native
COPY source_port/ui_native_patches.py conformance/ui_native_build.py distribution/incremental_native.py /ui-recipe/
RUN python /ui-recipe/ui_native_build.py

FROM ${RUNTIME_BASE}
USER root
COPY --from=native /ui-native-patch /opt/ui-native-patch
RUN python -c "import importlib.metadata as m, pathlib, shutil; d=m.distribution('openbexi-spell-source'); p=next(pathlib.Path(d.locate_file(f)) for f in d.files if str(f).endswith('/bin/libspell_executor313.so')); shutil.copyfile('/opt/ui-native-patch/compiled/libspell_executor313.so',p)"
USER 10003:10003
