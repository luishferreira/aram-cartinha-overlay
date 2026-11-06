import unittest

from tools.live.tracking import DebugTracker


OFFER = {"status": "observed", "cards": [
    {"id": 1072, "catalog_name": "Alvorada Flamejante", "slot": 0},
    {"id": 1373, "catalog_name": "Engenho do Encolhimento", "slot": 1},
    {"id": 1996, "catalog_name": "Aprimoramento – Fulgor", "slot": 2}]}
NONE = {"status": "unobserved"}


class DebugTrackingTests(unittest.TestCase):
    def ready(self):
        tracker = DebugTracker()
        tracker.set_match("match-a", {"name": "Lillia", "champion_id": 876}, 0)
        tracker.frame(OFFER, "present", 1)
        tracker.frame(OFFER, "present", 2)
        return tracker

    def test_offer_requires_two_consistent_reads(self):
        tracker = DebugTracker()
        tracker.frame(OFFER, "present", 1)
        self.assertIsNone(tracker.offer)
        tracker.frame(OFFER, "present", 2)
        self.assertEqual(len(tracker.offer), 3)

    def test_click_and_two_absent_frames_are_only_an_inference(self):
        tracker = self.ready()
        tracker.click(960, 445, 2.1)
        self.assertEqual(tracker.selected, [])
        tracker.frame(NONE, "absent", 3)
        self.assertEqual(tracker.selected, [])
        tracker.frame(NONE, "absent", 4)
        self.assertEqual(tracker.selected[0]["id"], 1373)
        self.assertEqual(tracker.selected[0]["confidence"], "inferred")

    def test_click_without_panel_closing_does_not_pick(self):
        tracker = self.ready()
        tracker.click(960, 445, 2.1)
        tracker.frame(OFFER, "present", 3)
        tracker.frame(OFFER, "present", 4)
        self.assertEqual(tracker.selected, [])

    def test_reroll_button_is_not_a_choice(self):
        tracker = self.ready()
        tracker.click(960, 760, 2.1)
        tracker.frame(NONE, "absent", 3)
        tracker.frame(NONE, "absent", 4)
        self.assertEqual(tracker.selected, [])

    def test_rerolled_offer_cancels_a_pending_click(self):
        tracker = self.ready()
        tracker.click(960, 445, 2.1)
        changed = {"status": "observed", "cards": [dict(c) for c in OFFER["cards"]]}
        changed["cards"][1]["id"] = 1332
        tracker.frame(changed, "present", 3)
        tracker.frame(NONE, "absent", 4)
        tracker.frame(NONE, "absent", 5)
        self.assertEqual(tracker.selected, [])

    def test_collapse_button_cancels_pending_choice(self):
        tracker = self.ready()
        tracker.click(960, 445, 2.1)
        tracker.click(960, 850, 2.2)
        tracker.frame(NONE, "absent", 3)
        tracker.frame(NONE, "absent", 4)
        self.assertEqual(tracker.selected, [])

    def test_alt_tab_and_ocr_failures_are_not_panel_closure(self):
        tracker = self.ready()
        tracker.click(960, 445, 2.1)
        for time in (3, 4, 5):
            tracker.frame(NONE, "unknown", time)
        self.assertEqual(tracker.selected, [])

    def test_stale_offer_does_not_capture_an_unrelated_click(self):
        tracker = self.ready()
        tracker.click(960, 445, 7)
        self.assertIsNone(tracker.pending)

    def test_partial_read_after_reroll_does_not_select_cached_slot(self):
        tracker = self.ready()
        tracker.frame(NONE, "present", 2.2)
        tracker.click(960, 445, 2.3)
        self.assertIsNone(tracker.pending)

    def test_new_match_never_inherits_the_old_history(self):
        tracker = self.ready()
        tracker.selected = [{"id": 1030, "confidence": "inferred"}]
        tracker.set_match("match-b", {"name": "Ashe", "champion_id": 22}, 4)
        self.assertEqual(tracker.selected, [])
        self.assertIsNone(tracker.offer)

    def test_restore_requires_the_exact_match_key(self):
        tracker = self.ready()
        tracker.selected = [{"id": 1030, "confidence": "inferred"}]
        saved = tracker.export()
        restored = DebugTracker()
        restored.set_match("match-a", {"name": "Lillia"}, 10, saved)
        self.assertEqual(restored.selected[0]["id"], 1030)
        unrelated = DebugTracker()
        unrelated.set_match("match-b", {"name": "Ashe"}, 10, saved)
        self.assertEqual(unrelated.selected, [])


if __name__ == "__main__":
    unittest.main()
