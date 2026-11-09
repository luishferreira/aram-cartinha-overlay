"""Compact native presentation. All measurements target the calibrated 1080p layout."""
from tools.live.source_cards import metric, percent, fit_combo_text

BG = "#111b25"
EDGE = "#283743"
TEXT = "#e8eef3"
MUTED = "#96a9b8"
MINT = "#91e4c5"
GOLD = "#ddc28d"
CENTERS = (592, 960, 1328)
COMBO_Y = 808  # Native reroll buttons occupy the area below the cards, through y~800.
SOURCES = (("AK", "aramkit"), ("BL", "blitz"), ("OP", "opgg"), ("AM", "arammayhem_champion_tier"))


def tiers(card):
    sources = card.get("sources", {}) if card and not card.get("error") else {}
    return tuple(metric(sources.get(source), "tier") or "—" for _, source in SOURCES)


def combo_summary(card):
    if not card or card.get("error"):
        return None
    evidence = card.get("combo_evidence", {})
    observed, notes = evidence.get("observed", []), evidence.get("editorial", [])
    if observed:
        combo = observed[0]
        kind = "par" if combo["kind"] == "observed_pair" else "trio"
        source = "ARAMKit" if combo["source"] == "aramkit" else "ARAMGG"
        if not combo["missing_members"]:
            return (kind.capitalize()+" observado", "Com "+" + ".join(combo["member_names"]),
                    source+" · combinação registrada", MINT)
        if combo["selected_members"] or not any(n["selected_members"] for n in notes):
            context = "Com "+" + ".join(combo["member_names"])+" · " if combo["member_names"] else ""
            return ("Caminho de "+kind, "Falta "+" + ".join(combo["missing_names"]), context+source, GOLD)
    if notes:
        note = notes[0]
        title = "Nota com "+" + ".join(note["member_names"]) if note["member_names"] else "Nota para o campeão"
        # Keep the actual source text rather than inventing a mechanical summary.
        text = "Outras citadas: "+" + ".join(note["other_names"]) if note["other_names"] else note["text"]
        return (title, text, "ARAM Mayhem · editorial (EN)", "#afc4dc")
    return None


def comparison_rows(cards):
    """Each column retains its own source and context; no pooled score."""
    values = [[] for _ in range(9)]
    for card in cards:
        valid = card and not card.get("error")
        sources = card.get("sources", {}) if valid else {}
        kit, gg = sources.get("aramkit"), sources.get("aramgg")
        rank = card.get("opgg_popularity") if valid else None
        observed = card.get("combo_evidence", {}).get("observed", []) if valid else []
        complete = next((c for c in observed if not c["missing_members"]), None)
        combo_wr = "—"
        if complete:
            source = "AK" if complete["source"] == "aramkit" else "GG"
            combo_wr = percent(metric(complete, "win_rate"))+" · "+source
        elif observed:
            combo_wr = "Incompleto"
        column = (*tiers(card), percent(metric(kit, "win_rate")), percent(metric(gg, "win_rate")),
                  percent(metric(kit, "pick_rate")),
                  f'#{rank["rank"]}/{rank["published_entries"]}' if rank else "—", combo_wr)
        for row, value in zip(values, column):
            row.append(value)
    labels = ("Tier ARAMKit", "Tier Blitz", "Tier OP.GG", "Tier AM · por raridade",
              "WR ARAMKit", "WR ARAMGG · global", "Popularidade ARAMKit", "Pick OP.GG · calculado",
              "WR do conjunto observado")
    return list(zip(labels, values))


