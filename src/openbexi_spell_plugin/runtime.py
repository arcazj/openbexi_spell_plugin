"""Bind the retained bounded SDK to the real DSS test service, without builtins."""
from __future__ import annotations

import json
import math
import operator
import os
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import uuid

from openbexi_spell.api import DriverException, SpellContext, _context


class DssAdapter:
    def __init__(self, url):
        parsed = urlsplit(url)
        if parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', 'localhost', '::1'} or parsed.username or parsed.query or parsed.fragment:
            raise ValueError('The v0.1 DSS development adapter requires a loopback HTTP URL')
        self.url = url.rstrip('/')

    def request(self, route, body=None):
        request = Request(self.url + route, data=None if body is None else json.dumps(body, allow_nan=False).encode(),
                          headers={'Content-Type': 'application/json'})
        try:
            with urlopen(request, timeout=5) as response:
                return json.load(response)
        except (OSError, ValueError) as error:
            certainty = 'UNKNOWN' if body is not None and route.endswith('/commands') else 'NO_EFFECT'
            raise DriverException(str(error), 'DSS_UNAVAILABLE', operation=route, effect_certainty=certainty) from error

    def invoke(self, name, args, modifiers):
        if name == '_Config':
            return {'defaults': {'Verify': {'Retries': 0, 'AdjLimits': False, 'OnFalse': 0}},
                    'max_verbosity': 5, 'retry_budget': 100}
        if name == '_Notify':
            print('[SPELL notification]', args, flush=True)
            return None
        if name == '_PolicyPrompt':
            raise DriverException('Interactive result/failure policy needs a host prompt service', 'UNSUPPORTED_PROMPT')
        if name == '_Abort':
            return None
        if name == 'Display':
            print(str(args[0]), flush=True)
            return True
        if name == 'GetTM':
            if modifiers.get('Wait'):
                raise DriverException('Waiting for fresh telemetry requires the later driver adapter', 'UNSUPPORTED_FRESHNESS_WAIT')
            item = args[0]
            for sample in self.request('/api/v1/telemetry')['samples']:
                if sample['item_id'] == item:
                    if sample['validity'] != 'VALID' or sample['quality'] != 'GOOD':
                        raise DriverException('Telemetry sample is not valid and good', 'INVALID_SAMPLE')
                    value = sample['raw_value' if modifiers.get('ValueFormat') == 'RAW' else 'engineering_value']
                    return value['value']
            raise DriverException('Telemetry item is not in the DSS catalogue', 'UNKNOWN_ITEM')
        if name == 'Verify':
            if modifiers.get('Retries', 0) or modifiers.get('Delay', 0) or modifiers.get('AdjLimits'):
                raise DriverException('v0.1 Verify inspects one current sample; retry/limit adjustment is unavailable', 'UNSUPPORTED_VERIFY_PROFILE')
            item, expected = args
            value = self.invoke('GetTM', (item,), modifiers)
            comparisons = {'EQ': operator.eq, 'NE': operator.ne, 'LT': operator.lt,
                           'LE': operator.le, 'GT': operator.gt, 'GE': operator.ge}
            if modifiers.get('IgnoreCase') and isinstance(value, str) and isinstance(expected, str):
                value, expected = value.casefold(), expected.casefold()
            if modifiers.get('Op', 'EQ') == 'EQ' and type(value) in {int, float} and type(expected) in {int, float}:
                return abs(value-expected) <= modifiers.get('Tolerance', 0)
            return comparisons[modifiers.get('Op', 'EQ')](value, expected)
        if name == 'BuildTC':
            command, values = args
            definitions = self.request('/api/v1/catalog')['commands']
            definition = next((d for d in definitions if d['name'] == command), None)
            if definition is None:
                raise DriverException('Command is not in the DSS catalogue', 'UNKNOWN_COMMAND')
            known = {item['name']: item for item in definition['arguments']}
            if set(values) - set(known):
                raise ValueError('Unknown command argument')
            typed = [{'name': key, 'value': value, 'value_type': known[key]['value_type'], 'value_format': 'ENG'} for key, value in values.items()]
            return {'command_name': command, 'arguments': typed}
        if name == 'Send':
            definitions = self.request('/api/v1/catalog')['commands']
            definition = next((d for d in definitions if d['name'] == args[0]['command_name']), None)
            if definition is None or definition.get('critical'):
                raise DriverException('Critical commands need the later interactive confirmation adapter', 'UNSUPPORTED_CRITICAL_COMMAND')
            state = self.request('/api/v1/state')
            body = {**args[0], 'operation_id': str(uuid.uuid4()), 'expected_epoch': state['epoch'],
                    'expected_revision': state['revision'], 'confirmed': True}
            result = self.request('/api/v1/commands', body)
            if result['outcome'] != 'SUCCEEDED':
                released = any(receipt.get('stage') == 'RELEASE' and receipt.get('outcome') == 'RELEASED'
                               for receipt in result.get('receipts', []))
                certainty = 'UNKNOWN' if result['outcome'] == 'UNCERTAIN' else 'CONFIRMED' if released else 'NO_EFFECT'
                raise DriverException('DSS command did not succeed', result['outcome'], operation='Send',
                                      effect_certainty=certainty)
            return True
        if name == 'WaitFor':
            target = args[0]
            if type(target) not in {int, float} or not math.isfinite(target) or not 0 <= target <= 86400:
                raise DriverException('v0.1 test adapter supports a relative numeric delay', 'UNSUPPORTED_TARGET')
            deadline = time.monotonic() + target
            while time.monotonic() < deadline:
                time.sleep(min(0.05, deadline-time.monotonic()))
            return True
        if name == 'Prompt':
            raise DriverException('Interactive SPELL prompts require the later host adapter', 'UNSUPPORTED_PROMPT')
        raise DriverException('Operation is outside the v0.1 DSS development profile', 'UNSUPPORTED_OPERATION', operation=name)


def activate(dss_url=None):
    url = dss_url or os.environ.get('OPENBEXI_DSS_URL', 'http://127.0.0.1:8085')
    context = SpellContext(DssAdapter(url))
    _context.set(context)
    return context
