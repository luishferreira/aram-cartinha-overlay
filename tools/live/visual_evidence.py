"""Passive visual evidence. No input events, game memory or synthetic actions."""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if not getattr(sys,'frozen',False):
    sys.path.insert(0, str(ROOT / "data/local/overlay-deps"))
import numpy as np
from PIL import Image

from tools.live.common import normalized


def panel_state(image):
    if image.size != (1920, 1080):
        return "uncalibrated"
    a = np.asarray(image)
    dark = sum(bool(np.all(a[y, x, :3] < [45, 60, 65])) for x in (590, 960, 1328) for y in (400, 620))
    top = sum(bool(np.all(a[260, x, :3] > [100, 85, 70])) for x in (440, 808, 1176))
    # Silver cards have dark grey lower borders; the old gold-oriented threshold
    # classified them as unknown and therefore rejected otherwise valid choices.
    lower = sum(bool(np.all(a[y, x, :3] > [50, 50, 50])) for x in (440, 808, 1176) for y in (500, 650))
    return "present" if dark >= 5 and top == 3 and lower >= 4 else "absent" if dark <= 2 or top == 0 else "unknown"


def scoreboard_visible(image):
    if image.size != (1920, 1080):
        return False
    # Native scoreboard background, not text from third-party overlays.
    a = np.asarray(image)
    return sum(bool(np.all(a[y, x, :3] < [40, 65, 70]))
               for x in (600, 900, 1100, 1400) for y in (390, 465, 540, 615)) >= 14


class AnimationDetector:
    """Experimental temporal classifier; emits slot only after the panel disappears."""
    def __init__(self):
        self.baseline = None
        self.armed_at = None
        self.last_present = 0
        self.pending = None
        self.hit_slot = None
        self.hits = 0
        self.faces = None
        self.previous_faces = None
        self.stable_faces = 0

    def reset(self):
        self.__init__()

    def update(self, image, now, panel):
        a = np.asarray(image)
        if image.size != (1920, 1080):
            return None
        stats = []
        for x in (470, 840, 1210):
            c = a[270:640, x:x + 240, :3]
            stats.append((float(c.mean()), float((c.max(axis=2) > 190).mean())))
        if panel == "present":
            if self.baseline is None or now - self.last_present > 2:
                self.baseline = stats
                self.armed_at = now
                self.faces = [descriptor(image.crop((x-77,235,x+77,390))) for x in (592,960,1328)]
            self.last_present = now
        if self.baseline is None:
            return None
        if now - self.last_present > 2:
            self.reset()
            return None
        slot = max(range(3), key=lambda s: stats[s][1])
        current_faces = [descriptor(image.crop((x-77,235,x+77,390))) for x in (592,960,1328)]
        others = [s for s in range(3) if s != slot]
        hit = (now - self.armed_at >= .3 and stats[slot][0] > self.baseline[slot][0] + 35
               and stats[slot][1] > max(.10, self.baseline[slot][1] + .07)
               and stats[slot][1] - max(stats[s][1] for s in others) > .09
               and all(stats[s][1] < .09 for s in others))
        if hit:
            self.hits = self.hits + 1 if slot == self.hit_slot else 1
            self.hit_slot = slot
            if self.hits >= 2 and self.pending is None:
                self.pending = (slot, now)
        else:
            self.hits = 0
        if self.pending:
            candidate = self.pending[0]
            others_visible = False
            for index,x in enumerate((592,960,1328)):
                if index == candidate:
                    continue
                current = current_faces[index]
                reference = self.faces[index]
                if reference is not None and current is not None and float((reference*current).sum()) > .75:
                    others_visible = True
            # A per-card reroll leaves other card faces intact. It cannot become
            # a pending acquisition that survives until a later real selection.
            if others_visible or now-self.pending[1] > 1:
                self.pending = None
                self.hits = 0
        # Refresh after stable rerolls, so the next comparison is against the
        # current faces rather than the original three cards of this round.
        stable = panel == "present" and self.previous_faces is not None and all(
            a is not None and b is not None and float((a*b).sum()) > .98
            for a,b in zip(current_faces,self.previous_faces))
        self.stable_faces = self.stable_faces+1 if stable else 0
        if self.stable_faces >= 2 and not hit and self.pending is None:
            self.faces = current_faces
            self.baseline = stats
        self.previous_faces = current_faces
        if self.pending and panel == "absent" and now - self.pending[1] >= .12:
            selected_slot = self.pending[0]
            self.reset()
            return selected_slot
        return None


def descriptor(image):
    a = np.asarray(image.convert("L").resize((24, 24), Image.Resampling.LANCZOS), dtype=float)
    a -= a.mean()
    norm = float(np.linalg.norm(a))
    return a / norm if norm > 30 else None


