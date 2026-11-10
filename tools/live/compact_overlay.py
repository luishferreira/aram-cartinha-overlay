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


def score_text(card,coverage=False):
    score=(card or {}).get('keitinha_score',{}) if not (card or {}).get('error') else {}
    value=score.get('value')
    if value is None:return '—'
    text=f'{value:.1f}'.replace('.',',')
    if coverage:text+=f' · {score["available_sources"]}/4 fontes'
    return text


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
    """Show consensus separately while preserving the original source indicators."""
    values = [[] for _ in range(10)]
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
        column = (score_text(card,coverage=True), *tiers(card), percent(metric(kit, "win_rate")), percent(metric(gg, "win_rate")),
                  percent(metric(kit, "pick_rate")),
                  f'#{rank["rank"]}/{rank["published_entries"]}' if rank else "—", combo_wr)
        for row, value in zip(values, column):
            row.append(value)
    labels = ("Keitinha Score · 0–100", "Tier ARAMKit", "Tier Blitz", "Tier OP.GG", "Tier AM · por raridade",
              "WR ARAMKit", "WR ARAMGG · global", "Popularidade ARAMKit", "Pick OP.GG · calculado",
              "WR do conjunto observado")
    return list(zip(labels, values))


def observation_sections(card):
    """Full eligible evidence, with editorial membership separate from requirements."""
    if card is None:
        return [("", "Carregando observações…")]
    if card.get("error"):
        return [("", "Base local indisponível")]
    evidence = card.get("combo_evidence", {})
    sections = []
    for note in evidence.get("editorial", []):
        lines = [note["text"]]
        if note.get("member_names"):
            lines.append("Já escolhidas e citadas: "+" + ".join(note["member_names"]))
        if note.get("other_names"):
            lines.append("Outras cartas citadas: "+" + ".join(note["other_names"]))
        sections.append(("ARAM Mayhem · nota editorial (EN)", "\n\n".join(lines)))
    for combo in evidence.get("observed", []):
        kind = "Par" if combo["kind"] == "observed_pair" else "Trio"
        source = "ARAMKit" if combo["source"] == "aramkit" else "ARAMGG"
        lines = []
        if combo.get("member_names"):
            lines.append("Com: "+" + ".join(combo["member_names"]))
        missing = combo.get("missing_names", [])
        if missing:
            lines.append("Falta: "+" + ".join(missing))
        else:
            lines.append("Completo com esta opção · WR observado "+percent(metric(combo, "win_rate")))
        sections.append((source+" · "+kind.lower()+" observado"+(" · incompleto" if missing else ""),
                         "\n".join(lines)))
    return sections or [("", "Sem observações salvas para esta carta neste campeão.")]


