"""Exercise child prompt answers typed into the actual IDE console in Run/Debug."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ide', type=Path, required=True)
    parser.add_argument('--wheel', type=Path, required=True)
    parser.add_argument('--image', required=True)
    args = parser.parse_args()
    image = subprocess.check_output(['docker','image','inspect',args.image,'--format','{{.Id}}'],text=True).strip()
    os.environ['OPENBEXI_SPELL_IMAGE'] = image
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    sys.path.insert(0, str(args.ide.resolve()/'src'))
    from PySide6.QtCore import QSettings, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from openbexi_ide.app import MainWindow

    evidence = ROOT/'.qualification/children/desktop'/uuid.uuid4().hex
    project = evidence/'project'
    project.mkdir(parents=True)
    environment = evidence/'interpreter'
    subprocess.run([sys._base_executable,'-m','venv',str(environment)],check=True)
    interpreter = environment/('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    installation = subprocess.run([str(interpreter),'-I','-m','pip','install','--no-index','--no-deps',str(args.wheel.resolve())],capture_output=True)
    (evidence/'installation.log').write_bytes(installation.stdout+installation.stderr)
    installation.check_returncode()
    report = {'passed':False,'image':image,'checks':[],
              'scope':'Actual Qt Run/Debug console keyboard routing in a private project; browser interaction and fresh-Windows installation are not asserted.',
              'wheel_sha256':hashlib.sha256(args.wheel.read_bytes()).hexdigest(),
              'harness_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'ide_commit':subprocess.check_output(['git','-C',str(args.ide),'rev-parse','HEAD'],text=True).strip()}
    application = QApplication([])
    view = MainWindow(project,QSettings(str(evidence/'preferences.ini'),QSettings.IniFormat))
    view.interpreter = interpreter.resolve()
    view.discover_backends()
    view.show()

    def wait(predicate, timeout=60):
        deadline = time.monotonic()+timeout
        while not predicate() and time.monotonic()<deadline:
            application.processEvents()
            QTest.qWait(10)
        assert predicate(), 'Desktop deadline exceeded: '+view.console.toPlainText()

    try:
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
            controller = view.run_controller if mode == 'run' else view.debug_controller
            action.trigger()
            for prompt,answer in (('CHILD_FIRST_CHOICE','0'),('CHILD_SECOND_CHOICE','1')):
                wait(lambda: prompt in view.console.toPlainText() and view.input.isEnabled()
                     and (mode == 'run' or view.debug_controller.input_pending))
                view.console.setFocus()
                QTest.keyClicks(view.console,answer)
                assert view.input.text() == answer, 'Console typing did not reach the enabled input field'
                QTest.keyClick(view.input,Qt.Key_Return)
            wait(lambda: not controller.running)
            console = view.console.toPlainText()
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
            report['checks'].append(mode+': two child menu answers typed through the readonly console and delivered to the child; parent finishes successfully')
        report['passed'] = True
    except Exception:
        report['error'] = traceback.format_exc()
        raise
    finally:
        (evidence/'console.txt').write_text(view.console.toPlainText(),encoding='utf-8',newline='\n')
        view.run_controller.stop()
        view.debug_controller.stop()
        try:
            wait(lambda: not view.is_busy())
        finally:
            view.close()
            application.processEvents()
            (evidence/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
            print(evidence,flush=True)


if __name__ == '__main__':
    main()
