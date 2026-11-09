"""Mayhem debug overlay: local API, native-screen OCR and explicit inferred picks."""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes as W
import hashlib
import json
import os
import shutil
from pathlib import Path
import sys
import threading
import time
import traceback
from datetime import datetime, timezone

SOURCE_ROOT = Path(__file__).resolve().parents[2]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))
from tools.app_paths import app_root,local_root
from tools.app_identity import set_app_id,apply_icon
ROOT = app_root()

from tools.live.offer_reader import load_names, read_offer
from tools.live.probe import capture, fetch_local, identify_champion
from tools.live.tracking import DebugTracker
from tools.live.windows_host import WindowsHost
from tools.live.session_history import load_history, process_key
from tools.live.source_cards import SourceCards, combo_rows
from tools.live.compact_overlay import CompactCards
from tools.live.hotkeys import OverlayHotkeys
from tools.live.data_paths import resource


def atomic_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


class DebugApp:
    def __init__(self, args):
        self.args = args
        self.host = WindowsHost(exclude_from_capture=not args.demo)
        self.stop = threading.Event()
        self.lock = threading.RLock()
        self.tracker = DebugTracker()
        self.enabled = True
        self.offer_tags = [None]*3
        self.last_game = None
        self.read_status = "Aguardando API local e janela do LoL"
        self.started = time.monotonic()
        self.started_wall = time.time()
        self.persisted = None
        self.last_acquisition = None
        self.last_failure_sample = None
        self.failure_sample_count = 0
        self.first_offer_saved = False
        self.panel_width = 300
        self.panel_height = 180
        self.local = local_root(ROOT)/'debug-overlay'
        self.local.mkdir(parents=True, exist_ok=True)
        (self.local / "matches").mkdir(exist_ok=True)
        run = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        self.run = self.local / "runs" / run
        self.run.mkdir(parents=True)
        self.events = (self.run / "events.jsonl").open("a", encoding="utf-8", buffering=1)
        self.source_cards = SourceCards(ROOT,log=self.log)
        catalog = json.loads(resource(ROOT,'champions.json','research/champion-snapshots/champion-catalog.json').read_text(encoding="utf-8"))
        self.catalog = catalog["champions"]
        rows = json.loads(resource(ROOT,'augments-ptbr.json','research/public-snapshots/opgg-augments-ptbr.json').read_text(encoding="utf-8"))["data"]
        self.labels = {row["id"]: row["name"] for row in rows}
        self.names = load_names(ROOT)
        import tkinter as tk
        set_app_id()
        self.root = tk.Tk()
        apply_icon(self.root)
        self.root.withdraw()
        self.root.title("Mayhem Debug")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.94)
        self.root.configure(bg="#101722")
        self.root.geometry(f"{self.panel_width}x{self.panel_height}+{args.x}+{args.y}")
        frame = tk.Frame(self.root, bg="#101722", padx=10, pady=8)
        self.frame_widget = frame
        frame.pack(fill="both", expand=True)
        self.widgets = {}
        specs = [("champion", "#ffffff", 16, "bold"),
                 ("selected_title", "#78bfff", 9, "bold"),
                 ("selected", "#ffd887", 10, "normal"),
                 ("legend", "#96a9b8", 8, "normal"),
                 ("keys", "#97a7bc", 8, "normal")]
        for key, color, size, weight in specs:
            label = tk.Label(frame, text="", fg=color, bg="#101722", font=("Segoe UI", size, weight),
                             anchor="w", justify="left", wraplength=self.panel_width - 20)
            label.pack(fill="x", pady=(0, 3))
            self.widgets[key] = label
        self.root.update_idletasks()
        self.hwnd = self.host.make_overlay(self.root.winfo_id(), show=False)
        self.compact = CompactCards(self.root, self.host, demo=args.demo, log=self.log, on_close=self.close)
        if not args.demo:
            self.log("overlay_capture_exclusion", windows=self.host.capture_exclusions,
                     all_excluded=all(self.host.capture_exclusions.values()))
        self.card_windows = self.compact.headers
        self.tag_drawn = [None]*3
        self.source_drawn = [None]*3
        atomic_json(self.run / "window.json", {"pid": os.getpid(), "hwnd": int(self.hwnd), "demo": args.demo,
                                              "layout": "compact-v1", **self.compact.metadata()})
        self.hotkeys = OverlayHotkeys()
        self.launcher = None
        if not args.demo:
            from tools.launcher.window import Launcher
            self.launcher = Launcher(self.root,self.stop,self.close,root=ROOT)
        self.hotkey_retry_at = time.monotonic()+2
        self.hotkey_error = len(self.hotkeys.registered) != 2
        if self.hotkey_error:
            self.log("hotkey_unavailable", registered=sorted(self.hotkeys.registered), errors=self.hotkeys.errors)
        else:
            self.log("hotkeys_ready", target="owned_message_window")
        if args.demo:
            self.seed_demo()
        else:
            threading.Thread(target=self.worker, daemon=True, name="mayhem-collector").start()
            from tools.items.watcher import ItemSetWatcher
            self.item_sets = ItemSetWatcher(self.stop, ROOT, log=self.log)
            threading.Thread(target=self.item_sets.run, daemon=True, name="mayhem-item-sets").start()
        self.root.after(20, self.tick)

    def log(self, kind, **values):
        if self.events.closed:
            return
        if "at" in values:
            values["monotonic_at"] = values.pop("at")
        self.events.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(), "kind": kind, **values}, ensure_ascii=False) + "\n")

    def seed_demo(self):
        now = time.monotonic()
        self.tracker.set_match("demo", {"name": "Master Yi", "champion_id": 11, "level": 12}, now)
        self.tracker.selected = [{"id": key, "catalog_name": self.labels[key], "confidence": "demo"} for key in (2141, 1029)]
        self.tracker.offer = [{"id": key, "catalog_name": self.labels[key], "slot": slot} for slot, key in enumerate((3086, 1058, 1015))]
        self.tracker.offer_seen_at = now
        self.offer_tags = [{**card,"generation":0,"observed_at":now,"detected_at":now,
                            "sampled_at":now,"panel_seen_at":now} for card in self.tracker.offer]
        self.tracker.status = "SIMULAÇÃO — não são dados da partida atual"
        self.read_status = "Preview visual; coletor desligado"

    def worker(self):
        try:
            from tools.live.visual_collector import VisualCollector
            self.collector = VisualCollector(self)
            self.collector.run()
        except Exception:
            self.log("collector_start_error", detail=traceback.format_exc())

    def record_acquisition(self, screen, reading, api_status, game_time):
        diagnostic = {"api": api_status, "game_time": game_time,
                      "screen": screen.get("status"), "panel": screen.get("panel_visibility"),
                      "reading": reading, "ocr_region": screen.get("ocr_region")}
        fingerprint = json.dumps({k: v for k, v in diagnostic.items() if k != "game_time"}, sort_keys=True)
        if fingerprint != self.last_acquisition:
            self.log("acquisition", **diagnostic)
            self.last_acquisition = fingerprint
        source = self.run / "latest-frame.png"
        if screen.get("status") != "captured" or not source.exists():
            return
        if reading.get("status") == "observed" and not self.first_offer_saved:
            shutil.copyfile(source, self.run / "first-offer.png")
            atomic_json(self.run / "first-offer.json", diagnostic)
            self.first_offer_saved = True
        if reading.get("status") != "observed" and screen.get("panel_visibility") == "present":
            signature = hashlib.sha256(fingerprint.encode()).hexdigest()
            if signature != self.last_failure_sample:
                slot = self.failure_sample_count % 8
                shutil.copyfile(source, self.run / f"failed-offer-{slot}.png")
                atomic_json(self.run / f"failed-offer-{slot}.json", diagnostic)
                self.failure_sample_count += 1
                self.last_failure_sample = signature

    def persist(self):
        state = self.tracker.export()
        fingerprint = json.dumps(state, ensure_ascii=False, sort_keys=True)
        if fingerprint == self.persisted:
            return
        atomic_json(self.local / "state.json", state)
        if state["match_key"]:
            atomic_json(self.local / "matches" / f"{state['match_key']}.json", state)
        self.persisted = fingerprint

    def tick(self):
        if self.stop.is_set():
            return
        try:
            for action in self.hotkeys.drain():
                if action == 1:
                    self.enabled = not self.enabled
                    self.log("hotkey_toggle", enabled=self.enabled)
                elif action == 2:
                    self.log("hotkey_exit")
                    self.close()
                    return
            if self.hotkey_error and time.monotonic()>=self.hotkey_retry_at:
                self.hotkeys.retry()
                self.hotkey_retry_at=time.monotonic()+2
                self.hotkey_error=len(self.hotkeys.registered)!=2
                if not self.hotkey_error:
                    self.log("hotkeys_ready", target="owned_message_window", recovered=True)
            game = self.host.foreground_game()
            now = time.monotonic()
            stop_request = self.local / "stop.request"
            if stop_request.exists() and stop_request.stat().st_mtime >= self.started_wall:
                self.close()
                return
            show_request = self.local/'show.request'
            if self.launcher and show_request.exists() and show_request.stat().st_mtime>=self.started_wall:
                show_request.unlink()
                self.launcher.show()
            if self.launcher:
                self.launcher.overlay_active = self.enabled
            with self.lock:
                view = self.tracker.view(now)
                tags = [dict(t) if t else None for t in self.offer_tags]
            show = self.enabled and (bool(game) or self.args.demo)
            if show:
                if self.root.state() == "withdrawn":
                    self.root.deiconify()
                    self.host.make_overlay(self.root.winfo_id())
                if game:
                    # Right edge stays left of native title regions, preventing OCR feedback.
                    x = game["x"] + min(max(0, self.args.x), 20)
                    self.root.geometry(f"{self.panel_width}x{self.panel_height}{x:+d}{game['y'] + self.args.y:+d}")
                self.render(view)
            elif self.root.state() != "withdrawn":
                self.root.withdraw()
            self.render_card_tags(tags,game,self.enabled,now,view)
            if self.args.seconds and now - self.started >= self.args.seconds:
                self.close()
                return
        except Exception:
            self.log("ui_error", detail=traceback.format_exc())
        self.root.after(20, self.tick)

    def render_card_tags(self, tags, game, enabled, now, view):
        champion=view.get("champion") or {}
        champion_id=champion.get("champion_id")
        selected=tuple(sorted({c["id"] for c in view.get("selected",[])}))
        for slot,(window,widgets,handle) in enumerate(self.card_windows):
            tag = tags[slot]
            visible = enabled and (game is not None or self.args.demo) and tag is not None
            if visible and not self.args.demo:
                visible = now-tag.get("observed_at",0) <= 4
            if not visible:
                self.compact.hide_slot(slot)
                self.tag_drawn[slot] = None
                self.source_drawn[slot] = None
                continue
            text = self.labels.get(tag["id"], tag["catalog_name"])
            card = self.source_cards.get(champion_id, tag["id"], selected)
            self.compact.render_slot(slot, text, card, game)
            contextual = combo_rows(card)
            signature = (tag["id"],tag["generation"])
            if self.tag_drawn[slot] != signature:
                window.update_idletasks()
                displayed_at = time.monotonic()
                self.log("offer_tag_visible",slot=slot,card_id=tag["id"],generation=tag["generation"],
                         panel_to_display_ms=round((displayed_at-tag["panel_seen_at"])*1000),
                         capture_to_display_ms=round((displayed_at-tag["sampled_at"])*1000),
                         detection_to_display_ms=round((displayed_at-tag["detected_at"])*1000),demo=self.args.demo)
                self.tag_drawn[slot] = signature
            source_signature=(champion_id,tag["id"],selected,card.get("data_run")) if card else None
            if card and not card.get("error") and self.source_drawn[slot] != source_signature:
                self.source_drawn[slot]=source_signature
                self.log("source_card_visible",card_id=tag["id"],champion_id=champion_id,
                         selected_ids=list(selected),data_run=card["data_run"],load_ms=card.get("loaded_ms"),
                         layout="compact-v1", contextual_rows=contextual,demo=self.args.demo)
                path=self.run/f"source-card-{champion_id}-{tag['id']}.json"
                atomic_json(path,card)

        self.compact.render_controls(enabled and (game is not None or self.args.demo), game,
                                     self.root.winfo_x(), self.root.winfo_y(), self.panel_height)

    def render(self, view):
        champion = view["champion"]
        values = {
            "champion": ((champion["name"] + (" ?" if view["api_stale"] and not self.args.demo else "")) if champion else "—") + (" · SIMULAÇÃO" if self.args.demo else ""),
            "selected_title": "ESCOLHIDAS",
            "selected": "\n".join(f"{'✓' if card.get('confidence') in ('visual_name','visual_icon') else '~'} {self.labels.get(card['id'], card.get('catalog_name', str(card['id'])))}" for card in view["selected"]) or "—",
            "legend": "AK ARAMKit · BL Blitz · OP OP.GG\nAM ARAM Mayhem · tiers do campeão",
            "keys": "Ctrl+F8 ocultar · Ctrl+F9 sair",
        }
        if view.get("validation_pending") and view.get("panel") != "present":
            values["selected"] += "\n? validar no TAB + mouse"
        for key, value in values.items():
            if self.widgets[key].cget("text") != value:
                self.widgets[key].configure(text=value)
        self.root.update_idletasks()
        height = min(max(100, self.frame_widget.winfo_reqheight()), max(100, self.root.winfo_screenheight() - 60))
        if height != self.panel_height:
            self.panel_height = height
            self.root.geometry(f"{self.panel_width}x{height}{self.root.winfo_x():+d}{self.root.winfo_y():+d}")

    def close(self):
        self.stop.set()
        self.source_cards.close()
        collector = getattr(self,"collector",None)
        if collector is not None:
            collector.ocr_session.close()
        self.hotkeys.close()
        self.root.destroy()

    def run_loop(self):
        try:
            self.root.mainloop()
        finally:
            self.stop.set()
            self.events.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", help="Clearly labeled visual preview; no game reads")
    parser.add_argument("--launcher-demo", action="store_true", help="Preview pre-game with simulated selection; no game reads")
    parser.add_argument("--stop", action="store_true", help="Request that existing debug windows exit")
    parser.add_argument("--seconds", type=float, default=0, help="Optional auto-exit duration")
    parser.add_argument("--x", type=int, default=15)
    parser.add_argument("--y", type=int, default=30)
    args = parser.parse_args()
    if args.launcher_demo:
        from tools.launcher.window import preview
        preview()
        return
    local = local_root(ROOT)/'debug-overlay'
    local.mkdir(parents=True, exist_ok=True)
    if args.stop:
        (local / "stop.request").touch()
        return
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes, kernel.CreateMutexW.restype = [W.LPVOID, W.BOOL, W.LPCWSTR], W.HANDLE
    ctypes.set_last_error(0)
    mutex = kernel.CreateMutexW(None, False, "Local\\MayhemDebugOverlay" + ("Preview" if args.demo else ""))
    if ctypes.get_last_error() == 183:
        if not args.demo:
            (local/'show.request').touch()
        kernel.CloseHandle.argtypes = [W.HANDLE]
        kernel.CloseHandle(mutex)
        return
    try:
        DebugApp(args).run_loop()
    except Exception:
        with (local / "startup-error.log").open("a", encoding="utf-8") as log:
            traceback.print_exc(file=log)
        raise
    finally:
        kernel.CloseHandle.argtypes = [W.HANDLE]
        kernel.CloseHandle(mutex)


if __name__ == "__main__":
    main()
