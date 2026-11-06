"""Read installed packages and selected diagnostic markers without executing them.

Only targeted source excerpts and log marker counts/timestamps are archived.
Cookies, tokens, settings and complete logs are deliberately outside this probe.
"""
import gzip
import hashlib
import json
import re
import struct
from datetime import datetime, timezone
from pathlib import Path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inspect_asar(path, members):
    result = {"path": str(path), "members": []}
    with path.open("rb") as stream:
        result["sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
        stream.seek(0)
        header = struct.unpack("<4I", stream.read(16))
        tree = json.loads(stream.read(header[3]))
        for member, terms in members.items():
            entry = tree
            for part in member.split("/"):
                entry = entry["files"][part]
            if entry.get("unpacked"):
                data = Path(str(path) + ".unpacked").joinpath(member).read_bytes()
            else:
                stream.seek(8 + header[1] + int(entry["offset"]))
                data = stream.read(entry["size"])
            text_data = gzip.decompress(data) if data[:2] == b"\x1f\x8b" else data
            text = text_data.decode("utf-8")
            record = {"path": member, "sha256": digest(data), "text_sha256": digest(text_data)}
            if member == "package.json":
                package = json.loads(text)
                record["package"] = {key: package.get(key) for key in ("name", "version", "main")}
            record["markers"] = []
            for term in terms:
                matches = list(re.finditer(re.escape(term), text))
                record["markers"].append({
                    "term": term, "count": len(matches),
                    "excerpts": [{"character_offset": m.start(),
                                  "text": text[max(0, m.start() - 100):m.end() + 650]}
                                 for m in matches[:3]],
                })
            result["members"].append(record)
    return result


def inspect_logs(root):
    markers = ["[MAYHEM][GEP] confirmed mayhem augments",
               "[MAYHEM][GEP] published augments", "[MAYHEM][GEP] picked augment",
               "[MAYHEM][GEP] ignored payload because trusted augment triplet was not available",
               "package ready: gep"]
    results = []
    for name in ("boot.log", "main.log", "main.1.log"):
        path = root / name
        if not path.exists():
            continue
        data = path.read_bytes()
        lines = data.decode("utf-8", errors="replace").splitlines()
        result = {"path": str(path), "read_bytes_sha256": digest(data), "markers": []}
        for marker in markers:
            matches = [line for line in lines if marker in line]
            result["markers"].append({"marker": marker, "count": len(matches),
                "last_timestamps": [re.match(r"^\[[^\]]+\]", line).group(0)
                                    for line in matches[-3:] if re.match(r"^\[[^\]]+\]", line)]})
        results.append(result)
    return results


if __name__ == "__main__":
    local = Path.home() / "AppData/Local/Programs"
    opgg = inspect_asar(local / "OP.GG/resources/app.asar", {
        "package.json": [],
        "assets/main/main.js": ["this.app=c.overwolf", "registerOverwolfPackageManager=function",
            "createLoLMayhemGepEvent=function", "isTrustedLoLMayhemGepEvent=function",
            "publishLoLMayhemGepEvent=function", "onGameEventsPackageReady=function",
            '"picked_augment"===e.key', "lol:mayhem.gepEvent", "ocr", "tesseract"],
    })
    blitz = inspect_asar(local / "Blitz/resources/app.asar", {
        "package.json": [],
        "src/gameHandlers/lol/index.js": ["dllToInject", "sendArenaAugmentsData", "ARENA_EVENT"],
        "src/injection-manager.js": ["lolModule:", "lolFlutterModule:"],
    })
    output = {"recorded_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Static package excerpts plus existing application diagnostic markers; no target execution or live attach.",
        "opgg": opgg, "blitz": blitz,
        "diagnostics": inspect_logs(Path.home() / "AppData/Roaming/opgg-electron-app/logs"),
        "limits": ["Logs are historical application-authored evidence, not a live instrumentation capture.",
                   "Counts can contain repeated notifications and do not count unique offers or games.",
                   "Negative marker searches apply only to the selected source members.",
                   "GEP's internal acquisition mechanism is not established by these excerpts."]}
    destination = Path(__file__).parent / "augment-recognition" / "installed-evidence-20261030.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise SystemExit("Snapshot already exists; choose a new destination to preserve it.")
    destination.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(destination)