class CompactCards:
    def __init__(self, root, host, demo=False, log=lambda *a, **k: None, on_close=None):
        import tkinter as tk
        self.tk, self.root, self.host, self.demo, self.log = tk, root, host, demo, log
        self.headers, self.combos, self.native = [], [], []
        self.content = [None]*3
        self.names = ["—"]*3
        self.cards = [None]*3
        self.details_open = False
        self.notes_open = False
        self.detail_content = None
        self.notes_content = None
        for slot in range(3):
            window, frame, handle = self.window(310, 78)
            frame.configure(pady=5)
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
            row=tk.Frame(frame,bg=BG);row.pack(fill='x')
            pick = tk.Label(row, text="Pick OP —", bg=BG, fg=TEXT, font=("Segoe UI", 9))
            pick.pack(side='left')
            score=tk.Label(row,text='Keitinha Score  —',bg=BG,fg=MINT,font=('Segoe UI',9,'bold'))
            score.pack(side='right')
            self.headers.append((window, {"letters": letters, "pick": pick, "score":score}, handle))

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

        self.control_width = 420 if demo else 300
        self.control, frame, self.control_handle = self.window(self.control_width, 32, interactive=True, padding=0)
        self.button = tk.Button(frame, text="Comparar fontes", command=self.toggle, bg="#1b2b38", fg=TEXT,
                                activebackground="#294354", activeforeground=TEXT, relief="flat", bd=0,
                                font=("Segoe UI", 9), cursor="hand2", takefocus=False)
        self.button.pack(side="left", fill="both", expand=True)
        self.notes_button = tk.Button(frame, text="Observações", command=self.toggle_notes, bg="#1b2b38", fg=TEXT,
                                      activebackground="#294354", activeforeground=TEXT, relief="flat", bd=0,
                                      font=("Segoe UI", 9), cursor="hand2", takefocus=False)
        self.notes_button.pack(side="left", fill="both", expand=True, padx=(1, 0))
        if demo and on_close:
            tk.Button(frame, text="Fechar prévia ×", command=on_close, bg="#273440", fg=TEXT,
                      activebackground="#3b4a57", activeforeground=TEXT, relief="flat", bd=0,
                      font=("Segoe UI", 9), cursor="hand2", takefocus=False).pack(side="right", fill="y", padx=(1, 0))
        self.details, frame, self.details_handle = self.window(1046, 260, interactive=True)
        frame.configure(pady=3)
        top = tk.Frame(frame, bg=BG)
        top.pack(fill="x", pady=(0, 3))
        tk.Label(top, text="Comparar fontes", bg=BG, fg=TEXT, pady=0,
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        tk.Button(top, text="Fechar ×", command=self.toggle, bg=BG, fg=MUTED, relief="flat", bd=0,
                  font=("Segoe UI", 9), cursor="hand2", takefocus=False,pady=0).pack(side="right")
        table = tk.Frame(frame, bg=BG)
        table.pack(fill="both", expand=True)
        table.columnconfigure(0, minsize=230)
        self.detail_names, self.detail_cells = [], []
        tk.Label(table, text="Indicador", bg=BG, fg=MUTED, anchor="w",pady=0,
                 font=("Segoe UI", 9)).grid(row=0, column=0, sticky="ew", pady=(0, 3))
        for i in range(3):
            table.columnconfigure(i+1, weight=1, uniform="cards")
            name = tk.Label(table, text="—", bg=BG, fg=TEXT, font=("Segoe UI", 9, "bold"),
                            wraplength=245, justify="center",pady=0)
            name.grid(row=0, column=i+1, sticky="ew", pady=(0, 3))
            self.detail_names.append(name)
        for i, (label, _) in enumerate(comparison_rows([None]*3), 1):
            tk.Label(table, text=label, bg=BG, fg=MUTED, font=("Segoe UI", 9),
                     anchor="w",pady=0).grid(row=i, column=0, sticky="ew")
            cells = []
            for column in range(1, 4):
                cell = tk.Label(table, text="—", bg=BG, fg=MINT if i in (1,10) else TEXT,
                                font=("Segoe UI", 9), anchor="center",pady=0)
                cell.grid(row=i, column=column, sticky="ew")
                cells.append(cell)
            self.detail_cells.append(cells)

        # Covers native card bodies only while expanded; rerolls and scores stay exposed.
        self.notes, frame, self.notes_handle = self.window(1046, 488, interactive=True)
        top = tk.Frame(frame, bg=BG)
        top.pack(fill="x", pady=(0, 8))
        tk.Label(top, text="Observações", bg=BG, fg=TEXT,
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        tk.Button(top, text="Fechar ×", command=self.toggle_notes, bg=BG, fg=MUTED, relief="flat", bd=0,
                  font=("Segoe UI", 9), cursor="hand2", takefocus=False).pack(side="right")
        columns = tk.Frame(frame, bg=BG)
        columns.pack(fill="both", expand=True)
        self.notes_names, self.notes_texts = [], []
        for slot in range(3):
            columns.columnconfigure(slot, weight=1, uniform="notes")
            column = tk.Frame(columns, bg=BG)
            column.grid(row=0, column=slot, sticky="nsew", padx=(0 if slot == 0 else 9, 0))
            name = tk.Label(column, text="—", bg=BG, fg=MINT, font=("Segoe UI", 10, "bold"),
                            wraplength=310, justify="left", anchor="w")
            name.pack(fill="x", pady=(0, 7))
            body = tk.Frame(column, bg=BG)
            body.pack(fill="both", expand=True)
            scrollbar = tk.Scrollbar(body, orient="vertical", width=10, bd=0, highlightthickness=0)
            scrollbar.pack(side="right", fill="y")
            text = tk.Text(body, wrap="word", width=1, height=1, bg=BG, fg=TEXT, relief="flat",
                           bd=0, highlightthickness=0, font=("Segoe UI", 10), padx=3, pady=3,
                           cursor="arrow", takefocus=False, yscrollcommand=scrollbar.set,
                           selectbackground="#294354", spacing1=3, spacing3=6)
            text.pack(side="left", fill="both", expand=True)
            scrollbar.configure(command=text.yview)
            text.tag_configure("heading", foreground=GOLD, font=("Segoe UI", 9, "bold"), spacing1=12)
            text.configure(state="disabled")
            self.notes_names.append(name)
            self.notes_texts.append(text)
        columns.rowconfigure(0, weight=1)

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
        score='Keitinha Score  '+score_text(card)
        content = (grades, pick, score, summary, name)
        if self.content[slot] != content:
            for label, tier in zip(widgets["letters"], grades):
                color = MUTED if tier=="—" else MINT if tier.startswith("S") else "#b3cbe7" if tier.startswith("A") else "#c2a4b1"
                label.configure(text=tier, fg=color)
            widgets["pick"].configure(text=pick)
            widgets['score'].configure(text=score)
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
        if summary and not self.details_open and not self.notes_open:
            self.show(self.combos[slot][0], x, oy+COMBO_Y, 310, 100)
        elif self.combos[slot][0].state() != "withdrawn":
            self.combos[slot][0].withdraw()
        if self.demo:
            self.show(self.native[slot][0], x, oy+192, 310, 500)

    def toggle(self):
        self.details_open = not self.details_open
        self.notes_open = False
        self.notes_button.configure(text="Observações")
        self.button.configure(text="Recolher comparação" if self.details_open else "Comparar fontes")
        self.log("comparison_toggled", expanded=self.details_open, demo=self.demo)

    def toggle_notes(self):
        self.notes_open = not self.notes_open
        self.details_open = False
        self.button.configure(text="Comparar fontes")
        self.notes_button.configure(text="Recolher notas" if self.notes_open else "Observações")
        self.log("observations_toggled", expanded=self.notes_open, demo=self.demo)

    def render_notes(self, game):
        if not self.notes_open:
            self.notes.withdraw()
            return
        sections = [observation_sections(card) if name != "—" else [("", "—")]
                    for name, card in zip(self.names, self.cards)]
        content = (tuple(self.names), tuple(tuple(column) for column in sections))
        if content != self.notes_content:
            previous = self.notes_content
            for slot, (name, text, column) in enumerate(zip(self.notes_names, self.notes_texts, sections)):
                if previous and (previous[0][slot], previous[1][slot]) == (content[0][slot], content[1][slot]):
                    continue
                name.configure(text=self.names[slot])
                text.configure(state="normal")
                text.delete("1.0", "end")
                for heading, body in column:
                    if heading:
                        text.insert("end", heading+"\n", "heading")
                    text.insert("end", body+"\n\n")
                text.configure(state="disabled")
                text.yview_moveto(0)
            self.notes_content = content
        ox, oy = (game["x"], game["y"]) if game else (0, 0)
        self.show(self.notes, ox+437, oy+204, 1046, 488, interactive=True)

    def render_controls(self, visible, game, root_x, root_y, root_height):
        if not visible or not any(name!="—" for name in self.names):
            self.details_open = False
            self.notes_open = False
            self.button.configure(text="Comparar fontes")
            self.notes_button.configure(text="Observações")
            self.control.withdraw()
            self.details.withdraw()
            self.notes.withdraw()
            return
        self.show(self.control, root_x, root_y+root_height+5, self.control_width, 32, interactive=True)
        self.render_notes(game)
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
                "control_hwnd": int(self.control_handle), "details_hwnd": int(self.details_handle),
                "notes_hwnd": int(self.notes_handle)}
