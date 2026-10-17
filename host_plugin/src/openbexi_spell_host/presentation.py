"""Translate native notifications into the optional neutral procedure-view protocol."""
from datetime import datetime, timezone


def presentation(message):
    if message.get('type') != 'event':
        return None
    event, body = message.get('event'), message.get('body', {})
    common = {'procedureId': body.get('ProcId', body.get('procedureId', '')),
              'rootProcedureId': body.get('rootProcedureId', '')}
    if event == 'spell/source':
        result = dict(common, kind='source', source=body['source'], text=body['text'],
                      offset=body['offset'], complete=body['complete'])
    elif event == 'spell/notification':
        if 'source' not in body or 'line' not in body:
            return None
        timestamp = body.get('ItemTime') or body.get('Time', '')
        if str(timestamp).isdigit() and len(str(timestamp)) >= 14:
            try:
                timestamp = datetime.fromtimestamp(int(timestamp) / 1_000_000, timezone.utc).isoformat(timespec='milliseconds')
            except (ValueError, OverflowError, OSError):
                pass
        result = dict(common, kind='line', source=body['source'], line=body['line'],
            current=body.get('DataType') == 'CURRENT_LINE', timestamp=timestamp,
            item=body.get('ItemName', ''), value=body.get('ItemValue', ''),
            status=body.get('ItemStatus', ''), details=body)
    elif event == 'spell/status':
        result = dict(common, kind='status', status=body.get('ExecutorStatus', ''))
    elif event == 'spell/prompt':
        prompt_type = int(body.get('DataType', 0))
        labels = body.get('OptionValues') or body.get('ExpectedValues')
        choices = [{'label': label, 'value': str(index)} for index, label in enumerate(labels.split('\4'))] if labels else []
        result = dict(common, kind='prompt', promptId=body['promptId'], text=body.get('Text', ''),
            choices=choices, inputType=('password' if prompt_type & 4096 else 'number' if prompt_type & 16
                                      else 'date' if prompt_type & 1024 else 'text'))
        if body.get('DefaultProvided') == 'True' and not prompt_type & 4096:
            result['defaultHint'] = body.get('Default', '')
    elif event == 'spell/promptClosed':
        result = dict(common, kind='promptClosed', promptId=body['promptId'])
    elif event == 'openbexi/promptReminder':
        result = dict(common, kind='reminder', promptId=body.get('promptId', ''))
    else:
        return None
    return {'type': 'event', 'event': 'openbexi/procedure', 'body': result}
