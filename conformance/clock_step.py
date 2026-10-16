"""Advance a captured DSS state without masking authority or control failures."""
from dss.engine import DssConflict


def try_step(engine, state, request, stages, accepted, rejected):
    observation = dict(rpc_request=request, before=state, stages=stages)
    try:
        after = engine.control('STEP', state['epoch'], state['revision'], 1)
    except DssConflict:
        current = engine.state()
        # A command receipt may have advanced the revision since observation.
        # A new scenario/epoch or an unchanged revision is a real failure.
        if (current['epoch'] != state['epoch'] or
                current['scenario_id'] != state['scenario_id'] or
                current['revision'] <= state['revision']):
            raise
        rejected.append(dict(observation, observed_after_rejection=current))
        return False
    accepted.append(dict(observation, after=after))
    return True
