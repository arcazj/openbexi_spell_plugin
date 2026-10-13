"""Four independent dimensions for individually identified telemetry contracts."""
import textwrap

CASES, METADATA = {}, {}
POLICY = 'Wait=False, Retries=0, PromptUser=False, PromptFailure=True, HandleError=False, OnFalse=NOACTION'
GET = 'Wait=False, HandleError=False'
VOLTAGE = 'TM.POWER.BUS_VOLTAGE'


def contract(name, rows, positive, boundary, failure, recovery=None, oracle=None):
    sources = dict(positive=positive, boundary=boundary, failure=failure,
                   recovery=recovery if recovery is not None else failure + '\n' + positive)
    for dimension, source in sources.items():
        key = name + ':' + dimension
        CASES[key] = textwrap.dedent(source).strip() + '\n'
        METADATA[key] = dict(dimension=dimension, contracts=['CMP-LRM244-' + row for row in rows],
                             oracle=oracle or 'LRM 2.4.4 pp36-47; original native methods; fixed catalog voltage 28000 raw / 28.0 engineering; real original-schema RPC and immutable binary source samples; literal comparison expectations and explicit exception/no-update recovery.')


contract('acquire', ['FUNCTION-GETTM', 'EXAMPLE-030', 'SYNTAX-TM-MNEMONIC', 'SECTION-4-2-1-025'],
         f"equal(GetTM('{VOLTAGE}', HandleError=False), 28.0)",
         "equal(GetTM('TM.POWER.SAFE_MODE', HandleError=False), False)\nequal(GetTM('TM.THERMAL.MODE', HandleError=False), 'OFF')",
         "rejects(DriverException, lambda: GetTM('TM.ABSENT', HandleError=False))\nrejects(SyntaxException, lambda: GetTM(42, HandleError=False))")

contract('described', ['SYNTAX-TM-DESCRIBED-MNEMONIC'],
         f"equal(GetTM('T {VOLTAGE} Description with spaces', HandleError=False), 28.0)",
         f"equal(GetTM('t   {VOLTAGE}   ', HandleError=False), 28.0)",
         "rejects(DriverException, lambda: GetTM('T TM.ABSENT description', HandleError=False))")

contract('raw', ['EXAMPLE-033', 'SECTION-4-2-2-026'],
         f"equal(GetTM('{VOLTAGE}', ValueFormat=RAW, HandleError=False), 28000)",
         "equal(GetTM('TM.POWER.SAFE_MODE', ValueFormat=RAW, HandleError=False), False)",
         f"rejects(DriverException, lambda: GetTM('{VOLTAGE}', ValueFormat='INVALID', HandleError=False))")

contract('fresh', ['EXAMPLE-031', 'EXAMPLE-032'],
         f"fixture('feed', value=True)\nequal(GetTM('{VOLTAGE}', Wait=True, Timeout=2, HandleError=False), 28.0)",
         f"equal(GetTM('{VOLTAGE}', Wait=True, Timeout=TIME('+000 00:00:02'), HandleError=False), 28.0)",
         f"fixture('feed', value=False)\nfixture('tick')\nrejects(DriverException, lambda: GetTM('{VOLTAGE}', Wait=True, Timeout=.1, HandleError=False))",
         f"fixture('feed', value=False)\nrejects(DriverException, lambda: GetTM('{VOLTAGE}', Wait=True, Timeout=.1, HandleError=False))\nfixture('feed', value=True)\nequal(GetTM('{VOLTAGE}', Wait=True, Timeout=2, HandleError=False), 28.0)")

contract('timeout-forms', [],
         f"equal(GetTM('{VOLTAGE}', Wait=True, Timeout=2.0, HandleError=False), 28.0)",
         f"equal(GetTM('{VOLTAGE}', Wait=True, Timeout='+000 00:00:02', HandleError=False), 28.0)",
         f"rejects(DriverException, lambda: GetTM('{VOLTAGE}', Wait=True, Timeout=-1, HandleError=False))\nrejects(DriverException, lambda: GetTM('{VOLTAGE}', Wait=True, Timeout=TIME('01-Jan-2020 00:00:00'), HandleError=False))")

