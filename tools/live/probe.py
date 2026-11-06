"""Diagnostic collector for the active player, game payload and visible game OCR.

No recommendation engine, injected modules or other overlay's event stream.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import ssl
import subprocess
import time
import urllib.request
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.live.common import normalized
PRIVATE_KEYS = {"summonername", "riotid", "riotidgamename", "riotidtagline", "puuid", "summonerid"}


def player_identity(player):
    full = player.get("riotId")
    if not full and player.get("riotIdGameName") and player.get("riotIdTagLine"):
        full = f"{player['riotIdGameName']}#{player['riotIdTagLine']}"
    if not full and "#" in str(player.get("summonerName", "")):
        full = player["summonerName"]
    return full


def identify_champion(payload, catalog):
    """Resolve self uniquely; never choose the first champion/name match."""
    active = payload.get("activePlayer") or {}
    players = payload.get("allPlayers") or []
    identity = player_identity(active)
    method = "full_riot_id"
    if identity:
        candidates = [p for p in players if player_identity(p) == identity]
    else:
        candidates = []
    if not candidates:
        name = active.get("riotIdGameName") or active.get("summonerName")
        # A full ID never falls back to a different tagged player with the same game name.
        if identity:
            return {"status": "unresolved", "reason": "full_identity_not_found"}
        candidates = [p for p in players if name and (
            p.get("riotIdGameName") == name or p.get("summonerName") == name)]
        method = "unique_legacy_name"
    if len(candidates) != 1:
        return {"status": "unresolved", "reason": "ambiguous_player" if candidates else "player_not_found"}
    player = candidates[0]
    raw = str(player.get("rawChampionName") or "")
    key = raw.removeprefix("game_character_displayname_")
    matches = [champion for champion in catalog if normalized(champion["key"]) == normalized(key)] if key else []
    champion_method = "raw_champion_key"
    if not matches:
        matches = [champion for champion in catalog if normalized(champion["name"]) == normalized(player.get("championName"))]
        champion_method = "unique_catalog_name"
    if len(matches) != 1:
        return {"status": "unresolved", "reason": "champion_not_in_catalog"}
    champion = matches[0]
    return {"status": "resolved", "champion_id": champion["id"], "champion_key": champion["key"],
            "name": champion["name"], "player_match": method, "champion_match": champion_method,
            "level": player.get("level"), "item_ids": [i.get("itemID") for i in player.get("items", [])]}


def redact(value):
    if isinstance(value, dict):
        return {key: "[redacted]" if key.lower() in PRIVATE_KEYS else redact(child)
                for key, child in value.items()}
    if isinstance(value, list):
        return [redact(child) for child in value]
    return value


def augment_paths(value, path="$", result=None):
    result = [] if result is None else result
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if re.search(r"augment|mayhem|arena", key, re.I):
                result.append(child_path)
            augment_paths(child, child_path, result)
    elif isinstance(value, list):
        for i, child in enumerate(value):
            augment_paths(child, f"{path}[{i}]", result)
    return result


def fetch_local():
    # Self-signed TLS exception and proxy bypass are limited to this literal loopback URL.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(context=ssl._create_unverified_context()))
    with opener.open("https://127.0.0.1:2999/liveclientdata/allgamedata", timeout=2) as response:
        return json.load(response)


def capture(destination, ocr, *, native_titles=False, input_image=None, session=None):
    if os.name != "nt":
        return {"status": "unsupported_platform"}
    if session is not None and input_image is not None and ocr:
        return session.recognize(input_image,native_titles=native_titles)
    executable = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    command = [str(executable), "-NoProfile", "-File", str(Path(__file__).with_name("capture_game.ps1")),
               "-OutputPath", str(destination)]
    if ocr:
        command.append("-Ocr")
    if native_titles:
        command.append("-NativeTitles")
    if input_image is not None:
        command.extend(["-InputImage", str(input_image)])
    result = subprocess.run(command, capture_output=True, encoding="utf-8", errors="replace",
                            timeout=25, creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        return {"status": "capture_error", "detail": result.stderr[-1500:]}
    return json.loads(result.stdout.lstrip("\ufeff"))


def snapshot(directory, catalog, *, take_capture=False, ocr=False, augment_names=None):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    record = {"recorded_at": stamp, "champion": {"status": "unresolved"},
              "offered_augments": {"status": "not_validated"},
              "owned_augments": {"status": "not_validated"}}
    try:
        payload = fetch_local()
        record["api_status"] = "available"
        record["champion"] = identify_champion(payload, catalog)
        record["game"] = payload.get("gameData")
        record["augment_field_paths"] = augment_paths(payload)
        # Rune IDs remain in this evidence; they are not assumed to be owned augment IDs.
        sanitized = json.dumps(redact(payload), ensure_ascii=False, indent=2) + "\n"
        payload_path = directory / f"{stamp}.payload.json"
        payload_path.write_text(sanitized, encoding="utf-8")
        record["payload"] = {"path": payload_path.name, "sha256": hashlib.sha256(sanitized.encode()).hexdigest()}
    except Exception as error:
        record["api_status"] = "unavailable"
        record["api_error_type"] = type(error).__name__
    if take_capture:
        try:
            record["screen"] = capture(directory / f"{stamp}.png", ocr)
            if augment_names is not None:
                from tools.live.offer_reader import read_offer
                record["offered_augments"] = read_offer(record["screen"], augment_names)
        except Exception as error:
            record["screen"] = {"status": "capture_error", "error_type": type(error).__name__}
    (directory / f"{stamp}.observation.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", action="store_true", help="Capture only the foreground game client area")
    parser.add_argument("--ocr", action="store_true", help="Run installed Windows OCR on captured frames")
    parser.add_argument("--seconds", type=float, default=0, help="Bounded collection duration; default one observation")
    parser.add_argument("--interval", type=float, default=5)
    args = parser.parse_args()
    catalog = json.loads((ROOT / "research/champion-snapshots/champion-catalog.json").read_text(encoding="utf-8"))["champions"]
    from tools.live.offer_reader import load_names
    augment_names = load_names(ROOT)
    run = ROOT / "research/live-validation" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    run.mkdir(parents=True, exist_ok=False)
    print(f"Session: {run}", flush=True)
    start = time.monotonic()
    while True:
        record = snapshot(run, catalog, take_capture=args.capture or args.ocr, ocr=args.ocr, augment_names=augment_names)
        summary = {key: record.get(key) for key in ("recorded_at", "api_status", "champion", "offered_augments")}
        if "screen" in record:
            screen = record["screen"]
            summary["screen"] = {"status": screen.get("status"), "ocr_status": screen.get("ocr_status"),
                                 "ocr_line_count": len(screen.get("ocr_lines") or [])}
        print(json.dumps(summary, ensure_ascii=False), flush=True)
        if time.monotonic() - start >= args.seconds:
            break
        time.sleep(max(1, args.interval))


if __name__ == "__main__":
    main()
