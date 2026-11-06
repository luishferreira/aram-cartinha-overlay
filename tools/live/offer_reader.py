"""Initial title-region reader calibrated on a real 1920x1080 Mayhem offer.

This is acquisition only. No tiers, recommendations, clicks or imported GEP events.
"""
import json
from pathlib import Path

from tools.live.common import normalized


def load_names(root):
    from tools.live.data_paths import resource
    names = {}
    for filename,pack_name in (("opgg-augments-ptbr.json","augments-ptbr.json"),
                               ("opgg-augments-enus.json","augments-enus.json")):
        data = json.loads(resource(root,pack_name,Path('research/public-snapshots')/filename).read_text(encoding="utf-8"))
        for row in data["data"]:
            names.setdefault(normalized(row["name"]), {})[row["id"]] = row["name"]
    return names


def read_offer(screen, names):
    if screen.get("status") != "captured" or screen.get("ocr_status") != "recognized":
        return {"status": "unobserved", "reason": "no_usable_frame"}
    width, height = screen.get("width"), screen.get("height")
    if (width, height) != (1920, 1080):
        return {"status": "unobserved", "reason": "layout_not_calibrated"}
    # Native titles observed at y=436. Excludes OP.GG's titles at y~142,
    # Blitz's tier badges at y~700 and the catalog widget on the left.
    slots = [(430, 755), (795, 1125), (1165, 1495)]
    cards = []
    failures = []
    for slot, (left, right) in enumerate(slots):
        fragments = []
        for line in screen.get("ocr_lines", []):
            words = [word for word in line.get("words", [])
                     if left <= word["x"] + word["width"] / 2 <= right
                     and 400 <= word["y"] + word["height"] / 2 <= 478]
            if words:
                words.sort(key=lambda word: word["x"])
                fragments.append((min(word["y"] for word in words), " ".join(word["text"] for word in words)))
        fragments.sort()
        candidates = {}
        for i, (_, text) in enumerate(fragments):
            for value in [text] + ([text + " " + fragments[i + 1][1]] if i + 1 < len(fragments) else []):
                for augment_id, name in names.get(normalized(value), {}).items():
                    candidates[augment_id] = {"id": augment_id, "catalog_name": name,
                                              "ocr_text": value, "slot": slot}
        if len(candidates) != 1:
            failures.append({"slot": slot, "candidate_count": len(candidates),
                             "title_fragments": [text for _, text in fragments]})
        else:
            cards.append(next(iter(candidates.values())))
    if failures:
        return {"status": "unobserved", "reason": "incomplete_or_ambiguous_titles",
                **failures[0], "recognized_slots": cards, "failed_slots": failures}
    if len({card["id"] for card in cards}) != 3:
        return {"status": "unobserved", "reason": "duplicate_candidates"}
    return {"status": "observed", "source": "native_title_regions", "layout": "1920x1080-v1",
            "cards": cards, "temporal_confirmation": "not_implemented"}
