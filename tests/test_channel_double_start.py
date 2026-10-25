"""Starting a channel that is already running must not leave two of them.

Saving config restarts a channel, and starting it again used to interleave
with that restart. The second start overwrote the registry entry while the
first instance kept running, so one message could be answered twice.
"""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class FakeChannel:
    def __init__(self, name):
        self.name = name
        self.cloud_mode = False
        self.running = False
        self.startups = 0

    def startup(self):
        self.startups += 1
        self.running = True

    def stop(self):
        self.running = False


class ChannelStartTest(unittest.TestCase):

    def setUp(self):
        import app
        self.app = app
        self.created = []

        def create_channel(name):
            ch = FakeChannel(name)
            self.created.append(ch)
            return ch

        patcher = patch.object(app.channel_factory, "create_channel", side_effect=create_channel)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.mgr = app.ChannelManager()

    def _join_threads(self):
        for th in list(self.mgr._threads.values()):
            th.join(timeout=5)

    def test_starting_twice_leaves_a_single_live_channel(self):
        self.mgr.start(["terminal"])
        self._join_threads()
        first = self.mgr.get_channel("terminal")

        self.mgr.start(["terminal"])
        self._join_threads()
        second = self.mgr.get_channel("terminal")

        self.assertIsNot(first, second, "a fresh instance should replace the old one")
        self.assertFalse(first.running, "the superseded instance must be stopped, not orphaned")
        self.assertTrue(second.running)
        self.assertIs(self.mgr.get_channel("terminal"), second)

    def test_restart_after_a_start_keeps_one_channel(self):
        # Config save restarts, then a second start arrives.
        with patch.object(self.app, "_clear_singleton_cache"):
            self.mgr.restart("terminal")
            self._join_threads()
            self.mgr.start(["terminal"])
            self._join_threads()

        live = [ch for ch in self.created if ch.running]
        self.assertEqual(len(live), 1, f"expected one live channel, got {len(live)}")
        self.assertIs(live[0], self.mgr.get_channel("terminal"))

    def test_a_fresh_start_is_untouched(self):
        self.mgr.start(["web"])
        self._join_threads()
        self.assertEqual(self.mgr.get_channel("web").startups, 1)


if __name__ == "__main__":
    unittest.main()
