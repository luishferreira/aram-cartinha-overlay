import unittest

from tools.live.probe import identify_champion, redact


CATALOG = [{"id": 22, "key": "Ashe", "name": "Ashe"},
           {"id": 20, "key": "Nunu", "name": "Nunu e Willump"}]


class ChampionIdentityTests(unittest.TestCase):
    def test_self_is_matched_by_full_id_not_player_order(self):
        data = {"activePlayer": {"riotId": "Player#BR1"}, "allPlayers": [
            {"riotId": "Other#BR1", "rawChampionName": "game_character_displayname_Nunu"},
            {"riotId": "Player#BR1", "rawChampionName": "game_character_displayname_Ashe"}]}
        self.assertEqual(identify_champion(data, CATALOG)["champion_id"], 22)

    def test_tag_conflict_does_not_select_same_game_name(self):
        data = {"activePlayer": {"riotId": "Player#BR1", "riotIdGameName": "Player"},
                "allPlayers": [{"riotId": "Player#NA1", "riotIdGameName": "Player", "championName": "Ashe"}]}
        self.assertEqual(identify_champion(data, CATALOG)["status"], "unresolved")

    def test_duplicate_legacy_names_are_ambiguous(self):
        data = {"activePlayer": {"summonerName": "Player"}, "allPlayers": [
            {"summonerName": "Player", "championName": "Ashe"},
            {"summonerName": "Player", "championName": "Nunu e Willump"}]}
        self.assertEqual(identify_champion(data, CATALOG)["reason"], "ambiguous_player")

    def test_raw_key_works_with_different_display_language(self):
        data = {"activePlayer": {"riotIdGameName": "Player", "riotIdTagLine": "BR1"},
                "allPlayers": [{"riotId": "Player#BR1", "championName": "Nunu & Willump",
                                "rawChampionName": "game_character_displayname_Nunu"}]}
        self.assertEqual(identify_champion(data, CATALOG)["champion_id"], 20)

    def test_unknown_variant_is_not_silently_mapped_to_base(self):
        data = {"activePlayer": {"riotId": "Player#BR1"}, "allPlayers": [
            {"riotId": "Player#BR1", "rawChampionName": "game_character_displayname_Jade_Ashe"}]}
        self.assertEqual(identify_champion(data, CATALOG)["status"], "unresolved")

    def test_no_player_does_not_reuse_an_old_champion(self):
        self.assertEqual(identify_champion({}, CATALOG)["status"], "unresolved")

    def test_redaction_preserves_mechanical_evidence(self):
        data = {"allPlayers": [{"riotId": "Player#BR1", "summonerName": "Player", "puuid": "private",
                                "rawChampionName": "game_character_displayname_Ashe", "fullRunes": {"id": 3086}}]}
        result = redact(data)
        self.assertEqual(result["allPlayers"][0]["riotId"], "[redacted]")
        self.assertEqual(result["allPlayers"][0]["puuid"], "[redacted]")
        self.assertEqual(result["allPlayers"][0]["fullRunes"]["id"], 3086)
        self.assertEqual(data["allPlayers"][0]["riotId"], "Player#BR1")


if __name__ == "__main__":
    unittest.main()
