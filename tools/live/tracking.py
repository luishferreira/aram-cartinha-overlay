"""Acquisition state for the debug overlay; inferred picks are never verified picks."""
import copy


class DebugTracker:
    def __init__(self):
        self.match_key = None
        self.champion = None
        self.selected = []
        self.offer = None
        self.offer_seen_at = 0.0
        self.candidate_signature = None
        self.candidate_count = 0
        self.pending = None
        self.absent_count = 0
        self.visible = "unknown"
        self.api_seen_at = 0.0
        self.status = "Aguardando partida"
        self.history_partial = True
        self.revision = 0
        self.rounds = []
        self.validation_pending = False

    def set_match(self, key, champion, now, restored=None):
        if key != self.match_key:
            self.__init__()
            self.match_key = key
            if restored and restored.get("match_key") == key:
                self.selected = copy.deepcopy(restored.get("selected", []))
                self.rounds = copy.deepcopy(restored.get("rounds", []))
            self.status = "Histórico iniciado pelo debug; pode estar parcial"
        if champion is not None:
            self.champion = champion
            self.api_seen_at = now

    def frame(self, reading, panel, now):
        self.visible = panel
        if reading.get("status") == "observed":
            signature = tuple(card["id"] for card in reading["cards"])
            if self.pending and signature != self.pending["signature"]:
                self.pending = None
                self.status = "Oferta mudou / reroll; nenhuma aquisição registrada"
            if signature == self.candidate_signature:
                self.candidate_count += 1
            else:
                self.candidate_signature = signature
                self.candidate_count = 1
            if self.candidate_count >= 2:
                self.offer = copy.deepcopy(reading["cards"])
                self.offer_seen_at = now
                if not self.pending:
                    self.status = "Três cartas lidas na seleção nativa"
            self.absent_count = 0
        else:
            self.candidate_signature = None
            self.candidate_count = 0
            if panel == "absent":
                self.absent_count += 1
            else:
                self.absent_count = 0
        if self.pending:
            if now - self.pending["at"] > 8:
                self.pending = None
                self.status = "Escolha não confirmada pela transição; descartada"
            elif panel == "absent" and self.absent_count >= 2 and now - self.pending["at"] >= 0.3:
                card = copy.deepcopy(self.pending["card"])
                card.update(confidence="inferred", evidence="click_and_panel_closed", selected_at=now)
                self.selected.append(card)
                self.revision += 1
                self.pending = None
                self.offer = None
                self.status = "Escolha INFERIDA: clique + fechamento; HUD não verificado"
        if panel == "absent" and self.absent_count >= 2 and not self.pending:
            self.offer = None

    def click(self, x, y, now):
        # The collapse control is not a choice. Reroll controls (y~760) are excluded.
        if 850 <= x <= 1070 and 820 <= y <= 900:
            self.pending = None
            self.status = "Painel recolhido; sem aquisição"
            return
        if (not self.offer or self.visible != "present" or now - self.offer_seen_at > 3
                or self.candidate_count < 2 or self.candidate_signature != tuple(c["id"] for c in self.offer)):
            return
        if not 220 <= y <= 660:
            return
        for slot, (left, right) in enumerate(((455, 730), (825, 1100), (1195, 1470))):
            if left <= x <= right:
                self.pending = {"card": copy.deepcopy(self.offer[slot]), "signature": tuple(c["id"] for c in self.offer), "at": now}
                self.absent_count = 0
                self.status = "Clique detectado; aguardando fechamento da seleção"
                return

    def export(self):
        return {"match_key": self.match_key, "champion": self.champion,
                "selected": copy.deepcopy(self.selected), "history_partial": self.history_partial,
                "rounds": copy.deepcopy(self.rounds)}

    def view(self, now):
        return {**self.export(), "offer": copy.deepcopy(self.offer),
                "offer_stale": bool(self.offer and now - self.offer_seen_at > 3),
                "api_stale": now - self.api_seen_at > 4,
                "pending": copy.deepcopy(self.pending), "status": self.status,
                "panel": self.visible, "revision": self.revision,
                "validation_pending": self.validation_pending}
