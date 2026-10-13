ARG NATIVE_BASE
FROM ${NATIVE_BASE} AS native
COPY source_port/data_files_native_patches.py conformance/data_files_native_build.py /data-files-recipe/
RUN python /data-files-recipe/data_files_native_build.py

FROM openbexi-spell-host:v05-data-files
USER root
COPY --from=native /data-files-native /opt/data-files-native-patch
RUN python -c "import importlib.metadata as m, pathlib, shutil; d=m.distribution('openbexi-spell-source'); p=next(pathlib.Path(d.locate_file(f)) for f in d.files if str(f).endswith('/bin/SPELL-Context')); shutil.copyfile('/opt/data-files-native-patch/SPELL-Context',p)"
USER 10003:10003
