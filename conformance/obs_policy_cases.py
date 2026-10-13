"""Actual native telemetry failure/false-result policy, including prompt choices."""
from obs_qualification_cases import contract, POLICY

contract('false-noaction', ['EXAMPLE-042', 'OUTCOME-VERIFY-FAIL'],
         "result = Verify('TM.POWER.BUS_VOLTAGE', eq, 0.0, Wait=False, Retries=0, OnFalse=NOACTION)\nassert not result\nequal(result.keys(), ['0: TM.POWER.BUS_VOLTAGE'])",
         "result = Verify('TM.POWER.BUS_VOLTAGE', eq, 28.0, Wait=False, Retries=0, OnFalse=NOACTION)\nassert result\nequal(result.keys(), ['0: TM.POWER.BUS_VOLTAGE'])",
         "rejects(DriverException, lambda: Verify('TM.ABSENT', eq, 0.0, OnFalse=NOACTION, HandleError=False))")

contract('false-automatic', ['EXAMPLE-043', 'SECTION-4-3-5-035'],
         "result = Verify('TM.POWER.BUS_VOLTAGE', eq, 0.0, Wait=False, Retries=0, PromptUser=False, OnFalse=SKIP)\nassert result is True",
         "result = Verify('TM.POWER.BUS_VOLTAGE', eq, 0.0, Wait=False, Retries=0, PromptUser=False, OnFalse=CANCEL)\nassert result is False",
         "rejects(SyntaxException, lambda: Verify('TM.POWER.BUS_VOLTAGE', eq, 0.0, Wait=False, Retries=0, PromptUser=False, OnFalse=SKIP|CANCEL))")

contract('false-default', ['ERRATUM-VERIFY-ONFALSE-DEFAULT', 'OUTCOME-VERIFY-PASS'],
         "plan_prompt(['ABORT', 'SKIP', 'RECHECK', 'CANCEL'], 'SKIP')\nresult = Verify('TM.POWER.BUS_VOLTAGE', eq, 0.0, Wait=False, Retries=0)\nassert result is True",
         "plan_prompt(['ABORT', 'SKIP', 'RECHECK', 'CANCEL'], 'CANCEL')\nresult = Verify('TM.POWER.BUS_VOLTAGE', eq, 0.0, Wait=False, Retries=0)\nassert result is False",
         "rejects(SyntaxException, lambda: Verify('TM.POWER.BUS_VOLTAGE', eq, 0.0, OnFalse='invalid'))",
         oracle='LRM p41 lists ABORT|SKIP|RECHECK|CANCEL; p114 is an illustrative profile. Actual unmodified original native language.xml default and IPC choices are observed; SKIP/CANCEL results and invalid-mask recovery are asserted.')

contract('false-actions-erratum', ['ERRATUM-VERIFY-FALSE-ACTION-MODIFIER'],
         "plan_prompt(['CANCEL'], 'CANCEL')\nresult = Verify('TM.POWER.BUS_VOLTAGE', eq, 0.0, Wait=False, Retries=0, OnFalse=CANCEL, OnFailure=SKIP)\nassert result is False",
         "plan_prompt(['SKIP'], 'SKIP')\nresult = Verify('TM.POWER.BUS_VOLTAGE', eq, 0.0, Wait=False, Retries=0, OnFalse=SKIP, OnFailure=CANCEL)\nassert result is True",
         "plan_prompt(['SKIP'], 'SKIP')\nresult = GetTM('TM.ABSENT', OnFalse=CANCEL, OnFailure=SKIP)\nassert result is None",
         oracle='LRM pp41-42 detail OnFalse for comparison outcomes; p43 final OnFailure sentence is an erratum. Different OnFalse/OnFailure action sets are observed through native prompts for false conditions versus real absent-parameter driver failure.')

contract('recheck', ['CONSTANT-ACTION-RECHECK'],
         "plan_prompt(['RECHECK', 'CANCEL'], 'RECHECK')\nplan_prompt(['RECHECK', 'CANCEL'], 'CANCEL')\nresult = Verify('TM.POWER.BUS_VOLTAGE', eq, 0.0, Wait=False, Retries=0, OnFalse=RECHECK|CANCEL)\nassert result is False\nequal(acquisition_waits(), [False, True])",
         "plan_prompt(['RECHECK', 'CANCEL'], 'RECHECK')\nplan_prompt(['RECHECK', 'CANCEL'], 'RECHECK')\nplan_prompt(['RECHECK', 'CANCEL'], 'CANCEL')\nassert Verify('TM.POWER.BUS_VOLTAGE', eq, 0.0, Wait=False, Retries=0, OnFalse=RECHECK|CANCEL) is False\nequal(acquisition_waits(), [False, True, True])",
         "rejects(SyntaxException, lambda: Verify('TM.POWER.BUS_VOLTAGE', eq, 0.0, OnFalse=RECHECK|CANCEL, PromptUser=False))")
