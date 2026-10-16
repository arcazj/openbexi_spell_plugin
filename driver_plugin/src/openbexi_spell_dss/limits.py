"""Atomic, epoch-scoped limit definitions carried by the original RPC schema.

The versioned Any payload extends the GENERIC driver profile; the original flat
four-threshold wire format remains supported. No protobuf methods are invented.
"""
# SPDX-License-Identifier: GPL-3.0-or-later
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

from google.protobuf.wrappers_pb2 import BoolValue
from . import limit_definitions as definitions
from .limit_algorithm import Algorithm
from .codec import pack, unpack
from .journal import canonical
from .stubs import SPELLDriver_pb2 as p

PROFILE = 'OPENBEXI_LIMITS_1'
CONTROL = 'LimitProfile'
SEVERITY = {'Ignore': 0, 'Nominal': 0, 'Warning': 1, 'Error': 2}


class Limits:
    def __init__(self, dispatcher, acquire):
        self.dispatcher = dispatcher
        self.ground = dispatcher.ground
        self.database = dispatcher.transport.database
        self.acquire = acquire

    def collection(self, state, name):
        current = state.get('limit_definitions', {}).get(name)
        if current is not None:return deepcopy(current)
        old = state['limits'].get(name)
        return {'GENERIC': definitions.definition(old)} if old else {}

    def active(self, row):
        return row['Active'] and Algorithm(row.get('Algorithm', ''), self.database.item).evaluate(
            lambda name: self.reading(name)[0])

    def reading(self, name):
        row = self.acquire(name)
        if not row.validity:raise ValueError('Cannot evaluate limits on invalid or stale telemetry')
        value = unpack(row.engValue)
        return value, row.timestamp

    def validate_types(self, name, rows):
        kind = self.database.item(name)['raw_type']
        for row in rows.values():
            if (row['Type'] == 'STATUS' and kind != 'STRING'
                    or row['Type'] != 'STATUS' and kind not in ('INT64', 'UINT64')):
                raise ValueError('Limit type differs from the telemetry catalog type')
            Algorithm(row.get('Algorithm', ''), self.database.item)

    def updated(self, state, name, settings):
        allowed = {'Definition', 'Limits', 'Select', 'Type'}
        if type(settings) is not dict or set(settings)-allowed:
            raise ValueError('Invalid limit update settings')
        rows = definitions.modify(self.collection(state, name),
            updates=settings.get('Limits'), patch=settings.get('Definition'),
            selector=settings.get('Select', 'ACTIVE'), requested_type=settings.get('Type'), applies=self.active)
        self.validate_types(name, rows)
        return rows

    def publish(self, state, name, rows):
        all_rows = state.setdefault('limit_definitions', {})
        if name not in all_rows and len(all_rows) >= 128:raise ValueError('Limit parameter capacity exceeded')
        old = self.collection(state, name)
        history = state.setdefault('limit_history', {}).setdefault(name, {})
        for key in list(history):
            if key not in rows or old.get(key) != rows[key]:del history[key]
        all_rows[name] = rows
        # Keep the original flat GENERIC record for old wire clients/evidence.
        generic = rows.get('GENERIC')
        if generic and generic['Type'] == 'HARDSOFT':
            state['limits'][name] = {key: generic[key] for key in definitions.THRESHOLDS}
        else:state['limits'].pop(name, None)

    def adjusted(self, state, settings):
        if type(settings) is not dict or set(settings) != {'Conditions'}:
            raise ValueError('Invalid limit adjustment request')
        conditions = settings['Conditions']
        if type(conditions) is not list or not 1 <= len(conditions) <= 128:
            raise ValueError('Expected one to 128 adjustment conditions')
        seen = set()
        for condition in conditions:
            if type(condition) is not dict or set(condition) != {'Parameter', 'Value', 'Tolerance', 'Select'}:
                raise ValueError('Invalid limit adjustment condition')
            name, value = condition['Parameter'], condition['Value']
            self.database.item(name)
            if name in seen:raise ValueError('Duplicate adjustment parameter')
            seen.add(name)
            rows = self.collection(state, name)
            keys = definitions.selected(rows, condition['Select'], self.active)
            if not rows and condition['Select'] in ('ACTIVE', 'ALL'):keys = ['GENERIC']
            if not keys:raise ValueError('No selected limit definitions to adjust')
            for key in keys:
                old = rows.get(key)
                if type(value) is str or type(value) is list:
                    values = [value] if type(value) is str else value
                    if not values:raise ValueError('Expected nominal status values')
                    # Validate exact strings and duplicates before touching the old lists.
                    fresh = definitions.definition({'Nominal': values})
                    if old is not None and old['Type'] != 'STATUS':
                        raise ValueError('Status adjustment requires a STATUS definition')
                    patch = {status: list((old or fresh)[status]) for status in definitions.STATUSES}
                    for status in ('Warning', 'Error', 'Ignore'):
                        patch[status] = [item for item in patch[status] if item not in values]
                    patch['Nominal'] += [item for item in values if item not in patch['Nominal']]
                else:
                    if old is not None and old['Type'] != 'HARDSOFT':
                        raise ValueError('Numeric adjustment requires a HARDSOFT definition')
                    patch = {'Midpoint': definitions.number(value), 'Tolerance': definitions.number(condition['Tolerance'])}
                rows[key] = definitions.definition(patch, old)
            self.validate_types(name, rows)
            self.publish(state, name, rows)

    def change(self, mutation, check):
        def validate():
            state = self.ground.state()
            mutation(state)  # Complete preflight before effect intent.
            if len(canonical(state)) > 1024*1024:
                raise ValueError('Simulator ground service capacity exceeded')
        def action():
            check()
            self.ground.update(mutation)  # Validate again and commit one transaction.
            return BoolValue(value=True)
        action.validate = validate
        return action

    def file(self, uri):
        if type(uri) is not str or re.fullmatch(r'limits://[A-Za-z0-9_-]{1,64}', uri) is None:
            raise ValueError('Expected a registered limits:// file')
        path = Path(__file__).with_name('limit_files')/(uri[9:]+'.json')
        try:raw = path.read_bytes()
        except OSError as error:raise ValueError('Unknown registered limit file') from error
        if len(raw) > 65536:raise ValueError('Limit file exceeds bounds')
        def pairs(items):
            result = {}
            for key, value in items:
                if key in result:raise ValueError('Duplicate limit file key')
                result[key] = value
            return result
        try:document = json.loads(raw, object_pairs_hook=pairs)
        except (ValueError, RecursionError) as error:raise ValueError('Invalid limit file') from error
        if (type(document) is not dict or set(document) != {'schema', 'parameters'}
                or document['schema'] != PROFILE or type(document['parameters']) is not dict
                or not 1 <= len(document['parameters']) <= 128):
            raise ValueError('Invalid limit file schema')
        parameters = {}
        for name, rows in document['parameters'].items():
            self.database.item(name)
            parameters[name] = definitions.modify({}, updates=rows)
            self.validate_types(name, parameters[name])
        return parameters, hashlib.sha256(raw).hexdigest()

    def prepare(self, method, request, check):
        if method == 'RestoreNormalLimits':
            if request.type_url and unpack(request):raise ValueError('Unsupported restore-limits modifier')
            def restore(state):
                state['limits'].clear()
                for key in ('limit_definitions', 'limit_history', 'limit_enabled', 'limit_files'):
                    state.pop(key, None)
            return self.change(restore, check)
        name = request.item.mnemonic
        if method == 'SetLimits':
            payload = unpack(request.set.limitset)
            if type(payload) is not dict:raise ValueError('Limit payload must be a dictionary')
            if CONTROL not in payload:
                if set(payload) != set(definitions.THRESHOLDS):
                    raise ValueError('Legacy limit requests require four thresholds')
                self.database.item(name)
                row = definitions.definition(payload)
                self.validate_types(name, {'GENERIC': row})
                return self.change(lambda state: self.publish(state, name, {'GENERIC': row}), check)
            if payload.get(CONTROL) != PROFILE or set(payload)-{CONTROL, 'Operation', 'Settings'}:
                raise ValueError('Unknown limit payload profile')
            operation, settings = payload.get('Operation'), payload.get('Settings')
            if operation == 'Adjust':
                if name:raise ValueError('Adjustments identify parameters in their conditions')
                return self.change(lambda state: self.adjusted(state, settings), check)
            if operation == 'Load':
                if name or type(settings) is not dict or set(settings) != {'File'}:
                    raise ValueError('Invalid limit file request')
                parameters, digest = self.file(settings['File'])
                def load(state):
                    for parameter, rows in parameters.items():self.publish(state, parameter, deepcopy(rows))
                    files = state.setdefault('limit_files', {})
                    if settings['File'] not in files and len(files) >= 128:
                        raise ValueError('Limit file receipt capacity exceeded')
                    files[settings['File']] = digest
                return self.change(load, check)
            self.database.item(name)
            if operation == 'Modify':
                def modify(state):self.publish(state, name, self.updated(state, name, settings))
                return self.change(modify, check)
            if operation == 'Alarm':
                if type(settings) is not dict or set(settings) != {'Enabled'} or type(settings['Enabled']) is not bool:
                    raise ValueError('Alarm enable flag must be Boolean')
                def enable(state):
                    enabled = state.setdefault('limit_enabled', {})
                    if name not in enabled and len(enabled) >= 128:raise ValueError('Alarm parameter capacity exceeded')
                    enabled[name] = settings['Enabled']
                    state.setdefault('limit_history', {}).pop(name, None)
                return self.change(enable, check)
            raise ValueError('Unknown limit operation')
        self.database.item(name)
        settings = unpack(request.config) if request.config.type_url else {}
        if type(settings) is not dict:raise ValueError('Invalid limit query settings')
        if method == 'GetLimits':
            if not settings:return lambda: p.LimitSet(limitset=pack(self.ground.state()['limits'].get(name, {})))
            if settings.get(CONTROL) != PROFILE or set(settings)-{CONTROL, 'Select', 'Value'}:
                raise ValueError('Unknown limit query profile')
            choice = settings.get('Select', 'ALL')
            if 'Value' in settings and choice in ('ALL', 'ACTIVE'):
                raise ValueError('Value requires a specific limit identifier')
            def get():
                rows = self.collection(self.ground.state(), name)
                if not rows:raise ValueError('No limit definitions are configured for '+name)
                keys = definitions.selected(rows, choice, self.active)
                result = {key: rows[key] for key in keys}
                if choice not in ('ALL', 'ACTIVE'):
                    result = rows[choice]
                    if 'Value' in settings:result = definitions.property_value(result, settings['Value'])
                return p.LimitSet(limitset=pack(result))
            return get
        if method != 'IsAlarmed' or settings:raise ValueError('Unsupported limit query')
        def alarm():
            def evaluate(state):
                if not state.get('limit_enabled', {}).get(name, True):return False
                rows = self.collection(state, name)
                if not rows:return False
                keys = definitions.selected(rows, 'ACTIVE', self.active)
                history = state.setdefault('limit_history', {}).setdefault(name, {})
                for key in list(history):
                    if key not in keys:del history[key]
                if not keys:return False
                value, timestamp = self.reading(name)
                stamp = hashlib.sha256(pack([timestamp, value]).SerializeToString(deterministic=True)).hexdigest()
                alarmed = False
                for key in keys:
                    previous = history.get(key, {})
                    if previous.get('sample') != stamp:
                        severity = definitions.classify(rows[key], value, previous.get('value'))
                        violations = min(1024, previous.get('violations', 0)+1) if SEVERITY[severity] else 0
                        triggered = SEVERITY[severity] > 0 and violations >= max(1, rows[key].get('Hysteresis', 0))
                        previous = dict(sample=stamp, value=value, violations=violations,
                                        severity=severity, alarmed=triggered)
                        history[key] = previous
                    alarmed = alarmed or previous['alarmed']
                return alarmed
            return BoolValue(value=self.ground.update(evaluate))
        return alarm
