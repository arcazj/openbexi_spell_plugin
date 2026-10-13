"""Fresh native procedure checks for terminal policy and configuration isolation."""
from pathlib import Path

from spell.lang.constants import ABORT, NOACTION, SKIP
from spell.lang.functions import ChangeLanguageConfig, GetSharedData, GetTM, SetSharedData
from spell.lang.helpers.datahelper import GetSharedData_Helper
from spell.lib.registry import REGISTRY
from spell.runtime import ARGS


def run():
    scenario = ARGS['scenario']
    # The preceding native worker changed these defaults and then aborted.
    assert REGISTRY['CTX'].getFunctionConfig('GetTM')['Wait'] is False
    helper = GetSharedData_Helper()
    helper.configure()
    assert helper.getConfig('HandleError') is True
    ChangeLanguageConfig(GetTM, Wait=True)
    ChangeLanguageConfig(GetSharedData, HandleError=False)
    assert REGISTRY['CTX'].getFunctionConfig('GetTM')['Wait'] is True
    try:
        if scenario == 'failure-auto':
            GetSharedData('absent-common-edge', HandleError=True, PromptFailure=False, OnFailure=ABORT)
        elif scenario == 'failure-interactive':
            GetSharedData('absent-common-edge', HandleError=True, OnFailure=ABORT | SKIP)
        elif scenario == 'uncaught':
            GetSharedData('absent-common-edge', HandleError=False)
        elif scenario in ('true-auto', 'false-auto'):
            assert SetSharedData(Name='common-edge', Value=10)
            if scenario == 'true-auto':
                SetSharedData(Name='common-edge', Value=11, PromptUser=False, OnTrue=ABORT)
            else:
                SetSharedData(Name='common-edge', Value=11, Expected=-1, PromptUser=False, OnFalse=ABORT)
        elif scenario == 'recovery':
            assert SetSharedData(Name='common-edge', Value=42, OnTrue=NOACTION)
            assert GetSharedData('common-edge') == 42
            Path('recovered.txt').write_text('fresh native executor; explicit restart; original defaults', encoding='utf-8')
        else:
            raise AssertionError(scenario)
        Path('continued.txt').write_text('completed', encoding='utf-8')
    finally:
        Path('cleanup.txt').write_text(scenario, encoding='utf-8')


run()
