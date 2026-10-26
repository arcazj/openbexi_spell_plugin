"""Real mTLS rotation with an in-flight RPC at the host freeze boundary."""

import threading
import time
import uuid

import pytest

import test_live_handoff as live

source, setup, ledger = live.source, live.setup, live.ledger


def start_thread(function):
    result, errors = [], []

    def run():
        try:
            result.append(function())
        except BaseException as error:
            errors.append(error)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread, result, errors


@pytest.mark.parametrize("lost_reply", [False, True])
def test_host_drain_waits_for_rpc_and_requires_fresh_one_shot_activation(
    ledger, pki, tmp_path, lost_reply
):
    runtime, epoch_path = live.runtime(ledger, pki, tmp_path)
    guarded = runtime.guarded_route()
    entered, release, drained = (threading.Event() for _ in range(3))
    original = runtime.route.call
    calls, receipts = [], []

    def blocked(request, **kwargs):
        calls.append(kwargs["path"])
        response = original(request, **kwargs)
        if kwargs["path"] == "/v1/worker/check":
            entered.set()
            assert release.wait(3)
            if lost_reply:
                raise TimeoutError("Deliberately lost read response")
        return response

    runtime.route.call = blocked
    active, _, active_errors = start_thread(
        lambda: guarded.call(runtime.request, path="/v1/worker/check", schema="openbexi.worker/2")
    )
    assert entered.wait(3)
    runtime.prepare_path.write_text(runtime.epoch)

    def emit(event, **fields):
        receipts.append(dict(event=event, **fields))
        drained.set()

    parked, _, parked_errors = start_thread(lambda: runtime.checkpoint(emit))
    try:
        assert not drained.wait(0.1)
        assert runtime.active_calls == 1
        release.set()
        active.join(3)
        assert not active.is_alive()
        assert bool(active_errors) == lost_reply
        assert drained.wait(3)
        assert receipts == [
            dict(
                event="native-handoff-agent-drained",
                runtime_epoch=runtime.epoch,
                active_calls=0,
                quiescence_proven=False,
            )
        ]
        for _ in range(3):
            with pytest.raises(ValueError, match="held"):
                guarded.call(
                    runtime.request, path="/v1/worker/command-poll", schema="openbexi.worker/2"
                )
        with pytest.raises(ValueError, match="held"):
            runtime.ensure(runtime.epoch, native=True)
        # Deleting the host marker supplies neither a grant nor thaw permission.
        runtime.prepare_path.unlink()
        time.sleep(0.06)
        assert parked.is_alive() and runtime.draining
        assert calls == ["/v1/worker/check"]
        _, _, _, new_epoch = live.resumed(ledger, pki)
        epoch_path.write_text(new_epoch)
        parked.join(3)
        assert not parked.is_alive() and not parked_errors
        assert runtime.rotations == 1 and not runtime.draining
        assert calls == ["/v1/worker/check", "/v1/worker/handoff-activate"]
        response = (
            guarded.call(runtime.request, path="/v1/worker/check", schema="openbexi.worker/2")
            if not lost_reply
            else None
        )
        if response is not None:
            assert response["checked"]
    finally:
        release.set()
        if parked.is_alive():
            # Unrecognized epochs fail activation and terminate the test thread.
            epoch_path.write_text(str(uuid.uuid4()))
            parked.join(3)


def test_lost_activation_after_drain_cannot_resume_polling_or_retry(ledger, pki, tmp_path):
    runtime, epoch_path = live.runtime(ledger, pki, tmp_path)
    original = runtime.route.call
    calls = []

    def lost(*args, **kwargs):
        calls.append(kwargs["path"])
        original(*args, **kwargs)
        raise TimeoutError("Activation reply lost")

    runtime.route.call = lost
    runtime.prepare_path.write_text(runtime.epoch)
    drained = threading.Event()
    thread, _, errors = start_thread(lambda: runtime.checkpoint(lambda *a, **k: drained.set()))
    try:
        assert drained.wait(2)
        _, _, _, new_epoch = live.resumed(ledger, pki)
        epoch_path.write_text(new_epoch)
        thread.join(3)
        assert len(errors) == 1 and isinstance(errors[0], TimeoutError)
        assert runtime.failed and runtime.draining
        with pytest.raises(ValueError):
            runtime.guarded_route().call(runtime.request, path="/v1/worker/command-poll")
        with pytest.raises(ValueError, match="uncertain"):
            runtime.ensure()
        assert calls == ["/v1/worker/handoff-activate"]
    finally:
        if thread.is_alive():
            epoch_path.write_text(str(uuid.uuid4()))
            thread.join(3)


def test_unknown_prepare_cannot_request_activation_or_authority(ledger, pki, tmp_path):
    runtime, _ = live.runtime(ledger, pki, tmp_path)
    runtime.prepare_path.write_text(str(uuid.uuid4()))
    with pytest.raises(ValueError, match="prepare identity"):
        runtime.checkpoint(lambda *a, **k: pytest.fail("Forged drain acknowledged"))
    assert not runtime.draining and runtime.rotations == 0
