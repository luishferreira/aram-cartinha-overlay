import unittest

from tools.live.compact_overlay import tiers, combo_summary, comparison_rows,score_text,observation_sections
from tools.live.source_cards import SourceReader


class CompactPresentationTests(unittest.TestCase):
    def setUp(self):
        self.reader = SourceReader()

    def tearDown(self):
        self.reader.close()

    def test_tiers_use_champion_evidence_and_never_fall_back_to_global(self):
        card = self.reader.read(11, 3086, [2141])
        self.assertEqual(tiers(card), ("A", "S", "A", "—"))
        self.assertIsNotNone(card["sources"]["arammayhem_tier"])
        self.assertEqual(tiers(self.reader.read(None, 3086)), ("—",)*4)

    def test_compact_par_summary_refers_to_selected_card_and_has_no_wr(self):
        summary = combo_summary(self.reader.read(11, 3086, [2141]))
        self.assertEqual(summary[0], "Par observado")
        self.assertIn("Ultra-Hidra", summary[1])
        self.assertNotIn("WR", " ".join(summary))

    def test_comparison_keeps_incomplete_trio_separate_from_wr(self):
        card = self.reader.read(11, 1058, [1029])
        summary = combo_summary(card)
        self.assertEqual(summary[0], "Caminho de trio")
        self.assertIn("Recursão", summary[1])
        rows = comparison_rows([card, None, self.reader.read(None, 1058)])
        self.assertEqual(rows[-1][1], ["Incompleto", "—", "—"])
        self.assertEqual(len(rows), 10)
        self.assertNotIn("índice", str(rows))
        self.assertNotIn("jogos", str(rows))
        self.assertNotIn("CN", str(rows))

    def test_score_is_a_separate_number_with_coverage_not_a_percentage(self):
        card=self.reader.read(18,3078)
        value=card['keitinha_score']['value']
        self.assertEqual(score_text(card),f'{value:.1f}'.replace('.',','))
        self.assertNotIn('%',score_text(card))
        self.assertIn('/4 fontes',comparison_rows([card,None,None])[0][1][0])
        self.assertEqual(score_text(self.reader.read(None,3078)),'—')
        self.assertEqual(score_text({'error':'unavailable'}),'—')

    def test_no_contextual_data_does_not_create_a_recommendation(self):
        self.assertIsNone(combo_summary(None))
        self.assertIsNone(combo_summary({"error": "unavailable"}))
        self.assertIsNone(combo_summary(self.reader.read(None, 1058)))
        self.assertEqual(tiers({"error": "unavailable"}), ("—",)*4)

    def test_editorial_summary_keeps_source_wording_without_invented_requirements(self):
        card = self.reader.read(11, 1015, [2141])
        summary = combo_summary(card)
        self.assertEqual(summary[0], "Nota para o campeão")
        self.assertEqual(summary[1], card["editorial"]["text"])
        self.assertIn("editorial (EN)", summary[2])

    def test_expanded_observations_include_every_full_editorial_and_combo(self):
        card = self.reader.read(11, 1058, [1029])
        evidence = card['combo_evidence']
        sections = observation_sections(card)
        self.assertEqual(len(sections), len(evidence['editorial'])+len(evidence['observed']))
        for note, (_, body) in zip(evidence['editorial'], sections):
            self.assertIn(note['text'], body)
            for name in note['other_names']:
                self.assertIn(name, body)
        for combo, (heading, body) in zip(evidence['observed'], sections[len(evidence['editorial']):]):
            for name in combo['member_names']+combo['missing_names']:
                self.assertIn(name, body)
            if combo['missing_names']:
                self.assertIn('incompleto', heading)
                self.assertNotIn('WR', body)
            else:
                self.assertIn('WR observado', body)


if __name__ == "__main__":
    unittest.main()