class IconBank:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.templates = {}
        self.offer_templates = {}
        self.offer_sources = {}
        self.cache = {}
        for p in self.folder.glob("*.png"):
            try:
                self.add(int(p.stem.split("-")[0]), Image.open(p), save=False)
            except (OSError, ValueError):
                pass
        for p in self.folder.glob("offer-*.png"):
            try:
                with Image.open(p) as image:
                    self.add_offer(int(p.stem.split("-")[1]),image.copy(),save=False)
            except (OSError,ValueError):
                pass

    def add(self, card_id, image, save=True):
        feature = descriptor(image)
        if feature is None:
            return
        variants = self.templates.setdefault(card_id, [])
        if any(float((feature * previous).sum()) > .995 for previous in variants):
            return
        if len(variants) < 8:
            if save:
                image.save(self.folder / f"{card_id}-{len(variants)}.png")
            variants.append(feature)
            self.cache.clear()

    def add_offer(self, card_id, patch, save=True):
        sources = self.offer_sources.setdefault(card_id,[])
        fingerprint = descriptor(patch)
        if fingerprint is None or any(float((fingerprint*p).sum()) > .98 for p in sources) or len(sources)>=2:
            return
        vectors = []
        for size in (120,132,144,156,168,180):
            for dx in (-8,0,8):
                for dy in (-24,-16,-8,0,8,16,24):
                    x,y=116+dx,116+dy
                    value=descriptor(patch.crop((x-size//2,y-size//2,x+size//2,y+size//2)))
                    if value is not None:
                        vectors.append(value.ravel())
        if save:
            patch.save(self.folder/f"offer-{card_id}-{len(sources)}.png")
        sources.append(fingerprint)
        if vectors:
            self.offer_templates.setdefault(card_id,[]).append(np.asarray(vectors,dtype=np.float32))
        self.cache.clear()

    def learn_offer(self, image, cards):
        for c in cards:
            x = (592, 960, 1328)[c["slot"]]
            self.add(c["id"], image.crop((x - 72, 240, x + 72, 384)))
            self.add_offer(c["id"],image.crop((x-116,196,x+116,428)))

    def restore_offers(self, folder):
        for p in Path(folder).glob("*.json"):
            try:
                cards=json.loads(p.read_text(encoding="utf-8"))
                with Image.open(p.with_suffix(".png")) as crop:
                    image=Image.new("RGB",(1920,1080))
                    image.paste(crop,(430,190))
                self.learn_offer(image,cards)
            except (OSError,ValueError,KeyError):
                continue

    def match(self, image, candidates):
        key=(image.size,image.tobytes(),tuple(sorted(set(candidates))))
        if key in self.cache:
            return self.cache[key]
        scores = []
        # Exclude the TAB frame; try small variations in how its glyph is padded.
        queries = [descriptor(image.crop((p, p, image.width-p, image.height-p))) for p in (0, 1, 2, 3)]
        if image.width >= 32:
            queries = []
            for size in (18,20,22,24):
                for dx in (-2,0,2,4):
                    for dy in (-2,0,2,4):
                        x,y=image.width//2+dx,image.height//2+dy
                        queries.append(descriptor(image.crop((x-size//2,y-size//2,x+size//2,y+size//2))))
        matrix = np.asarray([q.ravel() for q in queries if q is not None],dtype=np.float32)
        for card_id in set(candidates):
            values = [float((q*t).sum()) for q in queries if q is not None
                      for t in self.templates.get(card_id, [])]
            if matrix.size:
                values.extend(float((templates @ matrix.T).max()) for templates in self.offer_templates.get(card_id,[]))
            if values:
                scores.append((max(values), card_id))
        scores.sort(reverse=True)
        advanced = image.width >= 32
        threshold = .86 if advanced else .78
        result = None
        if scores and scores[0][0] >= threshold and (len(scores)==1 or scores[0][0]-scores[1][0] >= .12):
            result = {"id":scores[0][1],"similarity":round(scores[0][0],4)}
        if len(self.cache) >= 64:
            self.cache.clear()
        self.cache[key] = result
        return result


def self_tab_cells(screen, player_names):
    matches = []
    for line in screen.get("ocr_lines", []):
        words = line.get("words", [])
        if not words or normalized(line.get("text")) not in player_names:
            continue
        x, y = min(w["x"] for w in words), min(w["y"] for w in words)
        if not 305 <= y <= 665:
            continue
        side = "left" if 650 <= x <= 950 else "right" if 1200 <= x <= 1495 else None
        if side:
            matches.append((side, round(y + 14)))
    if len(matches) != 1:
        return []
    side, y = matches[0]
    xs = (299, 328, 357) if side == "left" else (1559, 1588, 1617)
    return [(x-12, y+dy-12, x+12, y+dy+12) for dy in (0, 32) for x in xs]


def tooltip_card(screen, names, cursor, cells):
    if cursor is None:
        return None
    hovered = [i for i, (l,t,r,b) in enumerate(cells) if l <= cursor[0] <= r and t <= cursor[1] <= b]
    if len(hovered) != 1:
        return None
    candidates = {}
    fragments = []
    for line in screen.get("ocr_lines", []):
        words = [w for w in line.get("words", []) if 430 <= w["x"] <= 1495 and 710 <= w["y"] <= 960]
        if words:
            fragments.append((min(w["y"] for w in words), " ".join(w["text"] for w in sorted(words, key=lambda w:w["x"]))))
    fragments.sort()
    for i, (_, text) in enumerate(fragments):
        variants = [text] + ([text + " " + fragments[i+1][1]] if i+1 < len(fragments) else [])
        for text in variants:
            for card_id, label in names.get(normalized(text), {}).items():
                candidates[card_id] = {"id": card_id, "catalog_name": label, "tab_index": hovered[0]}
    return next(iter(candidates.values())) if len(candidates) == 1 else None


class EvidenceLedger:
    """Persist unresolved rounds, alternatives and per-TAB-cell corrections."""
    def __init__(self, state=None):
        state = state or {}
        self.rounds = copy.deepcopy(state.get("rounds", []))
        self.selected = copy.deepcopy(state.get("selected", []))
        self.last_signature = None

    def offer(self, cards, level, now):
        signature = tuple(c["id"] for c in cards)
        gap = now-self.rounds[-1].get("last_seen", now) if self.rounds else 0
        if signature == self.last_signature:
            self.rounds[-1]["last_seen"] = now
            return
        self.last_signature = signature
        if not self.rounds or self.rounds[-1].get("resolved") or (gap > 30 and self.rounds[-1].get("level") != level):
            self.rounds.append({"key": f"round-{len(self.rounds)+1}", "level": level, "offers": [], "resolved": False})
        current = self.rounds[-1]
        current["last_seen"] = now
        if not any(tuple(c["id"] for c in o["cards"]) == signature for o in current["offers"]):
            current["offers"].append({"at": now, "cards": copy.deepcopy(cards)})

    def record(self, card, source, now, *, round_key=None, tab_index=None, score=None):
        previous = next((c for c in self.selected if tab_index is not None and c.get("tab_index") == tab_index), None)
        if previous is None and round_key:
            previous = next((c for c in self.selected if c.get("round_key") == round_key), None)
        if previous is None:
            previous = next((c for c in self.selected if c["id"] == card["id"]), None)
        if previous is None and tab_index is not None:
            # A named/icon-identified alternative can correct a unique earlier
            # hypothesis from that offer, even before its TAB position was known.
            alternatives = []
            for r in self.rounds:
                if card["id"] in {c["id"] for o in r["offers"] for c in o["cards"]}:
                    alternatives.extend(c for c in self.selected if c.get("round_key") == r["key"]
                                        and c.get("tab_index") is None and c.get("evidence") != "tooltip_name")
            if len(alternatives) == 1:
                previous = alternatives[0]
        if previous is None:
            previous = copy.deepcopy(card)
            previous["evidence_log"] = []
            self.selected.append(previous)
        # A tooltip is stronger than icon similarity or selection animation.
        if previous.get("evidence") == "tooltip_name" and source != "tooltip_name":
            return False
        if previous.get("evidence") == "tab_icon" and source == "selection_animation":
            return False
        old_id = previous["id"]
        round_key = round_key or previous.get("round_key")
        if old_id != card["id"]:
            previous.setdefault("corrections", []).append({"old_id": old_id, "new_id": card["id"], "source": source, "at": now})
        evidence = {"source": source, "id": card["id"], "at": now}
        if score is not None:
            evidence["similarity"] = score
        previous.update(id=card["id"], catalog_name=card["catalog_name"], evidence=source,
                        confidence="visual_name" if source == "tooltip_name" else "visual_icon" if source == "tab_icon" else "inferred", selected_at=now)
        if not previous.get("evidence_log") or previous["evidence_log"][-1].get("source") != source or old_id != card["id"]:
            previous.setdefault("evidence_log", []).append(evidence)
        if tab_index is not None:
            previous["tab_index"] = tab_index
            # Merge an earlier animation-only record of this same card, rather
            # than displaying it twice when a tooltip corrects another slot.
            duplicates = [c for c in self.selected if c is not previous and c["id"] == card["id"] and c.get("tab_index") is None]
            for duplicate in duplicates:
                previous["evidence_log"] = duplicate.get("evidence_log", []) + previous["evidence_log"]
                self.selected.remove(duplicate)
        if round_key:
            previous["round_key"] = round_key
        for r in self.rounds:
            ids = {c["id"] for o in r["offers"] for c in o["cards"]}
            if r["key"] == round_key or (not r.get("resolved") and card["id"] in ids):
                r.update(resolved=True, selected_id=card["id"])
                previous.setdefault("round_key", r["key"])
                break
        return True

    def candidates(self):
        return {c["id"]: c for r in self.rounds for o in r["offers"] for c in o["cards"]}

    def export(self):
        return {"rounds": copy.deepcopy(self.rounds), "selected": copy.deepcopy(self.selected)}
