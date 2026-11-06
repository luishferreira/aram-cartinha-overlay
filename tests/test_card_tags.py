import copy
from pathlib import Path
import unittest

from tools.live.card_tags import CardTags
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
CARDS=[{"id":i,"catalog_name":str(i),"slot":s} for s,i in enumerate((1072,1373,1996))]


class CardTagTests(unittest.TestCase):
    def setUp(self):
        self.image=Image.open(ROOT / "research/live-validation/20261030T224149.797765Z/20261030T224149.797765Z.png").convert("RGB")

    def test_partial_first_read_labels_only_known_positions(self):
        tags=CardTags();tags.frame(self.image,"present",10)
        reading={"status":"unobserved","recognized_slots":CARDS[1:]}
        published=tags.publish(reading,self.image,10.1,self.image,"present",now=10.8)
        self.assertIsNone(tags.tags[0])
        self.assertEqual([c["slot"] for c in published],[1,2])
        self.assertEqual(tags.tags[1]["panel_seen_at"],10)
        self.assertEqual(tags.tags[1]["detected_at"],10.8)

    def test_reroll_invalidates_changed_slot_and_rejects_old_ocr(self):
        tags=CardTags();tags.frame(self.image,"present",10)
        reading={"status":"observed","cards":CARDS}
        tags.publish(reading,self.image,10.1,self.image,"present",now=10.8)
        changed=self.image.copy()
        ImageDraw.Draw(changed).rectangle((437,400,747,478),fill="black")
        tags.frame(changed,"present",11)
        self.assertIsNone(tags.tags[0])
        self.assertEqual(tags.tags[1]["id"],1373)
        tags.publish(reading,self.image,10.9,changed,"present",now=11.5)
        self.assertIsNone(tags.tags[0])

    def test_panel_closure_and_old_frames_never_show_labels(self):
        tags=CardTags();tags.frame(self.image,"present",10)
        reading={"status":"observed","cards":CARDS}
        self.assertEqual(tags.publish(reading,self.image,10,self.image,"present",now=15),[])
        tags.publish(reading,self.image,15,self.image,"present",now=15.5)
        tags.frame(self.image,"absent",16)
        self.assertEqual(tags.tags,[None,None,None])
        self.assertEqual(tags.publish(reading,self.image,15,self.image,"absent",now=16),[])

    def test_refresh_keeps_initial_detection_time_without_duplicate_event(self):
        tags=CardTags();tags.frame(self.image,"present",10)
        reading={"status":"observed","cards":CARDS}
        tags.publish(reading,self.image,10,self.image,"present",now=11)
        self.assertEqual(tags.publish(reading,self.image,11.5,self.image,"present",now=12),[])
        self.assertEqual(tags.tags[0]["detected_at"],11)
        self.assertEqual(tags.tags[0]["observed_at"],12)

    def test_brief_reroll_uncertainty_preserves_unchanged_labels(self):
        tags=CardTags();tags.frame(self.image,"present",10)
        tags.publish({"status":"observed","cards":CARDS},self.image,10,self.image,"present",now=10.1)
        tags.frame(self.image,"present",10.1)
        changed=self.image.copy()
        ImageDraw.Draw(changed).rectangle((805,235,1115,478),fill="black")
        tags.frame(changed,"unknown",10.12)
        tags.frame(changed,"absent",10.15)
        self.assertIsNone(tags.tags[1])
        self.assertEqual(tags.tags[0]["id"],1072)
        self.assertEqual(tags.tags[2]["id"],1996)
        tags.frame(changed,"unknown",10.3)
        self.assertEqual(tags.tags[2]["id"],1996)


if __name__ == "__main__":
    unittest.main()
