"""Check driver chains, whose repository sources have no upstream port stage."""


def verify_driver_stages(record):
    state={name:row['original_sha256'] for name,row in record['sources'].items()}
    assert record['stages']
    for stage in record['stages']:
        assert stage['recipe'] in record['recipes']
        for name,row in stage['sources'].items():
            assert name in state and state[name]==row['before_sha256'],name
            state[name]=row['after_sha256']
    assert state=={name:row['patched_sha256'] for name,row in record['sources'].items()}
    assert all(record['python_sources'][name]==value for name,value in state.items())
