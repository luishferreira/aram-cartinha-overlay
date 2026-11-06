from pathlib import Path
import tempfile
import time
import unittest

from tools.live.source_cards import SourceReader,SourceCards,panel_rows,combo_rows,fit_combo_text,percent,count


class LiveSourceCardTests(unittest.TestCase):
    def setUp(self):
        self.reader=SourceReader()

    def tearDown(self):
        self.reader.close()

    def test_real_champion_card_preserves_independent_sources_and_scopes(self):
        card=self.reader.read(18,3078)
        sources=card["sources"]
        self.assertEqual(sources["blitz"]["metrics"]["tier"]["value"],"S")
        self.assertEqual(sources["opgg"]["metrics"]["tier"]["value"],"A")
        # General ARAMKit differs from stage 1 (49.04%); no inferred stage.
        self.assertEqual(sources["aramkit"]["metrics"]["win_rate"]["value"],.4948)
        self.assertEqual(sources["aramkit"]["metrics"]["sample_count"]["value"],70979)
        self.assertEqual(sources["aramgg"]["metrics"]["win_rate"]["value"],.5005)
        self.assertEqual(sources["aramgg"]["metrics"]["sample_count"]["value"],8440)
        self.assertEqual(sources["aramgg"]["context"]["region"],"WORLD")
        self.assertEqual(sources["aramgg_popularity"]["context"]["region"],"CN")
        self.assertIsNone(sources["opgg"]["patch"])
        self.assertIsNone(card["combined_tier"])
        self.assertEqual(card["scope"],"champion_overall_not_build")
        self.assertEqual(self.reader.db.execute("PRAGMA query_only").fetchone()[0],1)

    def test_undefined_opgg_performance_is_index_and_popularity_is_calculated_rank(self):
        card=self.reader.read(18,3078)
        rows=panel_rows(card)
        self.assertIn("83,81",rows[5])
        self.assertNotIn("83,81%",rows[5])
        self.assertNotIn("WR",rows[5])
        self.assertEqual(card["opgg_popularity"]["rank"],32)
        self.assertEqual(card["opgg_popularity"]["published_entries"],195)
        self.assertEqual(card["sources"]["arammayhem_tier"]["scope"],"global")

    def test_no_champion_never_uses_another_champions_statistics(self):
        card=self.reader.read(None,3078)
        self.assertIsNone(card["sources"]["aramkit"])
        self.assertIsNone(card["sources"]["blitz"])
        self.assertIsNone(card["opgg_popularity"])
        self.assertIsNotNone(card["sources"]["arammayhem_tier"])

    def test_missing_is_not_zero_and_zero_is_not_missing(self):
        card=self.reader.read(18,999999)
        self.assertTrue(all(v is None for v in card["sources"].values()))
        self.assertIn("WR —",panel_rows(card)[0])
        self.assertEqual(percent(0),"0,00%")
        self.assertEqual(count(0),"0")

    def test_editorial_keeps_original_text_and_hypothesis_status(self):
        card=self.reader.read(18,1134,[1077])
        self.assertIn("Draw Your Sword",card["editorial"]["text"])
        self.assertEqual(card["editorial"]["validation"],"editorial_hypothesis")
        self.assertEqual(card["editorial"]["selected_members"],[])
        self.assertTrue(any("Nota Mayhem (EN)" in row for row in combo_rows(card)))

    def test_contextual_editorial_does_not_mutate_cached_base(self):
        self.reader.editorials["champion:game:18"]=[
            {"augment_ids":["augment:game:3078"],"explanation":"Solo note","url":"solo"},
            {"augment_ids":["augment:game:3078","augment:game:1077"],"explanation":"Pair note","url":"pair"}]
        first=self.reader.read(18,3078,[1077])
        second=self.reader.read(18,3078,[])
        self.assertEqual(first["editorial"]["text"],"Pair note")
        self.assertEqual(first["editorial"]["selected_members"],["augment:game:1077"])
        self.assertEqual(second["editorial"]["selected_members"],[])
        first["sources"]["blitz"]["metrics"]["tier"]["value"]="X"
        self.assertEqual(self.reader.read(18,3078)["sources"]["blitz"]["metrics"]["tier"]["value"],"S")

    def test_worker_loads_locally_and_caches_without_blocking_ui_lookup(self):
        service=SourceCards()
        try:
            started=time.monotonic()
            card=service.get(18,3078,[1077])
            while card is None and time.monotonic()-started<3:
                time.sleep(.01)
                card=service.get(18,3078,[1077])
            self.assertIsNotNone(card)
            self.assertEqual(card["champion_id"],18)
            self.assertEqual(card["selected_ids"],[1077])
            self.assertIs(service.get(18,3078,[1077]),card)
        finally:
            service.close()
            service.thread.join(timeout=1)

    def test_real_trio_completion_is_observed_not_a_prediction(self):
        card=self.reader.read(17,3086,[1030,1098])
        trio=next(c for c in card["combo_evidence"]["observed"] if c["source"]=="aramgg")
        self.assertEqual(trio["status"],"completes_observed")
        self.assertEqual(trio["missing_members"],[])
        self.assertEqual(trio["metrics"]["sample_count"]["value"],159)
        self.assertEqual(trio["metrics"]["win_rate"]["value"],.7358)
        self.assertFalse(trio["causal_synergy"])
        self.assertIsNone(trio["predicted_win_rate"])
        self.assertIn("Forma trio observado",combo_rows(card)[0])
        self.assertFalse(card["combo_evidence"]["selected_winner"])

    def test_partial_trio_does_not_display_its_wr_as_current_context(self):
        card=self.reader.read(17,3086,[1030])
        trio=next(c for c in card["combo_evidence"]["observed"]
                  if set(c["augment_ids"])=={"augment:game:1030","augment:game:1098","augment:game:3086"})
        self.assertEqual(trio["status"],"observed_path")
        self.assertEqual(trio["missing_members"],["augment:game:1098"])
        # Use just this evidence to verify its own display, independently of other pairs.
        card["combo_evidence"]={"observed":[trio],"editorial":[]}
        self.assertTrue(any(row.startswith("Falta:") for row in combo_rows(card)))
        self.assertNotIn("WR", " ".join(combo_rows(card)))

    def test_observed_history_unknown_patch_and_retired_members_are_excluded(self):
        def pair(native,**extra):
            return {"source":"aramkit","kind":"observed_pair","native_id":native,
                    "augment_ids":["augment:game:1058","augment:game:1029"],"patch":"16.21",
                    "metrics":{"win_rate":{"value":.6},"sample_count":{"value":100}},**extra}
        self.reader.combinations["champion:game:11"]=[
            pair("valid"),pair("old",historical_patch=True),pair("other_patch",patch="16.19"),
            pair("unknown_patch",patch=None),pair("retired",augment_ids=["augment:game:1058","augment:game:1310"]),
            pair("unresolved",augment_ids=["augment:game:1058","augment:arammayhem:unknown"])]
        self.reader.availability["augment:game:1310"]=["retired"]
        rows=self.reader.observed_combos(11,1058,[1029])
        self.assertEqual([r["native_id"] for r in rows],["valid"])

    def test_context_and_sample_size_order_observations_instead_of_highest_wr(self):
        def pair(native,other,wr,n):
            return {"source":"aramkit","kind":"observed_pair","native_id":native,
                    "augment_ids":["augment:game:1058",f"augment:game:{other}"],"patch":"16.21",
                    "metrics":{"win_rate":{"value":wr},"sample_count":{"value":n}}}
        self.reader.combinations["champion:game:11"]=[pair("high_wr",1029,.99,20),
            pair("more_sample",1029,.5,200),pair("missing_card",1030,1,10000)]
        rows=self.reader.observed_combos(11,1058,[1029])
        self.assertEqual([r["native_id"] for r in rows],["more_sample","high_wr","missing_card"])

    def test_editorial_members_are_not_converted_to_requirements(self):
        self.reader.editorials["champion:game:11"]=[
            {"augment_ids":["augment:game:1058","augment:game:1029","augment:game:1030"],
             "explanation":"Several alternatives, not mandatory prerequisites.","member_semantics":"unspecified"}]
        card=self.reader.read(11,1058,[1029])
        note=card["editorial"]
        self.assertEqual(note["selected_members"],["augment:game:1029"])
        self.assertEqual(note["other_members"],["augment:game:1030"])
        self.assertIsNone(note["required_members"])
        self.assertIsNone(note["required_items"])
        self.assertTrue(any(row.startswith("Outras citadas:") for row in combo_rows(card)))

    def test_empty_retired_and_unresolved_editorial_cannot_drive_advice(self):
        self.reader.editorials["champion:game:11"]=[
            {"augment_ids":["augment:game:1058"],"explanation":"Nothing."},
            {"augment_ids":["augment:game:1058","augment:arammayhem:unknown"],"explanation":"Unknown card"},
            {"augment_ids":["augment:game:1058","augment:game:1310"],"explanation":"Retired card"}]
        self.reader.availability["augment:game:1310"]=["retired"]
        self.assertEqual(self.reader.editorial_options(11,1058,[]),[])

    def test_missing_champion_or_card_produces_no_contextual_advice(self):
        for champion,card in ((None,1058),(11,999999)):
            result=self.reader.read(champion,card,[1029])
            self.assertEqual(result["combo_evidence"]["observed"],[])
            self.assertEqual(result["combo_evidence"]["editorial"],[])
            self.assertEqual(combo_rows(result),[])

    def test_changing_selected_cards_recomputes_completion_without_mutating_previous_result(self):
        before=self.reader.read(17,3086,[1030])
        after=self.reader.read(17,3086,[1030,1098,1098])
        self.assertTrue(all(c["missing_members"] for c in before["combo_evidence"]["observed"] if c["source"]=="aramgg"))
        self.assertTrue(any(not c["missing_members"] for c in after["combo_evidence"]["observed"] if c["source"]=="aramgg"))

    def test_context_text_fits_budget_and_marks_truncated_explanations(self):
        text=fit_combo_text(["Com: carta escolhida", "Nota muito longa com ressalvas importantes"],len,20,2)
        self.assertEqual(len(text.splitlines()),2)
        self.assertTrue(text.endswith("…"))
        self.assertTrue(all(len(line)<=20 for line in text.splitlines()))
        self.assertEqual(fit_combo_text(["texto"],len,20,0),"")
        long=fit_combo_text(["a"*100],len,20,2)
        self.assertTrue(all(len(line)<=20 for line in long.splitlines()))

    def test_unavailable_database_reports_failure_instead_of_inventing_statistics(self):
        base=Path(__file__).resolve().parents[1]/"data/test-tmp"
        base.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as folder:
            service=SourceCards(folder)
            try:
                service.thread.join(timeout=1)
                result=service.get(18,3078)
                self.assertIn("error",result)
                self.assertEqual(panel_rows(result)[0],"Base local indisponível")
                self.assertNotIn("WR", " ".join(panel_rows(result)))
            finally:
                service.close()


if __name__=="__main__":
    unittest.main()