acquire_item = f"item = GetTM('{VOLTAGE}', Extended=True, HandleError=False)\n"
contract('extended', ['MODIFIER-EXTENDED', 'TYPE-TELEMETRYITEM', 'EXAMPLE-034', 'SECTION-4-2-3-027'],
         acquire_item + "equal(item.name(), 'TM.POWER.BUS_VOLTAGE')\nequal(item.raw(), 28000)\nequal(item.eng(), 28.0)\nassert item.status()",
         "flag = GetTM('TM.POWER.SAFE_MODE', Extended=True, HandleError=False)\nequal(flag.raw(), False)\nequal(flag.eng(), False)",
         "rejects(DriverException, lambda: GetTM('TM.ABSENT', Extended=True, HandleError=False))")

for method, expected in [('NAME', repr(VOLTAGE)), ('DESCRIPTION', repr('Synthetic DC bus voltage')),
                         ('FULLNAME', repr(VOLTAGE + ': Synthetic DC bus voltage')),
                         ('RAW', '28000'), ('ENG', '28.0'), ('STATUS', 'True')]:
    spelling = 'fullName' if method == 'FULLNAME' else method.lower()
    read = f'equal(item.{spelling}(), {expected})'
    contract('item-' + method.lower(), ['METHOD-TELEMETRY-ITEM-' + method],
             acquire_item + read,
             acquire_item + f"fixture('tick', ticks=3)\n{read}",
             acquire_item + "rejects(DriverException, lambda: item.refresh({'Unqualified': True}))\n" + read)

contract('item-time', ['METHOD-TELEMETRY-ITEM-TIME'],
         acquire_item + "stamp = item.time()\nassert isinstance(stamp, TIME) and not stamp.isRel()\nassert abs(stamp.abs() - time.time()) < 5",
         acquire_item + "stamp = str(item.time())\nfixture('tick')\nequal(str(item.time()), stamp)",
         acquire_item + "stamp = str(item.time())\nrejects(DriverException, lambda: item.refresh({'Unqualified': True}))\nequal(str(item.time()), stamp)")

contract('item-refresh', ['METHOD-TELEMETRY-ITEM-REFRESH'],
         "fixture('feed', value=False)\nitem = GetTM('TM.CORE.TICK', Extended=True, HandleError=False)\nold = item.raw()\nfixture('tick', ticks=3)\nequal(item.raw(), old)\nitem.refresh(Wait=False)\nequal(item.raw(), old + 3)",
         acquire_item + "item.refresh(Wait=True, Timeout=TIME('+000 00:00:02'))\nequal(item.raw(), 28000)",
         acquire_item + "rejects(DriverException, lambda: item.refresh({'Unqualified': True}))\nequal(item.raw(), 28000)")

operators = {
    'EQ': ('eq', '28.0', '28.0', '27.0'),
    'NEQ': ('neq', '27.0', '28.0001', '28.0'),
    'GE': ('ge', '27.0', '28.0', '29.0'),
    'GT': ('gt', '27.0', '27.9999', '28.0'),
    'LE': ('le', '29.0', '28.0', '27.0'),
    'LT': ('lt', '29.0', '28.0001', '28.0'),
    'BW': ('bw', '27.0, 29.0', '28.0, 28.0', '29.0, 30.0'),
    'NBW': ('nbw', '29.0, 30.0', '28.0001, 30.0', '27.0, 29.0'),
}
for row, (operator, good, edge, bad) in operators.items():
    statement = lambda values: f"Verify('{VOLTAGE}', {operator}, {values}, Tolerance=0, {POLICY})"
    contract('operator-' + operator, ['OPERATOR-VERIFY-' + row],
             'assert ' + statement(good), 'assert ' + statement(edge) + '\nassert not ' + statement(bad),
             f"rejects(SyntaxException, lambda: Verify('{VOLTAGE}', {operator}, {good}, 123, {POLICY}))")

contract('single', ['EXAMPLE-035', 'SYNTAX-VERIFY-CONDITION', 'SECTION-4-3-1-031'],
         f"assert Verify(['{VOLTAGE}', eq, 28.0], {POLICY})",
         f"assert not Verify(['{VOLTAGE}', eq, 0.0], {POLICY})",
         f"rejects(SyntaxException, lambda: Verify(['{VOLTAGE}', 'invalid', 28.0], {POLICY}))")

