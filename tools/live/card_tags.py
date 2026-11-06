"""Display-only first readings; never promote partial OCR to an acquired card."""
import time

from tools.live.visual_evidence import descriptor

CENTERS = (592, 960, 1328)


def features(image, slot):
    x = CENTERS[slot]
    return (descriptor(image.crop((x-77,235,x+77,390))),
            descriptor(image.crop((x-155,400,x+155,478))))


def compatible(reference, current):
    return all(a is not None and b is not None and float((a*b).sum()) >= threshold
               for a,b,threshold in zip(reference,current,(.88,.90)))


class CardTags:
    def __init__(self):
        self.tags = [None]*3
        self.references = [None]*3
        self.generations = [0]*3
        self.starts = [0.0]*3
        self.panel = False
        self.last_present = 0

    def frame(self, image, panel, now):
        # A single rerolled card can make the global panel classifier uncertain.
        # Keep unaffected positions only while their own title/icon still match.
        if panel == "present":
            self.last_present = now
        grace = .6 if panel == "unknown" else .12
        visible = panel == "present" or (self.panel and now-self.last_present <= grace)
        if visible and not self.panel:
            self.starts = [now]*3
        for slot in range(3):
            if self.tags[slot] is not None and (not visible or not compatible(self.references[slot],features(image,slot))):
                self.tags[slot] = self.references[slot] = None
                self.generations[slot] += 1
                self.starts[slot] = now
        self.panel = visible

    def publish(self, reading, source_image, sampled_at, current_image, panel, now=None):
        now = time.monotonic() if now is None else now
        if panel != "present" or now-sampled_at > 4:
            return []
        cards = reading.get("cards",[]) if reading.get("status")=="observed" else reading.get("recognized_slots",[])
        published = []
        for card in cards:
            slot = card["slot"]
            ref = features(source_image,slot)
            if not compatible(ref,features(current_image,slot)):
                continue
            previous = self.tags[slot]
            changed = previous is None or previous["id"] != card["id"]
            if changed:
                if previous is not None:
                    self.generations[slot] += 1
                self.tags[slot] = {**card, "generation":self.generations[slot],
                                   "detected_at":now, "panel_seen_at":self.starts[slot] or sampled_at,
                                   "sampled_at":sampled_at}
                published.append(dict(self.tags[slot]))
            self.tags[slot]["observed_at"] = now
            self.references[slot] = ref
        return published
