ARG NATIVE_BASE=openbexi-spell-native:v06-diagnostic-6a340659e519
ARG RUNTIME_BASE=openbexi-spell-dss:v05-dta-time-obs-development
FROM ${NATIVE_BASE} AS native
COPY source_port/dta_ipc_patches.py source_port/dta_native_patches.py source_port/dta_time_patches.py source_port/data_files_native_patches.py source_port/ui_native_patches.py source_port/flow_patches.py source_port/flow_analyze.py conformance/dta_ipc_build.py distribution/incremental_native.py /dta-recipe/
RUN python /dta-recipe/dta_ipc_build.py

FROM ${RUNTIME_BASE}
USER root
COPY --from=native /dta-native-patch /opt/dta-native-patch
RUN python -c "import importlib.metadata as m, pathlib, shutil, json; d=m.distribution('openbexi-spell-source'); manifest=json.loads(pathlib.Path('/opt/dta-native-patch/manifest.json').read_text()); [(shutil.copyfile('/opt/dta-native-patch/compiled/'+name, next(pathlib.Path(d.locate_file(f)) for f in d.files if str(f).endswith('/bin/'+name)))) for name in manifest['artifacts']]"
USER 10003:10003
