"""The expectations below come from LRM 2.4.4 and fixed DSS initial conditions."""
CASES = {
    'gettm.eng': "equal(GetTM('TM.POWER.BUS_VOLTAGE', Wait=False, PromptUser=False, OnFailure=ABORT), 28.0)",
    'gettm.raw': "equal(GetTM('TM.POWER.BUS_VOLTAGE', ValueFormat=RAW, Wait=False, PromptUser=False, OnFailure=ABORT), 28000)",
    'gettm.described': "equal(GetTM('T TM.POWER.BUS_VOLTAGE Bus voltage', Wait=False, PromptUser=False, OnFailure=ABORT), 28.0)",
    'gettm.item': "item = GetTM('TM.POWER.BUS_VOLTAGE', Extended=True, Wait=False, PromptUser=False, OnFailure=ABORT)\nequal(item.name(), 'TM.POWER.BUS_VOLTAGE')\nequal(item.raw(), 28000)\nequal(item.eng(), 28.0)\nequal(item.status(), True)",
    'verify.equal': "result = Verify('TM.POWER.BUS_VOLTAGE', eq, 28.0, Wait=False, Retries=0, PromptUser=False, OnFalse=NOACTION, OnFailure=ABORT)\nassert result, str(result)",
    'verify.false': "result = Verify('TM.POWER.BUS_VOLTAGE', eq, 27.0, Wait=False, Retries=0, PromptUser=False, OnFalse=NOACTION, OnFailure=ABORT)\nassert not result, str(result)",
    'gettm.missing': "assert rejects(SpellException, lambda: GetTM('TM.DOES.NOT.EXIST', Wait=False, PromptUser=False, OnFailure=ABORT))\nequal(GetTM('TM.POWER.BUS_VOLTAGE', Wait=False, PromptUser=False, OnFailure=ABORT), 28.0)",
    'gettm.timeout': "fixture('feed', value=False)\nfixture('tick')\nassert rejects(SpellException, lambda: GetTM('TM.POWER.BUS_VOLTAGE', Wait=True, Timeout=.15, PromptUser=False, OnFailure=ABORT))\nfixture('feed', value=True)\nequal(GetTM('TM.POWER.BUS_VOLTAGE', Wait=True, Timeout=2, PromptUser=False, OnFailure=ABORT), 28.0)",
    'verify.retries': "assert not Verify('TM.POWER.BUS_VOLTAGE', eq, 0.0, Wait=False, Retries=2, Timeout=2, PromptUser=False, OnFalse=NOACTION, OnFailure=ABORT)\nseen = fixture('observe')['rpc']\nrefreshes = [r for r in seen if r['check'] == 'verify.retries' and r['path'].endswith('/RefreshItem')]\nequal(len(refreshes), 3)",
    'verify.and': "assert Verify(AND(['TM.POWER.BUS_VOLTAGE', eq, 28.0], ['TM.THERMAL.MODE', eq, 'NOMINAL']), Wait=False, Retries=0, PromptUser=False, OnFalse=NOACTION, OnFailure=ABORT)",
    'verify.boundary': "assert Verify('TM.POWER.BUS_VOLTAGE', bw, 28.0, 28.0, Wait=False, Retries=0, PromptUser=False, OnFalse=NOACTION, OnFailure=ABORT)",
    'verify.invalid': "assert rejects(SpellException, lambda: Verify('TM.POWER.BUS_VOLTAGE', 'not-an-operator', 28.0, Wait=False, Retries=0, PromptUser=False, OnFalse=NOACTION, OnFailure=ABORT))",
}

# Failure policy is explicit so a language exception remains an assertion
# outcome; later interactive policy cases use their own traced procedure.
CASES = {name: source.replace('PromptUser=False,', 'PromptUser=False, PromptFailure=True, HandleError=False,')
         for name, source in CASES.items()}
CASES['verify.and'] = CASES['verify.and'].replace("'NOMINAL'", "'OFF'")

from obs_qualification_cases import CASES as QUALIFICATION_CASES, METADATA
import obs_policy_cases
CASES.update(QUALIFICATION_CASES)
CASES['probe.nested-wait'] = """fixture('feed', value=False)
fixture('tick')
began = time.monotonic()
rejects(DriverException, lambda: Verify(AND(OR(['TM.POWER.BUS_VOLTAGE', eq, 28.0])), Wait=True, Timeout=.8, Retries=0, PromptUser=False, PromptFailure=True, HandleError=False, OnFalse=NOACTION))
assert time.monotonic() - began >= .8
fixture('feed', value=True)
"""
