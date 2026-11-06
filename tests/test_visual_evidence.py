import json
from pathlib import Path
import tempfile
import unittest
import threading
from unittest.mock import Mock

from tools.live.visual_evidence import (AnimationDetector, EvidenceLedger, IconBank,
                                      panel_state, self_tab_cells, tooltip_card)
from tools.live.offer_reader import load_names
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "data/test-tmp"
CARDS = [{"id": i, "catalog_name": f"Card {i}", "slot": s} for s,i in enumerate((1030,1373,1332))]


class EvidenceTests(unittest.TestCase):
    def test_real_tab_icons_match_offer_only_templates_without_hover_learning(self):
        fixture=ROOT / "tests/fixtures/tab-icons-yasuo"
        case=json.loads((fixture / "case.json").read_text())
        TMP.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=TMP) as folder, Image.open(fixture/"own-row.png") as row:
            bank=IconBank(folder)
            for card_id in case["ids"]:
                with Image.open(fixture/f"offer-{card_id}.png") as patch:
                    bank.add_offer(card_id,patch)
            # The first sword remains ambiguous against other sword augments.
            # The other two must work before any tooltip trains a TAB template.
            for (x,y),expected in zip(case["centers"],case["expected"]):
                result=bank.match(row.crop((x-18,y-18,x+18,y+18)),case["ids"])
                self.assertEqual(result["id"] if result else None,expected)

    def test_real_yasuo_rerolls_do_not_survive_as_a_wrong_selection(self):
        fixture=ROOT / "tests/fixtures/yasuo-reroll"
        case=json.loads((fixture / "case.json").read_text())
        detector=AnimationDetector();events=[]
        for frame in case["frames"]:
            image=Image.new("RGB",(1920,1080))
            with Image.open(fixture/frame["path"]) as crop:
                image.paste(crop.resize((1080,660)),(420,120))
            slot=detector.update(image,frame["time"],panel_state(image))
            if slot is not None:
                events.append((frame["time"],slot))
        self.assertEqual(len(events),1)
        self.assertEqual(events[0][1],0)
        self.assertTrue(124.3 <= events[0][0] <= 125)

    def test_collector_requires_two_self_tooltip_reads_and_recovers_unseen_offer(self):
        from tools.live.visual_collector import VisualCollector
        from tools.live.tracking import DebugTracker
        source=ROOT / "research/live-validation/20261030T224714.575803Z/20261030T224726.762306Z"
        screen=json.loads(Path(str(source)+".observation.json").read_text(encoding="utf-8"))["screen"]
        TMP.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=TMP) as folder, Image.open(str(source)+".png") as image:
            app=Mock();app.local=app.run=Path(folder)
            app.tracker,app.lock,app.names=DebugTracker(),threading.RLock(),load_names(ROOT)
            collector=VisualCollector(app);collector.bind({"pid":1,"process_start":1})
            collector.player_names={"keita"}
            collector.accept_tab(screen,image,(357,635),1)
            self.assertEqual(collector.ledger.selected,[])
            collector.accept_tab(screen,image,(357,635),2)
            self.assertEqual(collector.ledger.selected[0]["id"],1332)
            self.assertEqual(collector.ledger.selected[0]["confidence"],"visual_name")

    def test_real_video_frames_flow_through_offer_binding_and_selection(self):
        from tools.live.visual_collector import VisualCollector
        from tools.live.tracking import DebugTracker
        fixture=ROOT / "tests/fixtures/visual-selection"
        cases=json.loads((fixture / "cases.json").read_text())
        TMP.mkdir(parents=True,exist_ok=True)
        for case in cases:
            with self.subTest(video=case["source_video"]), tempfile.TemporaryDirectory(dir=TMP) as folder:
                app=Mock();app.local=app.run=Path(folder)
                app.tracker,app.lock=DebugTracker(),threading.RLock()
                collector=VisualCollector(app);collector.bind({"pid":1,"process_start":1})
                cards=[{"id":i,"catalog_name":str(i),"slot":s} for s,i in enumerate(case["cards"])]
                for index,frame in enumerate(case["frames"]):
                    image=Image.new("RGB",(1920,1080))
                    with Image.open(fixture / frame["path"]) as crop:
                        image.paste(crop,(420,170))
                    if index==0:
                        collector.accept_offer({"status":"observed","cards":cards},image,frame["time"])
                    panel=panel_state(image)
                    slot=collector.detector.update(image,frame["time"],panel)
                    if panel=="present":
                        collector.update_offer_context(image,frame["time"])
                    if slot is not None:
                        collector.animation_choice(slot,image,frame["time"])
                self.assertEqual([c["id"] for c in collector.ledger.selected],[case["cards"][0]])
                self.assertEqual(collector.ledger.selected[0]["evidence"],"selection_animation")

    def test_silver_panel_is_present_with_dark_lower_borders(self):
        im = Image.new("RGB", (1920,1080), (2,20,20))
        for x in (440,808,1176):
            im.putpixel((x,260),(199,199,199))
            im.putpixel((x,500),(93,93,93))
            im.putpixel((x,650),(63,63,63))
        self.assertEqual(panel_state(im), "present")

    def test_hover_alone_never_selects(self):
        detector = AnimationDetector()
        im = Image.new("RGB", (1920,1080), (2,20,20))
        draw = ImageDraw.Draw(im)
        draw.rectangle((440,195,750,710),outline="white",width=15)
        for i in range(60):
            self.assertIsNone(detector.update(im,i/30,"present"))

    def test_animation_selects_each_position_only_after_closure(self):
        for slot in range(3):
            d = AnimationDetector()
            dark = Image.new("RGB", (1920,1080),(2,20,20))
            d.update(dark,0,"present")
            d.update(dark,.5,"present")
            effect = dark.copy()
            ImageDraw.Draw(effect).rectangle((470+370*slot,270,709+370*slot,639),fill="white")
            self.assertIsNone(d.update(effect,.6,"unknown"))
            self.assertIsNone(d.update(effect,.64,"unknown"))
            self.assertIsNone(d.update(effect,.70,"unknown"))
            self.assertEqual(d.update(dark,.8,"absent"),slot)
            self.assertIsNone(d.update(dark,.9,"absent"))

    def test_disappearance_or_global_flash_is_not_a_choice(self):
        for image in (Image.new("RGB",(1920,1080),"black"), Image.new("RGB",(1920,1080),"white")):
            d=AnimationDetector()
            d.update(Image.new("RGB",(1920,1080),"black"),0,"present")
            for i in range(1,30):
                self.assertIsNone(d.update(image,i/30,"absent"))

    def test_rerolls_retained_and_unknown_round_not_treated_as_no_choice(self):
        ledger=EvidenceLedger()
        ledger.offer(CARDS,6,1)
        reroll=[dict(c) for c in CARDS];reroll[0]["id"]=1996
        ledger.offer(reroll,6,2)
        saved=ledger.export()
        self.assertEqual(len(saved["rounds"]),1)
        self.assertEqual(len(saved["rounds"][0]["offers"]),2)
        restored=EvidenceLedger(saved)
        self.assertFalse(restored.rounds[0]["resolved"])
        self.assertEqual(set(restored.candidates()),{1030,1373,1332,1996})

    def test_tooltip_corrects_probable_choice_and_preserves_audit(self):
        ledger=EvidenceLedger();ledger.offer(CARDS,6,1)
        ledger.record(CARDS[0],"selection_animation",2,round_key="round-1")
        ledger.record(CARDS[0],"tab_icon",3,tab_index=0)
        ledger.record(CARDS[1],"tooltip_name",4,tab_index=0)
        self.assertEqual(len(ledger.selected),1)
        self.assertEqual(ledger.selected[0]["id"],1373)
        self.assertEqual(ledger.selected[0]["corrections"][0]["old_id"],1030)
        self.assertEqual(ledger.rounds[0]["selected_id"],1373)
        self.assertFalse(ledger.record(CARDS[2],"tab_icon",5,tab_index=0))
        self.assertEqual(ledger.selected[0]["id"],1373)

    def test_tooltip_can_correct_an_animation_before_tab_index_was_known(self):
        ledger=EvidenceLedger();ledger.offer(CARDS,6,1)
        ledger.record(CARDS[0],"selection_animation",2,round_key="round-1")
        ledger.record(CARDS[1],"tooltip_name",3,tab_index=1)
        self.assertEqual(len(ledger.selected),1)
        self.assertEqual(ledger.selected[0]["id"],1373)
        self.assertEqual(ledger.rounds[0]["selected_id"],1373)
        self.assertEqual(ledger.selected[0]["corrections"][0]["old_id"],1030)
        self.assertEqual(ledger.rounds[0]["selected_id"],1373)
        self.assertFalse(ledger.record(CARDS[2],"tab_icon",5,tab_index=1))
        self.assertEqual(ledger.selected[0]["id"],1373)

    def test_identical_icons_remain_ambiguous(self):
        TMP.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=TMP) as folder:
            bank=IconBank(folder)
            im=Image.new("RGB",(24,24),"black")
            ImageDraw.Draw(im).ellipse((4,4,20,20),fill="white")
            bank.add(1030,im);bank.add(1373,im)
            self.assertIsNone(bank.match(im,[1030,1373]))
            self.assertEqual(bank.match(im,[1030])["id"],1030)

    def test_real_tooltip_requires_self_row_and_hover_over_own_icon(self):
        path=ROOT / "research/live-validation/20261030T224714.575803Z/20261030T224726.762306Z.observation.json"
        screen=json.loads(path.read_text(encoding="utf-8"))["screen"]
        cells=self_tab_cells(screen,{"keita"})
        self.assertEqual(len(cells),6)
        names=load_names(ROOT)
        self.assertEqual(tooltip_card(screen,names,(357,635),cells)["id"],1332)
        self.assertIsNone(tooltip_card(screen,names,(1617,635),cells))
        self.assertEqual(self_tab_cells(screen,{"someoneelse"}),[])
        self.assertIsNone(tooltip_card(screen,names,(357,635),[]))

    def test_real_offer_icon_matches_self_tab_and_empty_cells_do_not_match(self):
        TMP.mkdir(parents=True,exist_ok=True)
        offer=Image.open(ROOT / "research/live-validation/20261030T224149.797765Z/20261030T224149.797765Z.png")
        tab=Image.open(ROOT / "research/live-validation/20261030T224714.575803Z/20261030T224726.762306Z.png")
        with tempfile.TemporaryDirectory(dir=TMP) as folder:
            bank=IconBank(folder)
            cards=[{"id":i,"slot":s} for s,i in enumerate((1072,1373,1996))]
            bank.learn_offer(offer,cards)
            self.assertEqual(bank.match(tab.crop((316,623,340,647)),[1072,1373,1996])["id"],1373)
            self.assertIsNone(bank.match(tab.crop((316,655,340,679)),[1072,1373,1996]))


if __name__ == "__main__":
    unittest.main()
