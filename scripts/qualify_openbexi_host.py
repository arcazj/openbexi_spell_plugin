"""Installed host wheel in the actual OpenBEXI Qt desktop, in a private project."""
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
    parser = argparse.ArgumentParser()
    parser.add_argument('--ide', type=Path, required=True)
    parser.add_argument('--interpreter', type=Path, required=True)
    parser.add_argument('--wheel', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.ide / 'src'))
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtCore import QSettings, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from openbexi_ide.app import MainWindow
    from openbexi_ide.fonts import configure_fonts
    from openbexi_runtime.launch import interpreter_info

    evidence = ROOT / '.qualification/v0.3/openbexi' / uuid.uuid4().hex
    project = evidence / 'project'
    project.mkdir(parents=True)
    report = {'passed': False, 'checks': [], 'wheel_sha256': hashlib.sha256(args.wheel.read_bytes()).hexdigest()}
    application = QApplication([])
    application.setStyle('Fusion')
    configure_fonts(application)
    view = None

    def pip(*arguments):
        result = subprocess.run([str(args.interpreter), '-I', '-m', 'pip', *arguments],
                                capture_output=True, text=True, timeout=60)
        with (evidence / 'installation.log').open('a', encoding='utf-8') as log:
            log.write(result.stdout + result.stderr)
        result.check_returncode()

    def wait(predicate, timeout=45):
        deadline = time.monotonic() + timeout
        while not predicate() and time.monotonic() < deadline:
            application.processEvents()
            QTest.qWait(10)
        assert predicate(), 'Desktop deadline exceeded: ' + view.console.toPlainText()

    def source(name, content):
        path = project / name
        path.write_text(content, encoding='utf-8')
        view.open_file(path)
        return path

    def output():
        return view.console.toPlainText() + '\n' + view.procedure_workspace.output.toPlainText()

    def select_spell():
        view.language.setCurrentIndex(view.language.findData('spell'))
        assert view.language.currentData() == 'spell'

    try:
        pip('install', '--no-deps', '--force-reinstall', str(args.wheel.resolve()))
        assert interpreter_info(args.interpreter, language='spell')['backend']['id'] == 'spell'
        view = MainWindow(project, QSettings(str(evidence / 'preferences.ini'), QSettings.IniFormat))
        view.interpreter = args.interpreter.resolve()
        view.discover_backends()
        view.show()
        wait(lambda: view.language.findData('spell') >= 0)
        select_spell()
        source('run.py', "from spell.lang.functions import Display\nfrom pathlib import Path\nDisplay('DESKTOP_NATIVE_RUN')\nPath('answer.txt').write_text('42')\n")
        view.run_action.trigger()
        wait(lambda: not view.is_busy())
        assert 'DESKTOP_NATIVE_RUN' in output(), output()
        manifests = list(project.glob('.openbexi/runs/*/manifest.json'))
        assert len(manifests) == 1
        assert (manifests[0].parent / 'artifacts/answer.txt').read_text() == '42'
        assert not (project / 'answer.txt').exists()
        report['checks'].append('Installed backend discovery, toolbar Run and isolated result export')

        path = source('debug.py', "from spell.lang.functions import Display\nvalue = 21\ncheckpoint = value + 1\nanswer = checkpoint + 1\nDisplay('DESKTOP_DEBUG_' + str(answer))\nassert answer == 42\n")
        editor = view.current_editor()
        editor.toggle_breakpoint(3)
        view.debug_action.trigger()
        controller = view.procedure_workspace.run_controller(view.procedure_workspace.selected)
        stacks = []
        controller.stack_changed.connect(stacks.append)
        wait(lambda: controller.paused and bool(stacks))
        assert stacks[-1][0]['line'] == 3
        assert not view.out_action.isEnabled()
        values = []
        controller.view_request('variables', {'variablesReference': 1}, values.append)
        wait(lambda: bool(values))
        assert any(value['name'] == 'value' and value['value'] == '21' for value in values[0]['variables'])
        edited = []
        controller.view_request('setVariable', {'variablesReference': 1, 'name': 'value', 'value': '40'}, edited.append)
        wait(lambda: bool(edited))
        assert edited[0]['value'] == '40'
        assert view.grab().save(str(evidence / 'native-debugger.png'))
        editor.toggle_breakpoint(3)
        controller.set_breakpoints(path, [])
        wait(lambda: view.procedure_workspace.control_buttons['stepIn'].isEnabled())
        view.procedure_workspace.control_buttons['stepIn'].click()
        wait(lambda: controller.paused and stacks[-1][0]['line'] == 4)
        wait(lambda: view.procedure_workspace.control_buttons['continue'].isEnabled())
        view.procedure_workspace.control_buttons['continue'].click()
        wait(lambda: not view.is_busy())
        assert 'DESKTOP_DEBUG_42' in output(), output()
        report['checks'].append('Actual workspace Debug, breakpoint, DAP stack/variables/edit, workspace Step and Continue')

        source('prompt.py', "from spell.lang.functions import Prompt, Display\nfrom spell.lang.constants import YES_NO\nfrom spell.lang.modifiers import Type\nassert Prompt('Desktop native prompt?', {Type:YES_NO}) is True\nDisplay('DESKTOP_PROMPT_COMPLETE')\n")
        view.debug_action.trigger()
        workspace = view.procedure_workspace
        wait(lambda: workspace.selected is not None and workspace.selected.prompt and workspace.choices is not None)
        workspace.choices.buttons()[0].click()
        assert workspace.commit.isEnabled()
        workspace.commit.click()
        wait(lambda: not view.is_busy())
        assert 'DESKTOP_PROMPT_COMPLETE' in output(), output()
        report['checks'].append('Native prompt answered through workspace choice and Commit widgets')

        source('stop.py', "import time\nfrom spell.lang.functions import Display\nDisplay('DESKTOP_STOP_READY')\nwhile True:\n    time.sleep(0.02)\n")
        view.run_action.trigger()
        wait(lambda: 'DESKTOP_STOP_READY' in output())
        wait(lambda: view.procedure_workspace.control_buttons['abort'].isEnabled())
        view.procedure_workspace.control_buttons['abort'].click()
        wait(lambda: not view.is_busy())
        report['checks'].append('Desktop Stop closes its owned native runtime')

        pip('uninstall', '-y', 'openbexi-spell-host')
        view.discover_backends()
        wait(lambda: view.language.findData('spell') < 0)
        assert interpreter_info(args.interpreter)['backends'] == []
        source('plain.py', "print('PYTHON_AFTER_PLUGIN_REMOVAL')\n")
        view.run_action.trigger()
        wait(lambda: not view.is_busy())
        assert 'PYTHON_AFTER_PLUGIN_REMOVAL' in output(), output()
        report['checks'].append('Uninstall removes backend; ordinary Python Run still works')
        report['passed'] = True
    except Exception:
        report['error'] = traceback.format_exc()
        raise
    finally:
        if view is not None:
            (evidence / 'console.txt').write_text(view.console.toPlainText(), encoding='utf-8')
            for controller in view.procedure_workspace.controllers:
                controller.stop()
            view.run_controller.stop()
            view.debug_controller.stop()
            wait(lambda: not view.is_busy())
            view.close()
            application.processEvents()
        report['ide_commit'] = subprocess.check_output(['git', '-C', str(args.ide), 'rev-parse', 'HEAD'], text=True).strip()
        report['image'] = subprocess.check_output(['docker', 'image', 'inspect', 'openbexi-spell-host:0.3.0', '--format', '{{.Id}}'], text=True).strip()
        (evidence / 'result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        print(evidence, flush=True)


if __name__ == '__main__':
    main()
