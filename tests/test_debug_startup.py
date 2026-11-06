import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from tools.live.debug_overlay import DebugApp
from tools.live.offer_reader import load_names
from tools.live.session_history import load_history, process_key
from tools.live.tracking import DebugTracker

ROOT = Path(__file__).resolve().parents[1]
TEST_TMP = ROOT / "data/test-tmp"
GAME = {"pid": 123, "process_start": 987654}


class TwoIterations:
    def __init__(self):
        self.count = 0

    def is_set(self):
        return self.count >= 2

    def wait(self, _):
        self.count += 1


class StartupAcquisitionTests(unittest.TestCase):
    def setUp(self):
        TEST_TMP.mkdir(parents=True, exist_ok=True)

    def test_visual_offer_is_read_even_when_live_api_is_unavailable(self):
        from tools.live.visual_collector import VisualCollector
        from PIL import Image
        import time
        fixture = json.loads((ROOT / "tests/fixtures/live-offer-1920.json").read_text(encoding="utf-8"))
        app = Mock()
        app.stop, app.lock, app.tracker = TwoIterations(), threading.RLock(), DebugTracker()
        app.catalog, app.names = [], load_names(ROOT)
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as folder:
            app.local = app.run = Path(folder)
            collector = VisualCollector(app)
            collector.bind(GAME)
            image = Image.new("RGB", (1920,1080))
            collector.latest = (collector.key, 1, time.monotonic(), image, "present", False, None)
            def next_frame(*args, **kwargs):
                collector.latest = (collector.key, collector.latest[1]+1, time.monotonic(), image, "present", False, None)
                return dict(fixture["screen"])
            with patch("tools.live.visual_collector.fetch_local", side_effect=ConnectionError), patch(
                "tools.live.visual_collector.capture", side_effect=next_frame) as capture:
                collector.ocr_loop()
        self.assertEqual(capture.call_count, 2)
        self.assertEqual([card["id"] for card in app.tracker.offer], fixture["expected_ids"])
        self.assertIsNone(app.tracker.champion)

    def test_champion_arriving_later_does_not_clear_early_choice(self):
        tracker = DebugTracker()
        key = process_key(GAME)
        tracker.set_match(key, None, 1)
        tracker.selected = [{"id": 1030, "confidence": "inferred"}]
        tracker.set_match(key, {"name": "Shaco", "champion_id": 35}, 5)
        self.assertEqual(tracker.selected[0]["id"], 1030)
        self.assertEqual(tracker.champion["name"], "Shaco")

    def test_binding_without_new_api_does_not_mark_old_data_as_fresh(self):
        tracker = DebugTracker()
        key = process_key(GAME)
        tracker.set_match(key, {"name": "Shaco"}, 1)
        tracker.set_match(key, None, 10)
        self.assertTrue(tracker.view(10)["api_stale"])

    def test_legacy_history_migrates_only_for_the_same_process_start(self):
        legacy = hashlib.sha256(b"123:987654:35").hexdigest()[:24]
        state = {"match_key": legacy, "champion": {"champion_id": 35}, "selected": [{"id": 1104}]}
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as folder:
            local = Path(folder)
            (local / "state.json").write_text(json.dumps(state), encoding="utf-8")
            result = load_history(local, GAME)
            self.assertEqual(result["selected"], [{"id": 1104}])
            self.assertEqual(result["match_key"], process_key(GAME))
            self.assertIsNone(load_history(local, dict(GAME, process_start=987655)))
            self.assertEqual(json.loads((local / "state.json").read_text())["match_key"], legacy)


if __name__ == "__main__":
    unittest.main()
