# Development integration only: keep accepted host/DSS images untouched.
ARG CONFORMANCE_IMAGE=openbexi-spell-host:v05-ui-flow-data-final
FROM ${CONFORMANCE_IMAGE} AS qualified
FROM openbexi-spell-dss:v05-common
USER root
COPY --from=qualified /opt/data-files-conformance-patch /opt/data-files-conformance-patch
COPY --from=qualified /opt/data-files-native-patch /opt/data-files-native-patch
COPY --from=qualified /opt/combined-native-patch /opt/combined-native-patch
RUN python -c "import pathlib, shutil, importlib.metadata as m; d=m.distribution('openbexi-spell-source'); source=pathlib.Path('/opt/data-files-conformance-patch/patched/spell'); shutil.copytree(source,pathlib.Path('/usr/local/lib/python3.13/site-packages/spell'),dirs_exist_ok=True); artifacts={'SPELL-Context':'/opt/data-files-native-patch/SPELL-Context','libspell_executor313.so':'/opt/combined-native-patch/compiled/libspell_executor313.so'}; [(shutil.copyfile(value,next(pathlib.Path(d.locate_file(f)) for f in d.files if str(f).endswith('/bin/'+name)))) for name,value in artifacts.items()]"
USER 10003:10003