contract('verify-raw', ['EXAMPLE-036'],
         f"assert Verify(['{VOLTAGE}', eq, 28000], ValueFormat=RAW, {POLICY})",
         f"assert not Verify(['{VOLTAGE}', eq, 28.0], ValueFormat=RAW, {POLICY})",
         f"rejects(DriverException, lambda: Verify(['{VOLTAGE}', eq, 28.0], ValueFormat='invalid', {POLICY}))")

contract('tolerance', ['EXAMPLE-038', 'SECTION-4-3-3-033'],
         f"assert Verify('{VOLTAGE}', eq, 28.1, Tolerance=.2, {POLICY})",
         f"assert Verify('{VOLTAGE}', eq, 27.9, Tolerance=.1, {POLICY})\nassert not Verify('{VOLTAGE}', eq, 27.8, Tolerance=.1, {POLICY})",
         f"rejects(DriverException, lambda: Verify('{VOLTAGE}', eq, 28.0, Tolerance=-.1, {POLICY}))")

contract('ignore-case', ['MODIFIER-IGNORECASE', 'EXAMPLE-046', 'SECTION-4-3-8-038'],
         f"assert Verify('TM.THERMAL.MODE', eq, 'off', IgnoreCase=True, {POLICY})",
         f"assert Verify('TM.THERMAL.MODE', neq, 'oFf', IgnoreCase=False, {POLICY})\nassert not Verify('TM.THERMAL.MODE', neq, 'oFf', IgnoreCase=True, {POLICY})",
         f"rejects(DriverException, lambda: Verify('TM.THERMAL.MODE', lt, 'OFF', IgnoreCase=True, {POLICY}))")

contract('result', ['TYPE-VERIFYRESULT', 'EXAMPLE-039', 'EXAMPLE-040', 'EXAMPLE-041', 'SECTION-4-3-4-034'],
         f"result = Verify([['{VOLTAGE}', eq, 28.0], ['TM.THERMAL.MODE', eq, 'OFF']], {POLICY})\nassert result\nequal(result.keys(), ['0: {VOLTAGE}', '1: TM.THERMAL.MODE'])\nequal([result[k] for k in result.keys()], [True, True])",
         f"result = Verify([['{VOLTAGE}', eq, 28.0], ['TM.THERMAL.MODE', eq, 'wrong']], {POLICY})\nassert not result\nequal([result[k] for k in result.keys()], [True, False])",
         f"result = Verify(['{VOLTAGE}', eq, 28.0], {POLICY})\nrejects(KeyError, lambda: result['unknown condition'])")

contract('alternatives', ['EXAMPLE-050', 'SECTION-4-3-11-041'],
         f"assert Verify('{VOLTAGE}', eq, [0.0, 28.0], {POLICY})",
         f"assert not Verify('{VOLTAGE}', eq, [], {POLICY})\nassert not Verify('{VOLTAGE}', eq, [0.0, 1.0], {POLICY})",
         f"rejects(DriverException, lambda: Verify('{VOLTAGE}', bw, [27.0], 29.0, {POLICY}))")

contract('item-comparison', ['EXAMPLE-051', 'EXAMPLE-053', 'EXAMPLE-054', 'SECTION-4-3-12-042'],
         "one = GetTM('TMparam1', Extended=True, HandleError=False)\ntwo = GetTM('TMparam2', Extended=True, HandleError=False)\n" + f"assert Verify([one, eq, two], {POLICY})\nassert Verify(['TMparam1', eq, [0.0, two]], {POLICY})",
         "one = GetTM('TMparam1', Extended=True, HandleError=False)\nthree = GetTM('TMparam3', Extended=True, HandleError=False)\n" + f"assert not Verify([one, eq, three], {POLICY})",
         f"rejects(SyntaxException, lambda: Verify([42, eq, 28.0], {POLICY}))")

contract('literal-name', ['EXAMPLE-052'],
         f"assert not Verify('TMparam1', eq, 'TMparam2', {POLICY})",
         f"assert Verify('TM.THERMAL.MODE', eq, 'OFF', {POLICY})",
         f"rejects(SyntaxException, lambda: Verify([42, eq, 'TMparam2'], {POLICY}))")

for operator, good, edge in [('AND', '[eq, eq]', '[eq, neq]'), ('OR', '[eq, neq]', '[neq, neq]')]:
    expression = lambda ops: f"{operator}(['{VOLTAGE}', {ops}[0], 28.0], ['TM.THERMAL.MODE', {ops}[1], 'OFF'])"
    contract('expression-' + operator.lower(), ['FUNCTION-CANDIDATE-' + operator],
             f"assert Verify({expression(good)}, {POLICY})",
             f"assert not Verify({expression(edge)}, {POLICY})",
             f"rejects(SyntaxException, lambda: {operator}())")

