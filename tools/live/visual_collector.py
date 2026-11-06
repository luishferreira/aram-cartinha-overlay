"""Separate fast visual sampling from slow API/OCR work; process-scoped evidence."""
import copy
from collections import deque
import json
import threading
import time

from tools.live.probe import capture, fetch_local, identify_champion, player_identity
from tools.live.offer_reader import read_offer
from tools.live.session_history import load_history, process_key
from tools.live.common import normalized
from tools.live.visual_evidence import (AnimationDetector, EvidenceLedger, IconBank, descriptor,
                                      panel_state, scoreboard_visible, self_tab_cells, tooltip_card)
from PIL import ImageGrab
import numpy as np
from tools.live.card_tags import CardTags
from tools.live.ocr_session import OcrSession


class VisualCollector:
    def __init__(self, app):
        self.app = app
        self.latest = None
        self.sequence = 0
        self.key = None
        self.ledger = EvidenceLedger()
        self.detector = AnimationDetector()
        self.buffer = deque(maxlen=60)
        self.cards = None
        self.reference = None
        self.before_effect = None
        self.before_effect_at = 0
        self.offer_started = 0
        self.cells = []
        self.cells_at = 0
        self.player_names = set()
        self.tooltip_signature = None
        self.tooltip_count = 0
        self.icon_votes = {}
        self.last_icon_scan = 0
        self.last_panel = "unknown"
        self.sample_count = 0
        self.rate_at = time.monotonic()
        self.last_error = None
        self.last_selection_at = 0
        self.tags = CardTags()
        self.ocr_session = OcrSession()
        self.last_reading = None
        self.api_payload = None
        self.api_at = 0
        self.last_tab_diagnostic = None

    def bind(self, game):
        key = process_key(game)
        if key == self.key:
            return
        restored = None
        try:
            restored = load_history(self.app.local, game)
        except (OSError, ValueError):
            self.app.log("restore_error")
        self.app.tracker.set_match(key, None, time.monotonic(), restored)
        self.ledger = EvidenceLedger(restored)
        self.bank = IconBank(self.app.local / "icons" / key)
        self.bank.restore_offers(self.app.local / "offers" / key)
        self.detector.reset()
        self.cards = self.reference = self.before_effect = None
        self.before_effect_at = 0
        self.cells, self.player_names = [], set()
        self.cells_at = 0
        self.icon_votes.clear()
        self.tooltip_signature, self.tooltip_count = None, 0
        self.buffer.clear()
        self.key = key
        self.last_selection_at = 0
        self.tags = CardTags()
        self.app.offer_tags = [None]*3
        self.last_reading = None
        self.api_payload, self.api_at = None, 0
        self.last_tab_diagnostic = None

    def sync(self):
        state = self.ledger.export()
        self.app.tracker.selected = state["selected"]
        self.app.tracker.rounds = state["rounds"]
        self.app.tracker.validation_pending = any(not r.get("resolved") for r in state["rounds"])
        self.app.persist()

    def snapshot_event(self, kind, image, **values):
        # Bound disk usage: eight event bundles per process run, plus offer references.
        slot = getattr(self, "event_count", 0) % 8
        self.event_count = getattr(self, "event_count", 0) + 1
        folder = self.app.run / f"visual-event-{slot}"
        folder.mkdir(exist_ok=True)
        image.save(folder / "event.png")
        for p in folder.glob("before-*.jpg"):
            p.unlink()
        for i, (_, frame) in enumerate(list(self.buffer)[::3]):
            frame.save(folder / f"before-{i:02}.jpg")
        (folder / "evidence.json").write_text(json.dumps({"kind": kind, **values}, ensure_ascii=False, indent=2), encoding="utf-8")
        self.app.log(kind, **values, sample=str(folder.name))

    def run(self):
        self.app.log("visual_collector_ready", target_fps=30, button_capture=False,
                     acquisition_version="visual-v3-tab-alignment")
        threading.Thread(target=self.ocr_loop, daemon=True, name="mayhem-ocr").start()
        while not self.app.stop.is_set():
            began = time.monotonic()
            try:
                game = self.app.host.foreground_game()
                if not game or (game["width"], game["height"]) != (1920, 1080):
                    with self.app.lock:
                        self.latest = None
                        self.detector.reset()
                        self.cells_at = 0
                        self.before_effect = None
                        self.tags = CardTags()
                        self.app.offer_tags = [None]*3
                    self.app.stop.wait(.15)
                    continue
                image = ImageGrab.grab(bbox=(game["x"], game["y"], game["x"]+1920, game["y"]+1080), all_screens=True)
                after = self.app.host.foreground_game()
                if not after or process_key(after) != process_key(game):
                    continue
                now = time.monotonic()
                panel = panel_state(image)
                tab = panel != "present" and scoreboard_visible(image)
                cursor = self.app.host.cursor_position(game)
                with self.app.lock:
                    self.bind(game)
                    self.sequence += 1
                    self.latest = (self.key, self.sequence, now, image, panel, tab, cursor)
                    self.app.tracker.visible = panel
                    self.tags.frame(image,panel,now)
                    self.app.offer_tags = copy.deepcopy(self.tags.tags)
                    selected_slot = self.detector.update(image, now, panel)
                    if panel == "present":
                        self.update_offer_context(image, now)
                    if selected_slot is not None:
                        self.animation_choice(selected_slot, image, now)
                    if panel == "absent" and self.last_panel == "present":
                        self.offer_started = now
                    # A visually closed panel never means 'nothing was selected'.
                    if panel == "absent" and now-self.offer_started > .4:
                        self.app.tracker.offer = None
                    if tab and self.cells and now-self.cells_at < 4 and now-self.last_icon_scan > .1:
                        self.scan_icons(image, now)
                        self.last_icon_scan = now
                    if not tab:
                        self.cells_at = 0
                        self.icon_votes.clear()
                    self.last_panel = panel
                    self.buffer.append((now, image.crop((420,170,1500,770)).resize((540,300))))
                    self.sample_count += 1
                    if now-self.rate_at >= 10:
                        self.app.log("capture_rate", fps=round(self.sample_count/(now-self.rate_at),1), target=30)
                        self.sample_count, self.rate_at = 0, now
            except Exception as error:
                label = (type(error).__name__, str(error))
                if label != self.last_error:
                    self.app.log("visual_error", error_type=label[0], detail=label[1])
                    self.last_error = label
                self.app.stop.wait(.5)
            self.app.stop.wait(max(0, 1/30-(time.monotonic()-began)))

    def update_offer_context(self, image, now):
        if not self.reference:
            return
        similarities = []
        for x in (592,960,1328):
            box = (x-77,235,x+77,390)
            a, b = descriptor(self.reference.crop(box)), descriptor(image.crop(box))
            similarities.append(float((a*b).sum()) if a is not None and b is not None else 0)
        if min(similarities) >= .85:
            self.before_effect, self.before_effect_at = image, now
        elif any(s >= .85 for s in similarities):
            # A partial icon change is consistent with a per-card reroll, not
            # the simultaneous loss of all three faces during selection.
            self.before_effect = None

    def animation_choice(self, slot, image, now):
        self.last_selection_at = now
        card = None
        # Protect against a reroll occurring while the OCR result is in flight.
        if self.cards and self.reference and self.before_effect and now-self.before_effect_at <= .6:
            similarities = []
            for x in (592,960,1328):
                box = (x-77,235,x+77,390)
                a, b = descriptor(self.reference.crop(box)), descriptor(self.before_effect.crop(box))
                similarities.append(float((a*b).sum()) if a is not None and b is not None else 0)
            if min(similarities) >= .85:
                card = self.cards[slot]
        if card:
            key = self.ledger.rounds[-1]["key"] if self.ledger.rounds else None
            self.ledger.record(card, "selection_animation", now, round_key=key)
            self.sync()
        else:
            self.app.tracker.validation_pending = True
            if not self.ledger.rounds or self.ledger.rounds[-1].get("resolved"):
                self.ledger.rounds.append({"key": f"round-{len(self.ledger.rounds)+1}", "level": None, "offers": [], "resolved": False})
            self.sync()
        self.snapshot_event("visual_selection", image, slot=slot, card_id=card["id"] if card else None, at=now)
        self.cards = self.reference = None
        self.ledger.last_signature = None

    def scan_icons(self, image, now):
        candidates = self.ledger.candidates()
        unknown = False
        occupied_indices = []
        for index, box in enumerate(self.cells):
            icon = image.crop(box)
            occupied = float(np.asarray(icon.convert("L").crop((2,2,22,22))).std()) > 18
            if occupied:
                occupied_indices.append(index)
            else:
                self.icon_votes[index]=(None,0)
                continue
            l,t,r,b=box
            match = self.bank.match(image.crop((l-6,t-6,r+6,b+6)), candidates)
            signature = match["id"] if match else None
            previous, count = self.icon_votes.get(index, (None,0))
            count = count+1 if previous == signature else 1
            self.icon_votes[index] = (signature,count)
            existing = next((c for c in self.ledger.selected if c.get("tab_index") == index), None)
            if occupied and existing is None:
                unknown = True
            if signature is None or count < 3:
                continue
            if existing and existing["id"] == signature and existing.get("confidence") in ("visual_name","visual_icon"):
                continue
            if self.ledger.record(candidates[signature], "tab_icon", now, tab_index=index, score=match["similarity"]):
                self.sync()
                self.snapshot_event("tab_icon_choice", image, card_id=signature, tab_index=index, similarity=match["similarity"])
        known_indices = {c.get("tab_index") for c in self.ledger.selected}
        if occupied_indices and len(occupied_indices) >= len(self.ledger.rounds) and all(i in known_indices for i in occupied_indices):
            changed = False
            for r in self.ledger.rounds:
                if not r.get("resolved") and not r.get("offers"):
                    r.update(resolved=True, resolution="complete_tab_inventory", selected_id=None)
                    changed = True
            if changed:
                self.sync()
        self.app.tracker.validation_pending = unknown or any(not r.get("resolved") for r in self.ledger.rounds)

    def ocr_loop(self):
        last_sequence = -1
        while not self.app.stop.is_set():
            try:
                with self.app.lock:
                    frame = self.latest
                if frame is None or frame[1] == last_sequence:
                    self.app.stop.wait(.15)
                    continue
                key, sequence, sampled_at, image, panel, tab, cursor = frame
                last_sequence = sequence
                if time.monotonic()-self.api_at >= 1:
                    try:
                        fresh_payload = fetch_local()
                    except Exception:
                        fresh_payload = None
                    with self.app.lock:
                        if key != self.key:
                            continue
                        self.api_payload = fresh_payload
                        self.api_at = time.monotonic()
                payload = self.api_payload
                with self.app.lock:
                    if key != self.key:
                        continue
                    if payload:
                        champion = identify_champion(payload, self.app.catalog)
                        if champion.get("status") == "resolved":
                            self.app.tracker.set_match(key, champion, time.monotonic())
                        active = payload.get("activePlayer") or {}
                        names = [active.get("riotIdGameName"), active.get("summonerName"), player_identity(active)]
                        self.player_names = {normalized(n.split("#")[0]) for n in names if n}
                if payload and payload.get("gameData", {}).get("gameMode") not in (None,"KIWI"):
                    self.app.stop.wait(.5)
                    continue
                if panel != "present" and not tab:
                    self.app.stop.wait(.3)
                    continue
                path = self.app.run / "ocr-input.bmp"
                image.save(path)
                ocr_started = time.monotonic()
                screen = capture(path, True, native_titles=not tab, input_image=path, session=self.ocr_session)
                ocr_ms = round((time.monotonic()-ocr_started)*1000)
                screen.update(status="captured", width=1920, height=1080, panel_visibility=panel)
                reading = read_offer(screen, self.app.names) if not tab else {"status":"unobserved", "reason":"scoreboard"}
                with self.app.lock:
                    if key != self.key or self.latest is None or time.monotonic()-sampled_at > 5:
                        continue
                    if not tab:
                        current = self.latest
                        published = self.tags.publish(reading,image,sampled_at,current[3],current[4])
                        self.app.offer_tags = copy.deepcopy(self.tags.tags)
                        for tag in published:
                            self.app.log("offer_tag_detected",slot=tag["slot"],card_id=tag["id"],
                                         generation=tag["generation"],
                                         panel_to_detection_ms=round((tag["detected_at"]-tag["panel_seen_at"])*1000),
                                         capture_to_detection_ms=round((tag["detected_at"]-sampled_at)*1000),ocr_ms=ocr_ms)
                    if reading.get("status") == "observed":
                        self.accept_offer(reading, image, sampled_at)
                    elif tab:
                        diagnostic=self.accept_tab(screen, image, cursor, sampled_at)
                        reading.update(diagnostic)
                        signature=json.dumps(diagnostic,sort_keys=True)
                        if signature != self.last_tab_diagnostic:
                            self.app.log("tab_read",ocr_ms=ocr_ms,**diagnostic)
                            self.last_tab_diagnostic=signature
                    self.app.persist()
                fingerprint = json.dumps(reading,sort_keys=True)
                if fingerprint != self.last_reading:
                    # Diagnostic PNG compression must not block the fast capture
                    # thread or the GUI for every repeated OCR of the same offer.
                    image.save(self.app.run / "latest-frame.png")
                    self.app.record_acquisition(screen, reading, "available" if payload else "unavailable", (payload or {}).get("gameData",{}).get("gameTime"))
                    self.last_reading = fingerprint
            except Exception as error:
                self.app.log("ocr_error", error_type=type(error).__name__, detail=str(error))
                self.app.stop.wait(.5)
            self.app.stop.wait(.12)

    def accept_offer(self, reading, image, sampled_at):
        cards = reading["cards"]
        if sampled_at < self.last_selection_at:
            self.bank.learn_offer(image, cards)
            if self.ledger.rounds and not self.ledger.rounds[-1].get("offers"):
                self.ledger.rounds[-1]["offers"].append({"at": sampled_at, "cards": copy.deepcopy(cards)})
            self.sync()
            return
        level = (self.app.tracker.champion or {}).get("level")
        self.ledger.offer(cards, level, sampled_at)
        self.cards, self.reference = copy.deepcopy(cards), image.copy()
        self.bank.learn_offer(image, cards)
        self.app.tracker.frame(reading, "present", sampled_at)
        # Each combination has an immutable title/icon reference, including rerolls.
        signature = "-".join(str(c["id"]) for c in cards)
        path = self.app.local / "offers" / self.key
        path.mkdir(parents=True, exist_ok=True)
        reference = path / f"{signature}.png"
        if not reference.exists():
            image.crop((430,190,1495,725)).save(reference)
            (path / f"{signature}.json").write_text(json.dumps(cards,ensure_ascii=False,indent=2),encoding="utf-8")
            self.app.log("offer_reference", cards=cards, path=str(reference))
        self.sync()

    def accept_tab(self, screen, image, cursor, sampled_at):
        cells = self_tab_cells(screen, self.player_names)
        if not cells:
            self.cells_at = 0
            self.tooltip_signature, self.tooltip_count = None, 0
            return {"self_row_found":False,"tooltip_id":None,"tooltip_stability":0}
        self.cells, self.cells_at = cells, time.monotonic()
        result = tooltip_card(screen, self.app.names, cursor, cells)
        signature = (result["id"],result["tab_index"]) if result else None
        self.tooltip_count = self.tooltip_count+1 if signature == self.tooltip_signature else 1
        self.tooltip_signature = signature
        diagnostic={"self_row_found":True,"tooltip_id":result["id"] if result else None,
                    "tooltip_stability":min(self.tooltip_count,2) if result else 0}
        if result and self.tooltip_count >= 2:
            index = result["tab_index"]
            existing = next((c for c in self.ledger.selected if c.get("tab_index") == index),None)
            if existing and existing["id"] == result["id"] and existing.get("evidence") == "tooltip_name":
                return diagnostic
            self.ledger.record(result,"tooltip_name",sampled_at,tab_index=index)
            self.bank.add(result["id"],image.crop(cells[index]))
            self.sync()
            self.snapshot_event("tooltip_choice",image,card_id=result["id"],tab_index=index)
        return diagnostic