class CompactCards:
    def __init__(self, root, host, demo=False, log=lambda *a, **k: None, on_close=None):
        import tkinter as tk
        self.tk, self.root, self.host, self.demo, self.log = tk, root, host, demo, log
        self.headers, self.combos, self.native = [], [], []
        self.content = [None]*3
        self.names = ["—"]*3
        self.cards = [None]*3
        self.details_open = False
        self.detail_content = None
        for slot in range(3):
            window, frame, handle = self.window(310, 78)
            grades = tk.Frame(frame, bg=BG)
            grades.pack(fill="x")
            letters = []
            for column, (label, _) in enumerate(SOURCES):
                group = tk.Frame(grades, bg=BG)
                group.grid(row=0, column=column, sticky="ew")
                grades.columnconfigure(column, weight=1, uniform="sources")
                tk.Label(group, text=label, bg=BG, fg=MUTED, font=("Segoe UI", 8)).pack(side="left")
                letter = tk.Label(group, text="—", bg=BG, fg=MUTED, font=("Segoe UI", 18, "bold"))
                letter.pack(side="left", padx=(3, 0))
                letters.append(letter)
            tk.Frame(frame, bg=EDGE, height=1).pack(fill="x", pady=(3, 3))
            pick = tk.Label(frame, text="Pick OP —", bg=BG, fg=TEXT, font=("Segoe UI", 9))
            pick.pack(fill="x")
            self.headers.append((window, {"letters": letters, "pick": pick}, handle))

            window, frame, handle = self.window(310, 100)
            accent = tk.Frame(frame, bg=MINT, width=2)
            accent.pack(side="left", fill="y", padx=(0, 8))
            stack = tk.Frame(frame, bg=BG)
            stack.pack(side="left", fill="both", expand=True)
            widgets = {"accent": accent}
            for key, size, weight, color in (("kind", 8, "bold", MINT), ("value", 10, "bold", TEXT),
                                             ("source", 8, "normal", MUTED)):
                label = tk.Label(stack, text="", bg=BG, fg=color, font=("Segoe UI", size, weight),
                                 justify="left", anchor="w", wraplength=270, padx=0, pady=0)
                label.pack(fill="x", pady=(0, 4 if key != "source" else 0))
                widgets[key] = label
            self.combos.append((window, widgets, handle))
            if demo:
                window, frame, handle = self.window(310, 500)
                frame.configure(bg="#0c2028")
                tk.Label(frame, text="SIMULAÇÃO", bg="#0c2028", fg=GOLD,
                         font=("Segoe UI", 9)).pack(pady=(30, 25))
                tk.Label(frame, text="✦", bg="#0c2028", fg=GOLD, font=("Segoe UI", 48)).pack(pady=28)
                name = tk.Label(frame, bg="#0c2028", fg="#e6ddbe", font=("Georgia", 16, "bold"),
                                wraplength=275, justify="center")
                name.pack(pady=(28, 18))
                self.native.append((window, name, handle))

        self.control_width = 300 if demo else 190
        self.control, frame, self.control_handle = self.window(self.control_width, 32, interactive=True, padding=0)
        self.button = tk.Button(frame, text="Comparar fontes", command=self.toggle, bg="#1b2b38", fg=TEXT,
                                activebackground="#294354", activeforeground=TEXT, relief="flat", bd=0,
                                font=("Segoe UI", 9), cursor="hand2", takefocus=False)
        self.button.pack(side="left", fill="both", expand=True)
        if demo and on_close:
            tk.Button(frame, text="Fechar prévia ×", command=on_close, bg="#273440", fg=TEXT,
                      activebackground="#3b4a57", activeforeground=TEXT, relief="flat", bd=0,
                      font=("Segoe UI", 9), cursor="hand2", takefocus=False).pack(side="right", fill="y", padx=(1, 0))
        self.details, frame, self.details_handle = self.window(1046, 260, interactive=True)
        top = tk.Frame(frame, bg=BG)
        top.pack(fill="x", pady=(0, 6))
        tk.Label(top, text="Comparar fontes", bg=BG, fg=TEXT,
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        tk.Button(top, text="Fechar ×", command=self.toggle, bg=BG, fg=MUTED, relief="flat", bd=0,
                  font=("Segoe UI", 9), cursor="hand2", takefocus=False).pack(side="right")
        table = tk.Frame(frame, bg=BG)
        table.pack(fill="both", expand=True)
        table.columnconfigure(0, minsize=230)
        self.detail_names, self.detail_cells = [], []
        tk.Label(table, text="Indicador", bg=BG, fg=MUTED, anchor="w",
                 font=("Segoe UI", 9)).grid(row=0, column=0, sticky="ew", pady=(0, 7))
        for i in range(3):
            table.columnconfigure(i+1, weight=1, uniform="cards")
            name = tk.Label(table, text="—", bg=BG, fg=TEXT, font=("Segoe UI", 9, "bold"),
                            wraplength=245, justify="center")
            name.grid(row=0, column=i+1, sticky="ew", pady=(0, 7))
            self.detail_names.append(name)
        for i, (label, _) in enumerate(comparison_rows([None]*3), 1):
            tk.Label(table, text=label, bg=BG, fg=MUTED, font=("Segoe UI", 9),
                     anchor="w").grid(row=i, column=0, sticky="ew")
            cells = []
            for column in range(1, 4):
                cell = tk.Label(table, text="—", bg=BG, fg=MINT if i==9 else TEXT,
                                font=("Segoe UI", 9), anchor="center")
                cell.grid(row=i, column=column, sticky="ew")
                cells.append(cell)
            self.detail_cells.append(cells)

    def window(self, width, height, interactive=False, padding=9):
        tk = self.tk
        window = tk.Toplevel(self.root)
        window.withdraw()
        window.overrideredirect(True)
        window.attributes("-topmost", True)
        window.attributes("-alpha", .98)
        window.configure(bg=EDGE)
        window.geometry(f"{width}x{height}+0+0")
        frame = tk.Frame(window, bg=BG, padx=padding, pady=6 if padding else 0)
        frame.pack(fill="both", expand=True, padx=1, pady=1)
        window.update_idletasks()
        handle = self.host.make_overlay(window.winfo_id(), show=False, interactive=interactive)
        return window, frame, handle

    def show(self, window, x, y, width, height, interactive=False):
        geometry = f"{width}x{height}{x:+d}{y:+d}"
        if getattr(window, "_compact_geometry", None) != geometry:
            window.geometry(geometry)
            window._compact_geometry = geometry
        if window.state() == "withdrawn":
            window.deiconify()
            self.host.make_overlay(window.winfo_id(), interactive=interactive)

    def clipped(self, label, text, lines=1, width=270):
        font = label.cget("font")
        return fit_combo_text([text], lambda value: int(self.root.tk.call("font", "measure", font, value)), width, lines)

    def hide_slot(self, slot):
        self.cards[slot], self.names[slot] = None, "—"
        for collection in (self.headers, self.combos, self.native):
            if slot<len(collection) and collection[slot][0].state() != "withdrawn":
                collection[slot][0].withdraw()

    def render_slot(self, slot, name, card, game):
        ox, oy = (game["x"], game["y"]) if game else (0, 0)
        x = ox+CENTERS[slot]-155
        self.cards[slot], self.names[slot] = card, name
        window, widgets, _ = self.headers[slot]
        grades, summary = tiers(card), combo_summary(card)
        rank = card.get("opgg_popularity") if card and not card.get("error") else None
        pick = f'Pick OP  #{rank["rank"]}' if rank else "Pick OP  —"
        if card and card.get("error"):
            pick = "Base local indisponível"
        content = (grades, pick, summary, name)
        if self.content[slot] != content:
            for label, tier in zip(widgets["letters"], grades):
                color = MUTED if tier=="—" else MINT if tier.startswith("S") else "#b3cbe7" if tier.startswith("A") else "#c2a4b1"
                label.configure(text=tier, fg=color)
            widgets["pick"].configure(text=pick)
            if summary:
                _, cw, _ = self.combos[slot]
                kind, value, source, color = summary
                cw["kind"].configure(text=self.clipped(cw["kind"], kind), fg=color)
                cw["value"].configure(text=self.clipped(cw["value"], value, 2))
                cw["source"].configure(text=self.clipped(cw["source"], source))
                cw["accent"].configure(bg=color)
            if self.demo:
                self.native[slot][1].configure(text=name)
            self.content[slot] = content
        self.show(window, x, oy+108, 310, 78)
        if summary and not self.details_open:
            self.show(self.combos[slot][0], x, oy+COMBO_Y, 310, 100)
        elif self.combos[slot][0].state() != "withdrawn":
            self.combos[slot][0].withdraw()
        if self.demo:
            self.show(self.native[slot][0], x, oy+192, 310, 500)

    def toggle(self):
        self.details_open = not self.details_open
        self.button.configure(text="Recolher comparação" if self.details_open else "Comparar fontes")
        self.log("comparison_toggled", expanded=self.details_open, demo=self.demo)

    def render_controls(self, visible, game, root_x, root_y, root_height):
        if not visible or not any(name!="—" for name in self.names):
            self.details_open = False
            self.button.configure(text="Comparar fontes")
            self.control.withdraw()
            self.details.withdraw()
            return
        self.show(self.control, root_x, root_y+root_height+5, self.control_width, 32, interactive=True)
        if not self.details_open:
            self.details.withdraw()
            return
        rows = comparison_rows(self.cards)
        content = (tuple(self.names), tuple(tuple(values) for _, values in rows))
        if content != self.detail_content:
            for label, name in zip(self.detail_names, self.names):
                label.configure(text=self.clipped(label, name, 2, 240))
            for cells, (_, values) in zip(self.detail_cells, rows):
                for cell, value in zip(cells, values):
                    cell.configure(text=value)
            self.detail_content = content
        ox, oy = (game["x"], game["y"]) if game else (0, 0)
        self.show(self.details, ox+437, oy+816, 1046, 260, interactive=True)

    def metadata(self):
        return {"tag_hwnds": [int(w[2]) for w in self.headers],
                "combo_hwnds": [int(w[2]) for w in self.combos],
                "native_hwnds": [int(w[2]) for w in self.native],
                "control_hwnd": int(self.control_handle), "details_hwnd": int(self.details_handle)}
