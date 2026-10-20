"""Upgrade the installed host through the real IDE plugin manager and run child prompts."""
import argparse
from email.parser import BytesParser
import hashlib
import importlib.metadata
import json
import os
import platform
from pathlib import Path
import subprocess
import sys
import time
import traceback
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def wheel_version(path):
    with zipfile.ZipFile(path) as archive:
        name, = [n for n in archive.namelist() if n.endswith('.dist-info/METADATA')]
        return BytesParser().parsebytes(archive.read(name))['Version']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ide', type=Path, required=True)
    parser.add_argument('--wheel', type=Path, required=True)
    parser.add_argument('--image', required=True)
    parser.add_argument('--previous-wheel', type=Path, required=True)
    parser.add_argument('--installed-ide-wheel', type=Path,
                        help='Audit and exercise this installed IDE instead of importing the source checkout')
    args = parser.parse_args()
    previous_version, target_version = wheel_version(args.previous_wheel), wheel_version(args.wheel)
    image = subprocess.check_output(['docker','image','inspect',args.image,'--format','{{.Id}}'],text=True).strip()
    os.environ['OPENBEXI_SPELL_IMAGE'] = image
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    installed_ide = None
    if args.installed_ide_wheel:
        import runpy
        auditor = ROOT/'distribution/workflow_evidence.py'
        proof = runpy.run_path(str(auditor))
        bindings = {'openbexi-ide': {'path': str(args.installed_ide_wheel.resolve()),
                    'sha256': hashlib.sha256(args.installed_ide_wheel.read_bytes()).hexdigest()}}
        installed_ide = {'wheels': proof['installed_wheels'](bindings, '.'),
                        'imports': proof['imported_modules'](bindings,
                            {'openbexi_ide':'openbexi-ide','openbexi_runtime':'openbexi-ide'}, '.'),
                        'auditor_sha256': hashlib.sha256(auditor.read_bytes()).hexdigest()}
    else:
        sys.path.insert(0, str(args.ide.resolve()/'src'))
    from PySide6.QtCore import QSettings, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from openbexi_ide.app import MainWindow
    from openbexi_ide.plugin_manager import PluginManager

    evidence = ROOT/'.qualification/children/desktop'/uuid.uuid4().hex
    project = evidence/'project'
    project.mkdir(parents=True)
    environment = evidence/'interpreter'
    subprocess.run([sys._base_executable,'-m','venv',str(environment)],check=True)
    interpreter = environment/('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    installation = subprocess.run([str(interpreter),'-I','-m','pip','install','--no-index','--no-deps',str(args.previous_wheel.resolve())],capture_output=True)
    (evidence/'installation.log').write_bytes(installation.stdout+installation.stderr)
    installation.check_returncode()
    report = {'passed':False,'image':image,'checks':[],
              'scope':'Actual Qt plugin manager upgrade/removal and workspace Run/Debug child prompt widgets in a private project.',
              'installed_ide': installed_ide,
              'wheel_sha256':hashlib.sha256(args.wheel.read_bytes()).hexdigest(),
              'previous_wheel_sha256':hashlib.sha256(args.previous_wheel.read_bytes()).hexdigest(),
              'harness_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'qt_interpreter':{'executable':sys.executable,'python':sys.version,'platform':platform.platform(),
                  'system':platform.system(),'implementation':platform.python_implementation(),
                  'dependencies':{name:importlib.metadata.version(name) for name in ('PySide6-Essentials','shiboken6')}},
              'ide_source_inputs':{p.relative_to(args.ide.resolve()).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in (args.ide.resolve()/'src').rglob('*.py')},
              'ide_commit':subprocess.check_output(['git','-C',str(args.ide),'rev-parse','HEAD'],text=True).strip()}
    application = QApplication([])
    view = MainWindow(project,QSettings(str(evidence/'preferences.ini'),QSettings.IniFormat))
    view.interpreter = interpreter.resolve()
    view.discover_backends()
    view.show()

    def output():
        return view.console.toPlainText() + '\n' + view.procedure_workspace.output.toPlainText()

    def wait(predicate, timeout=60):
        deadline = time.monotonic()+timeout
        while not predicate() and time.monotonic()<deadline:
            application.processEvents()
            QTest.qWait(10)
        assert predicate(), 'Desktop deadline exceeded: '+output()

    def metadata():
        code = "import importlib.metadata as m,openbexi_spell_host as h,json;print(json.dumps([m.version('openbexi-spell-host'),h.__version__]))"
        return json.loads(subprocess.check_output([str(interpreter),'-I','-c',code],text=True))

    manager = None
    sentinel = project/'preserved-user-file.txt'
    sentinel.write_text('preserve through plugin upgrade and removal',encoding='utf-8')
    settings = QSettings(str(evidence/'preferences.ini'),QSettings.IniFormat)
    settings.setValue('qualification/preserved','unchanged')
    settings.sync()
    try:
        assert metadata() == [previous_version,previous_version]
        manager = PluginManager(interpreter,view)
        manager.plugins_changed.connect(view.discover_backends)
        manager.show()
        wait(lambda: manager.operation is None and manager.packages.count() == 1)
        assert manager.packages.item(0).data(Qt.UserRole)['version'] == previous_version
        assert manager.install_wheel(args.wheel)
        wait(lambda: manager.operation is None and manager.packages.count() == 1
             and manager.packages.item(0).data(Qt.UserRole)['version'] == target_version)
        assert metadata() == [target_version,target_version]
        installed_root = Path(subprocess.check_output([str(interpreter),'-I','-c',
            "import sysconfig;print(sysconfig.get_path('purelib'))"],text=True).strip())
        installed = {}
        with zipfile.ZipFile(args.wheel) as archive:
            for name in archive.namelist():
                if name.endswith('/RECORD'):
                    continue  # pip adds its own installed files to RECORD.
                original = archive.read(name)
                assert (installed_root/name).read_bytes() == original, name
                installed[name] = hashlib.sha256(original).hexdigest()
        report['installed_wheel_members'] = installed
        (evidence/'upgrade-console.txt').write_text(manager.output.toPlainText(),encoding='utf-8')
        manager.hide()
        report['checks'].append(f'Actual IDE plugin manager upgrades installed host {previous_version} to {target_version}; distribution and module versions agree')
        wait(lambda: view.language.findData('spell') >= 0)
        view.language.setCurrentIndex(view.language.findData('spell'))
        (project/'child.py').write_text('''from spell.lang.functions import Prompt, Display
from spell.lang.constants import YES_NO
from pathlib import Path
assert Prompt('CHILD_FIRST_CHOICE', Type=YES_NO) is True
assert Prompt('CHILD_SECOND_CHOICE', Type=YES_NO) is False
Path('child-result.txt').write_text('yes/no')
Display('CHILD_CHOICES_COMPLETE')
''',encoding='utf-8',newline='\n')
        for mode in ('run','debug'):
            previous_manifests = set(project.glob('.openbexi/runs/*/manifest.json'))
            marker = 'PARENT_COMPLETE_'+mode
            source = project/(mode+'.py')
            source.write_text("from spell.lang.functions import StartProc, Display\nassert StartProc('child', HandleError=False) is True\nDisplay("+repr(marker)+")\n",encoding='utf-8',newline='\n')
            view.open_file(source)
            action = view.run_action if mode == 'run' else view.debug_action
            action.trigger()
            workspace = view.procedure_workspace
            for prompt,answer in (('CHILD_FIRST_CHOICE',0),('CHILD_SECOND_CHOICE',1)):
                wait(lambda: workspace.selected is not None and workspace.selected.prompt
                     and prompt in workspace.question.text() and workspace.prompt_body.isEnabled()
                     and workspace.choices is not None)
                workspace.choices.buttons()[answer].click()
                wait(workspace.commit.isEnabled)
                workspace.commit.click()
            wait(lambda: not view.is_busy())
            console = output()
            assert marker in console and 'CHILD_CHOICES_COMPLETE' in console, console
            assert 'exit 0' in console, console
            new_manifests = set(project.glob('.openbexi/runs/*/manifest.json'))-previous_manifests
            assert len(new_manifests) == 1, new_manifests
            manifest_path, = new_manifests
            manifest = json.loads(manifest_path.read_bytes())
            assert manifest['image'] == image
            assert (manifest_path.parent/'artifacts/child-result.txt').read_text() == 'yes/no'
            assert not (project/'child-result.txt').exists()
            (evidence/(mode+'-console.txt')).write_text(console,encoding='utf-8',newline='\n')
            report['checks'].append(mode+': two child menu answers selected and committed through workspace widgets; parent finishes successfully')
        manager.show()
        manager.packages.setCurrentRow(0)
        assert manager.remove_selected()
        wait(lambda: manager.operation is None and manager.packages.count() == 0)
        wait(lambda: view.language.findData('spell') < 0)
        assert not (installed_root/'openbexi_spell_host').exists()
        assert not list(installed_root.glob('openbexi_spell_host-*.dist-info'))
        (evidence/'removal-console.txt').write_text(manager.output.toPlainText(),encoding='utf-8')
        manager.hide()
        view.language.setCurrentIndex(view.language.findData('python'))
        ordinary = project/'ordinary.py'
        ordinary.write_text("print('ORDINARY_PYTHON_AFTER_PLUGIN_REMOVAL')\n",encoding='utf-8')
        view.open_file(ordinary)
        view.run_action.trigger()
        wait(lambda: not view.is_busy())
        assert 'ORDINARY_PYTHON_AFTER_PLUGIN_REMOVAL' in view.console.toPlainText()
        assert 'exit 0' in view.console.toPlainText()
        assert sentinel.read_text(encoding='utf-8') == 'preserve through plugin upgrade and removal'
        settings.sync()
        assert settings.value('qualification/preserved') == 'unchanged'
        report['checks'].append('Plugin manager removes the upgraded host; ordinary Python still runs and project/preferences survive')
        assert report['ide_source_inputs']=={p.relative_to(args.ide.resolve()).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (args.ide.resolve()/'src').rglob('*.py')}
        if installed_ide:
            assert installed_ide['wheels'] == proof['installed_wheels'](bindings, '.')
        report['passed'] = True
    except Exception:
        report['error'] = traceback.format_exc()
        raise
    finally:
        (evidence/'console.txt').write_text(output(),encoding='utf-8',newline='\n')
        for controller in view.procedure_workspace.controllers:
            controller.stop()
        view.run_controller.stop()
        view.debug_controller.stop()
        try:
            wait(lambda: not view.is_busy())
        finally:
            if manager is not None:
                manager.close()
            view.close()
            application.processEvents()
            (evidence/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
            print(evidence,flush=True)


if __name__ == '__main__':
    main()
