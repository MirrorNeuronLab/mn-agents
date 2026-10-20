import signal
import threading

import pytest

from mn_prototype_supervised_service_agent import ServiceContext, SupervisedServiceSpec, create_agent


@pytest.mark.parametrize("enabled,expected", [(False, ["health", "cycle", "cycle", "cycle"]), (True, ["health", "cycle", "health", "cycle", "health", "cycle"])])
def test_cycle_health_is_explicit_and_preserves_default_order(enabled, expected):
    calls = []
    run = create_agent(SupervisedServiceSpec(cycle=lambda c: calls.append("cycle"), health=lambda c: calls.append("health"), health_each_cycle=enabled, max_cycles=3, restore_signals=True))
    assert run()["cycles_completed"] == 3
    assert calls == expected


def test_failed_periodic_health_stops_work_and_always_cleans_up():
    context = ServiceContext()
    calls = []

    def health(c):
        calls.append("health")
        if c.cycles_completed:
            raise RuntimeError("source became unavailable")

    run = create_agent(SupervisedServiceSpec(cycle=lambda c: calls.append("cycle"), health=health, on_stop=lambda c: calls.append("stop"), health_each_cycle=True, max_cycles=3, restore_signals=True))
    with pytest.raises(RuntimeError, match="unavailable"):
        run(context=context)
    assert context.cycles_completed == 1
    assert calls == ["health", "cycle", "health", "stop"]


@pytest.mark.parametrize("where", ["success", "startup", "work", "cleanup"])
def test_signal_handlers_restore_after_every_exit(where):
    previous = {number: signal.getsignal(number) for number in (signal.SIGINT, signal.SIGTERM)}

    def callback(name):
        def invoke(context):
            if where == name:
                raise RuntimeError(name)
        return invoke

    run = create_agent(SupervisedServiceSpec(cycle=callback("work"), on_start=callback("startup"), on_stop=callback("cleanup"), max_cycles=1, restore_signals=True))
    if where == "success":
        run()
    else:
        with pytest.raises(RuntimeError):
            run()
    assert {number: signal.getsignal(number) for number in previous} == previous


def test_external_stop_prevents_next_health_and_cycle():
    context = ServiceContext()
    calls = []

    def cycle(c):
        calls.append("cycle")
        c.stop_event.set()

    run = create_agent(SupervisedServiceSpec(cycle=cycle, health=lambda c: calls.append("health"), health_each_cycle=True, restore_signals=True))
    assert run(context=context)["cycles_completed"] == 1
    assert calls == ["health", "cycle"]


def test_non_main_thread_never_installs_or_restores_signals(monkeypatch):
    calls = []
    monkeypatch.setattr(signal, "signal", lambda *args: pytest.fail("signal mutation outside main thread"))
    worker = threading.Thread(target=lambda: calls.append(create_agent(SupervisedServiceSpec(cycle=lambda c: None, max_cycles=1, restore_signals=True))()))
    worker.start()
    worker.join(timeout=5)
    assert not worker.is_alive()
    assert calls[0]["cycles_completed"] == 1


@pytest.mark.parametrize("options", [{"health_each_cycle": True}, {"health_each_cycle": 1}, {"restore_signals": 1}])
def test_invalid_health_options_fail_before_start(options):
    with pytest.raises(ValueError):
        create_agent(SupervisedServiceSpec(serve=lambda c: None, **options))
