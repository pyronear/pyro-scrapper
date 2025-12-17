import signal

import pytest

from continuous_scraper import ContinuousScraper


def test_signal_handler_sets_running_false(monkeypatch):
    # Prevent altering global signal handlers during the test
    monkeypatch.setattr("continuous_scraper.signal.signal", lambda *_, **__: None)

    scraper = ContinuousScraper(interval_seconds=60)
    scraper.running = True

    scraper._signal_handler(signal.SIGINT, None)

    assert scraper.running is False


def test_run_stops_after_single_cycle_without_wait(monkeypatch):
    # Prevent altering global signal handlers during the test
    monkeypatch.setattr("continuous_scraper.signal.signal", lambda *_, **__: None)

    scraper = ContinuousScraper(interval_seconds=60)

    def fake_run_once():
        scraper.scrape_count += 1
        scraper.running = False  # stop after the first cycle
        return True

    monkeypatch.setattr(scraper, "run_spider_once", fake_run_once)

    sleep_calls = []
    monkeypatch.setattr("continuous_scraper.time.sleep", lambda x: sleep_calls.append(x))

    scraper.run()

    assert scraper.scrape_count == 1
    assert sleep_calls == []  # no waiting because we stop immediately


def test_run_waits_between_cycles_and_stops(monkeypatch):
    # Prevent altering global signal handlers during the test
    monkeypatch.setattr("continuous_scraper.signal.signal", lambda *_, **__: None)

    class FakeClock:
        def __init__(self):
            self.t = 0

        def time(self):
            return self.t

        def sleep(self, seconds):
            # Advance virtual time instead of real sleeping
            self.t += seconds

    clock = FakeClock()
    monkeypatch.setattr("continuous_scraper.time.time", clock.time)
    monkeypatch.setattr("continuous_scraper.time.sleep", clock.sleep)

    scraper = ContinuousScraper(interval_seconds=5)

    def fake_run_once():
        # Simulate 1s of work per cycle
        clock.t += 1
        scraper.scrape_count += 1
        if scraper.scrape_count >= 2:
            scraper.running = False  # stop after two cycles
        return True

    monkeypatch.setattr(scraper, "run_spider_once", fake_run_once)

    scraper.run()

    assert scraper.scrape_count == 2
    # Expected timeline: after cycle1 t=1, wait ~4s -> t=5; cycle2 adds 1 -> t=6
    assert clock.time() >= 6
    # Ensure some waiting occurred (more than just the work time)
    assert clock.time() > scraper.scrape_count  # waited beyond the 1s per cycle