contract('nested-expression', ['TYPE-TELEMETRY-EXPRESSION', 'SYNTAX-VERIFY-BOOLEAN-TREE', 'EXAMPLE-055', 'EXAMPLE-056', 'SECTION-4-3-13-043'],
         f"assert Verify(AND(['{VOLTAGE}', eq, 28.0], OR(['TM.THERMAL.MODE', eq, 'OFF'], ['TM.THERMAL.MODE', eq, 'wrong'])), {POLICY})",
         f"assert not Verify(OR(['{VOLTAGE}', eq, 0.0], AND(['TM.THERMAL.MODE', eq, 'OFF'], ['TM.THERMAL.MODE', eq, 'wrong'])), {POLICY})",
         f"rejects(SyntaxException, lambda: Verify(AND(['{VOLTAGE}', 'invalid', 28.0]), {POLICY}))")

contract('mixed-modifiers', ['SYNTAX-VERIFY-CONDITION-LIST', 'EXAMPLE-047', 'EXAMPLE-048', 'EXAMPLE-049', 'SECTION-4-3-10-040'],
         f"assert Verify([['TMparam1', eq, 28.0], ['TMparam2', eq, 28000, {{ValueFormat: RAW}}], ['TMparam3', lt, 10.5]], {POLICY})",
         f"result = Verify([['TMparam1', eq, 28000], ['TMparam2', eq, 28.0, {{ValueFormat: ENG}}]], ValueFormat=RAW, {POLICY})\nassert result",
         f"rejects(DriverException, lambda: Verify([['TMparam1', eq, 28.0], ['TMparam2', eq, 28.0, {{ValueFormat: 'invalid'}}]], {POLICY}))")

retry_policy = POLICY.replace('Retries=0', 'Retries=2')
contract('retries', ['MODIFIER-RETRIES', 'EXAMPLE-044', 'SECTION-4-3-6-036'],
         f"assert not Verify('{VOLTAGE}', eq, 0.0, Timeout=2, {retry_policy})\nequal(acquisition_waits(), [False, True, True])\nassert all('response' in row and 'error' not in row for row in acquisitions())",
         f"assert not Verify('{VOLTAGE}', eq, 0.0, Timeout=2, {POLICY})\nequal(acquisition_waits(), [False])",
         f"rejects(DriverException, lambda: Verify('{VOLTAGE}', eq, 28.0, {POLICY.replace('Retries=0', 'Retries=-1')}))\nequal(acquisitions(), [])")

fresh_policy = POLICY.replace('Wait=False', 'Wait=True')
contract('verify-fresh', ['EXAMPLE-037', 'SECTION-4-3-2-032'],
         f"assert Verify('{VOLTAGE}', eq, 28.0, Timeout=2, {fresh_policy})\nequal(acquisition_waits(), [True])",
         f"assert Verify('{VOLTAGE}', eq, 28.0, Timeout='+000 00:00:02', {fresh_policy})",
         f"fixture('feed', value=False)\nrejects(DriverException, lambda: Verify('{VOLTAGE}', eq, 28.0, Timeout=.1, {fresh_policy}))",
         f"fixture('feed', value=False)\nrejects(DriverException, lambda: Verify('{VOLTAGE}', eq, 28.0, Timeout=.1, {fresh_policy}))\nfixture('feed', value=True)\nassert Verify('{VOLTAGE}', eq, 28.0, Timeout=2, {fresh_policy})")

contract('verify-delay', ['EXAMPLE-045', 'SECTION-4-3-7-037'],
         f"began = time.monotonic()\nassert Verify('{VOLTAGE}', eq, 28.0, Delay=.3, {POLICY})\nassert time.monotonic() - began >= .3",
         f"assert Verify('{VOLTAGE}', eq, 28.0, Delay=TIME('+000 00:00:00.1'), {POLICY})\nassert Verify('{VOLTAGE}', eq, 28.0, Delay=0, {POLICY})",
         f"rejects(SpellException, lambda: Verify('{VOLTAGE}', eq, 28.0, Delay='invalid', {POLICY}))")
