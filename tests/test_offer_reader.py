import copy
import json
from pathlib import Path
import unittest

from tools.live.offer_reader import load_names, read_offer


ROOT = Path(__file__).resolve().parents[1]


class NativeOfferReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads((ROOT / "tests/fixtures/live-offer-1920.json").read_text(encoding="utf-8"))
        cls.names = load_names(ROOT)

    def test_real_native_titles_match_three_ids_in_spatial_order(self):
        result = read_offer(self.fixture["screen"], self.names)
        self.assertEqual([card["id"] for card in result["cards"]], self.fixture["expected_ids"])

    def test_other_overlay_titles_do_not_count_as_native_offer(self):
        screen = copy.deepcopy(self.fixture["screen"])
        for line in screen["ocr_lines"]:
            for word in line["words"]:
                word["y"] = 142
        self.assertEqual(read_offer(screen, self.names)["status"], "unobserved")

    def test_partial_offer_is_not_published_as_complete(self):
        screen = copy.deepcopy(self.fixture["screen"])
        screen["ocr_lines"] = screen["ocr_lines"][:2]
        self.assertEqual(read_offer(screen, self.names)["status"], "unobserved")

    def test_unknown_left_title_does_not_hide_recognized_middle_and_right(self):
        screen = copy.deepcopy(self.fixture["screen"])
        screen["ocr_lines"][0]["words"][0]["text"] = "Unrecognized"
        result = read_offer(screen,self.names)
        self.assertEqual(result["status"],"unobserved")
        self.assertEqual([c["slot"] for c in result["recognized_slots"]],[1,2])

    def test_unknown_name_is_not_replaced_by_nearest_card(self):
        screen = copy.deepcopy(self.fixture["screen"])
        screen["ocr_lines"][0]["words"][0]["text"] = "Unrecognized"
        self.assertEqual(read_offer(screen, self.names)["status"], "unobserved")

    def test_uncalibrated_resolution_is_explicit(self):
        screen = dict(self.fixture["screen"], width=2560, height=1440)
        self.assertEqual(read_offer(screen, self.names)["reason"], "layout_not_calibrated")

    def test_background_window_does_not_reuse_a_previous_offer(self):
        self.assertEqual(read_offer({"status": "game_not_foreground"}, self.names)["status"], "unobserved")


if __name__ == "__main__":
    unittest.main()
