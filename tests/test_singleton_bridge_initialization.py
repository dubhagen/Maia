"""Concurrent cold Bridge callers must share its singleton instance."""

import threading

import pytest

import bridge.bridge as bridge_module
from common.singleton import singleton


SETTINGS = {"voice_to_text": "openai", "text_to_voice": "google", "model": "gpt-4"}


def test_concurrent_cold_bridge_calls_share_one_instance():
    # Bridge construction no longer reads vendor voice settings. The singleton
    # still has to hand every concurrent caller the same instance.
    bridge = singleton(bridge_module.Bridge.__wrapped__)
    instances = []
    errors = []

    def create():
        try:
            instances.append(bridge())
        except BaseException as error:
            errors.append(error)

    threads = [threading.Thread(target=create) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(3)
    assert not any(thread.is_alive() for thread in threads)
    assert not errors
    assert len(instances) == 8
    assert all(item is instances[0] for item in instances)
    assert bridge() is instances[0]


def test_explicit_new_bridge_instances_stay_uncached(monkeypatch):
    monkeypatch.setattr(bridge_module, "conf", lambda: SETTINGS)
    bridge = singleton(bridge_module.Bridge.__wrapped__)
    cached = bridge()
    fresh = bridge.new_instance()
    assert fresh is not cached
    assert bridge() is cached
    assert bridge.__wrapped__ is bridge_module.Bridge.__wrapped__


def test_failed_bridge_initialization_can_retry():
    attempts = {"n": 0}

    @singleton
    class Flaky:
        def __init__(self):
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise RuntimeError("fixture settings failure")

    with pytest.raises(RuntimeError, match="fixture settings failure"):
        Flaky()
    instance = Flaky()
    assert Flaky() is instance


def test_reentrant_construction_does_not_deadlock():
    holder = {}

    @singleton
    class Reentrant:
        def __init__(self):
            if not holder:
                holder["inner"] = True
                Reentrant()

    assert Reentrant() is Reentrant()
