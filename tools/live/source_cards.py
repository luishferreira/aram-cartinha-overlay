"""Read-only source evidence and an auditable runtime consensus; no automatic winner."""
import copy
import json
from pathlib import Path
import queue
import re
import sqlite3
import threading
import time

from tools.recommendation.card_evidence import plain, popularity_ranks
from tools.recommendation.keitinha_score import calculate,popularity_percentiles,MODEL_VERSION as SCORE_VERSION

from tools.app_paths import app_root
ROOT = app_root()
MODULE_VERSION="live-source-cards-0.3.0"


def metric(row, key):
    return row.get("metrics",{}).get(key,{}).get("value") if row else None


def percent(value):
    return f"{value*100:.2f}%".replace(".",",") if value is not None else "—"


def count(value):
    return f"{value:,}".replace(",",".") if value is not None else "—"


def number(value):
    return f"{value:.2f}".replace(".",",") if value is not None else "—"


def short(text, length):
    text = " ".join(str(text or "").split())
    return text if len(text)<=length else text[:length-1].rstrip()+"…"


class SourceReader:
    def __init__(self, root=ROOT, *, runtime_directory=None):
        self.root=Path(root)
        self.runtime_generation=None
        if runtime_directory is None:
            self.run=json.loads((self.root/"data/pipeline/current.json").read_text(encoding="utf-8"))["run"]
            if not re.fullmatch(r"[0-9a-f]{24}",self.run):
                raise ValueError("Invalid local data run")
            directory=self.root/"data/pipeline/runs"/self.run
            self.manifest=json.loads((directory/"manifest.json").read_text(encoding="utf-8"))
            database=directory/'mayhem.sqlite3'
        else:
            from tools.live.data_paths import load_pack
            directory=Path(runtime_directory)
            pack=load_pack(directory)
            self.runtime_generation=pack['generation']
            self.run=pack['data_run']
            self.manifest=pack['source_metadata']
            database=directory/'cards.sqlite3'
        self.db=sqlite3.connect(database.resolve().as_uri()+"?mode=ro",uri=True)
        self.db.row_factory=sqlite3.Row
        self.db.execute("PRAGMA query_only=ON")
        self.rankings={}
        self.popularity_scores={}
        self.cards={}
        self.editorials={}
        self.combinations={}
        self.availability={}
        self.labels={}
        self.source_patches={row["source"]:set(json.loads(row["metadata_json"]).get("patches",[]))
                             for row in self.db.execute('SELECT source,metadata_json FROM snapshots')}

    def close(self):
        self.db.close()

    def label(self, entity):
        if entity not in self.labels:
            name=None
            for row in self.db.execute('SELECT c.names_json FROM catalog c JOIN snapshots s ON s.id=c.snapshot_id WHERE c.entity_id=? ORDER BY CASE s.source WHEN "opgg" THEN 0 WHEN "blitz" THEN 1 ELSE 2 END,c.id',(entity,)):
                names=json.loads(row[0])
                if names.get("pt-BR"):
                    name=names["pt-BR"]
                    break
                name=name or names.get("en-US")
            self.labels[entity]=name or entity
        return self.labels[entity]

    def observations(self, champion, candidate):
        rows=[]
        for row in self.db.execute('SELECT o.*,s.source FROM observations o JOIN snapshots s ON s.id=o.snapshot_id WHERE o.entity_id=? AND (o.champion_id=? OR o.scope="global") ORDER BY s.source,o.id',(candidate,champion)):
            context=json.loads(row["context_json"])
            flags=json.loads(row["flags_json"])
            if context.get("series")=="historical" or any("historical" in f for f in flags):
                continue
            champion_rarity = row["source"]=="arammayhem" and context.get("ranking_scope")=="rarity"
            if row["scope"]=="champion" and ((context.get("ranking_scope") and not champion_rarity) or context.get("stage") not in (None,"all")):
                continue
            rows.append({"source":row["source"],"scope":row["scope"],"stage":row["stage"],
                         "patch":row["patch"],"stats_date":row["stats_date"],"context":context,
                         "metrics":json.loads(row["metrics_json"]),"flags":flags,"artifact":row["artifact"],"selector":row["selector"]})
        return rows

    def base(self, champion_id, card_id):
        key=(champion_id,card_id)
        if key in self.cards:
            return self.cards[key]
        champion=f"champion:game:{champion_id}" if champion_id is not None else None
        candidate=f"augment:game:{card_id}"
        rows=self.observations(champion,candidate)
        def pick(source,group=None,scope="champion",field=None,ranking_scope=None):
            choices=[r for r in rows if r["source"]==source and r["scope"]==scope
                     and r["context"].get("ranking_scope")==ranking_scope
                     and (group is None or r["context"].get("metric_group")==group)
                     and (field is None or metric(r,field) is not None)]
            return choices[0] if choices else None
        if champion is not None and champion not in self.rankings:
            self.rankings[champion]=popularity_ranks(self.db,champion)
            self.popularity_scores[champion]=popularity_percentiles(self.rankings[champion])
        sources={"aramkit":pick("aramkit"),"aramgg":pick("aramgg","uploaded_performance"),
                 "aramgg_popularity":pick("aramgg","recommendation_and_popularity"),
                 "blitz":pick("blitz"),"opgg":pick("opgg"),
                 "arammayhem_champion_tier":pick("arammayhem",field="tier",ranking_scope="rarity"),
                 "arammayhem_tier":pick("arammayhem",scope="global",field="tier"),
                 "arammayhem_popularity":pick("arammayhem",scope="global",field="popularity_rank")}
        result={"module_version":MODULE_VERSION,"data_run":self.run,"card_id":card_id,"champion_id":champion_id,
                "champion_name":self.label(champion) if champion else None,"sources":sources,
                "opgg_popularity":self.rankings.get(champion,{}).get(candidate),
                "scope":"champion_overall_not_build","combined_tier":None,"reference_rows":rows,
                "base_created_at":self.manifest.get("created_at")}
        result['keitinha_score']=calculate(sources,self.popularity_scores.get(champion,{}).get(candidate))
        self.cards[key]=result
        return result

    def usable_members(self, members):
        """Unresolved identities and source-retired members cannot drive suggestions."""
        for member in members:
            if not re.fullmatch(r"augment:game:\d+",member):
                return False
            if self.label(member)==member:
                return False
            if member not in self.availability:
                self.availability[member]=[
                    json.loads(row[0]).get("availability") for row in self.db.execute(
                        'SELECT c.attributes_json FROM catalog c JOIN snapshots s ON s.id=c.snapshot_id '
                        'WHERE s.source="arammayhem" AND c.entity_id=?',(member,))]
            if "retired" in self.availability[member]:
                return False
        return True

    def editorial_options(self, champion_id, card_id, selected):
        if champion_id is None:
            return []
        champion=f"champion:game:{champion_id}"
        candidate=f"augment:game:{card_id}"
        if champion not in self.editorials:
            self.editorials[champion]=[json.loads(r[0]) for r in self.db.execute('SELECT r.data_json FROM relations r JOIN snapshots s ON s.id=r.snapshot_id WHERE s.source="arammayhem" AND r.champion_id=? AND r.kind="editorial_bundle" ORDER BY r.id',(champion,))]
        chosen={f"augment:game:{i}" for i in selected if i!=card_id}
        relevant=[]
        for relation in self.editorials[champion]:
            if candidate not in relation.get("augment_ids",[]):
                continue
            if not self.usable_members(relation["augment_ids"]):
                continue
            patch=relation.get("response_patch") or relation.get("patch")
            if patch and patch not in self.source_patches.get("arammayhem",set()):
                continue
            text=plain(relation.get("explanation"))
            if not text or text.strip().lower() in ("nothing", "nothing."):
                continue
            overlap=sorted(chosen.intersection(relation["augment_ids"]))
            other=sorted(set(relation["augment_ids"])-chosen-{candidate})
            relevant.append({"text":text,"selected_members":overlap,
                             "member_names":[self.label(i) for i in overlap],"source":"arammayhem",
                             "other_members":other,"other_names":[self.label(i) for i in other],
                             "required_members":None,"required_items":None,
                             "member_semantics":relation.get("member_semantics","unspecified"),
                             "listed_members":list(relation["augment_ids"]),"patch":patch,
                             "language":"source_original","validation":"editorial_hypothesis",
                             "url":relation.get("url"),"artifact":relation.get("explanation_artifact",relation.get("artifact"))})
        relevant.sort(key=lambda r:(-len(r["selected_members"]),len(r["other_members"]),r.get("url") or ""))
        return relevant

    def editorial(self, champion_id, card_id, selected):
        relevant=self.editorial_options(champion_id,card_id,selected)
        return relevant[0] if relevant else None

    def observed_combos(self, champion_id, card_id, selected):
        if champion_id is None:
            return []
        champion=f"champion:game:{champion_id}"
        candidate=f"augment:game:{card_id}"
        chosen={f"augment:game:{i}" for i in selected if i!=card_id}
        if champion not in self.combinations:
            self.combinations[champion]=[
                {**json.loads(row["data_json"]),"source":row["source"]}
                for row in self.db.execute(
                    'SELECT r.data_json,s.source FROM relations r JOIN snapshots s ON s.id=r.snapshot_id '
                    'WHERE r.champion_id=? AND r.kind IN ("observed_pair","observed_trio") '
                    'AND s.source IN ("aramkit","aramgg") ORDER BY r.id',(champion,))]
        result=[]
        for relation in self.combinations[champion]:
            members=set(relation.get("augment_ids",[]))
            expected=2 if relation.get("kind")=="observed_pair" else 3
            if candidate not in members or len(members)!=expected or not self.usable_members(members):
                continue
            if relation.get("historical_patch") or relation.get("patch") not in self.source_patches.get(relation["source"],set()):
                continue
            wr=metric(relation,"win_rate")
            sample=metric(relation,"sample_count")
            if wr is None or not 0<=wr<=1 or sample is None or sample<=0:
                continue
            overlap=sorted(chosen.intersection(members))
            missing=sorted(members-chosen-{candidate})
            result.append({**copy.deepcopy(relation),"selected_members":overlap,
                           "member_names":[self.label(i) for i in overlap],
                           "missing_members":missing,"missing_names":[self.label(i) for i in missing],
                           "status":"completes_observed" if not missing else "observed_path",
                           "causal_synergy":False,"predicted_win_rate":None})
        # Context first, then evidence size. Never select the largest WR as a winner.
        result.sort(key=lambda r:(bool(r["missing_members"]),-len(r["selected_members"]),
                                  -metric(r,"sample_count"),r["source"],r.get("native_id", "")))
        return result

    def read(self, champion_id, card_id, selected=()):
        result=copy.deepcopy(self.base(champion_id,card_id))
        notes=self.editorial_options(champion_id,card_id,selected)
        result["editorial"]=notes[0] if notes else None
        result["combo_evidence"]={"observed":self.observed_combos(champion_id,card_id,selected),
                                  "editorial":notes,"selected_winner":False,
                                  "coverage":"source_published_subset","mechanics_verified":False}
        result["selected_ids"]=list(selected)
        return result


def panel_rows(card):
    """Nine compact rows; missing is distinct from an observed zero."""
    if card is None:
        return ["ARAMKit —", "", "ARAMGG —", "", "Blitz — · OP.GG —", "", "ARAM Mayhem —", "", ""]
    if card.get("error"):
        return ["Base local indisponível", "", "", "", "", "", "", "", ""]
    s=card["sources"]
    kit,gg,blitz,opgg=s["aramkit"],s["aramgg"],s["blitz"],s["opgg"]
    kr=metric(kit,"rank")
    kit_detail=f'Pop {percent(metric(kit,"pick_rate"))} · rank {kr if kr is not None else "—"}' if kit else ""
    rank=card.get("opgg_popularity")
    popularity=f'#{rank["rank"]}/{rank["published_entries"]}' if rank else "—"
    tier=metric(s.get("arammayhem_champion_tier"),"tier")
    mayhem=f'ARAM Mayhem {tier} · por raridade' if tier is not None else "ARAM Mayhem —"
    world=gg["context"].get("region") if gg else None
    gg_label="ARAMGG global" if world=="WORLD" else "ARAMGG"+(f" {world}" if world else "")
    return [f'ARAMKit {metric(kit,"tier") or "—"} · WR {percent(metric(kit,"win_rate"))}',
            kit_detail,
            f'{gg_label} · WR {percent(metric(gg,"win_rate"))}',
            "",
            f'Blitz {metric(blitz,"tier") or "—"} · OP.GG {metric(opgg,"tier") or "—"}',
            f'OP.GG pop calc. {popularity} · índice {number(metric(opgg,"performance_raw"))}',
            mayhem,"",
            ""]


def combo_rows(card):
    """Compact contextual advice; list membership is never a mechanical requirement."""
    if not card or card.get("error"):
        return []
    evidence=card.get("combo_evidence",{})
    observed=evidence.get("observed",[])
    notes=evidence.get("editorial",[])
    lines=[]
    if observed:
        combo=observed[0]
        kind="par" if combo["kind"]=="observed_pair" else "trio"
        source="ARAMKit" if combo["source"]=="aramkit" else "ARAMGG"
        if combo["status"]=="completes_observed":
            lines.append(f'Forma {kind} observado · {source} · WR {percent(metric(combo,"win_rate"))}')
            lines.append("Com: "+" + ".join(combo["member_names"]))
        elif combo["selected_members"] or not any(n["selected_members"] for n in notes):
            lines.append(f'Caminho de {kind} · {source}')
            if combo["member_names"]:
                lines.append("Com: "+" + ".join(combo["member_names"]))
            lines.append("Falta: "+" + ".join(combo["missing_names"]))
    if notes:
        note=notes[0]
        title="Nota Mayhem (EN)"
        if note["member_names"]:
            title+=" com "+" + ".join(note["member_names"])
        if note["other_names"]:
            lines.append(title)
            lines.append("Outras citadas: "+" + ".join(note["other_names"]))
            lines.append(note["text"])
        else:
            lines.append(title+": "+note["text"])
    return lines


def fit_combo_text(rows, measure, width, max_lines):
    """Word-wrap to the actual native font budget; full evidence remains in JSON."""
    if max_lines<=0:
        return ""
    wrapped=[]
    for row in rows:
        line=""
        for word in row.split():
            while measure(word)>width:
                cut=1
                while cut<len(word) and measure(word[:cut+1])<=width:
                    cut+=1
                if line:
                    wrapped.append(line);line=""
                wrapped.append(word[:cut]);word=word[cut:]
            if not word:
                continue
            trial=(line+" "+word).strip()
            if line and measure(trial)>width:
                wrapped.append(line);line=word
            else:
                line=trial
        if line:
            wrapped.append(line)
    if len(wrapped)>max_lines:
        wrapped=wrapped[:max_lines]
        tail=wrapped[-1]
        while tail and measure(tail+"…")>width:
            tail=tail[:-1]
        wrapped[-1]=tail.rstrip()+"…"
    return "\n".join(wrapped)


class SourceCards:
    """Queue SQLite work outside Tk/capture threads; UI only reads a small cache."""
    def __init__(self, root=ROOT, log=None):
        self.root=Path(root)
        self.log=log or (lambda *a,**k:None)
        self.queue=queue.Queue(maxsize=32)
        self.lock=threading.Lock()
        self.cache={}
        self.pending=set()
        self.stop=threading.Event()
        self.failure=None
        self.thread=threading.Thread(target=self.worker,daemon=True,name="mayhem-source-cards")
        self.thread.start()

    def get(self, champion_id, card_id, selected=()):
        key=(champion_id,card_id,tuple(sorted(set(selected))))
        with self.lock:
            if self.failure:
                return self.failure
            if key in self.cache:
                return self.cache[key]
            if key not in self.pending:
                try:
                    self.queue.put_nowait(key)
                    self.pending.add(key)
                except queue.Full:
                    pass
        return None

    def worker(self):
        reader=None
        try:
            from tools.live.data_paths import active_pack
            pack=active_pack(self.root,verify_files=False)
            reader=SourceReader(self.root,runtime_directory=pack[0] if pack else None)
            self.log("source_cards_ready",data_run=reader.run,module_version=MODULE_VERSION,
                     score_version=SCORE_VERSION,
                     runtime_generation=reader.runtime_generation)
            while not self.stop.is_set():
                try:
                    key=self.queue.get(timeout=.2)
                except queue.Empty:
                    continue
                began=time.monotonic()
                try:
                    card=reader.read(*key)
                    card["loaded_ms"]=round((time.monotonic()-began)*1000)
                except Exception as error:
                    card={"error":type(error).__name__,"card_id":key[1]}
                    self.log("source_card_error",error_type=type(error).__name__,detail=str(error))
                with self.lock:
                    if len(self.cache)>=512:
                        self.cache.clear()
                    self.cache[key]=card
                    self.pending.discard(key)
        except Exception as error:
            with self.lock:
                self.failure={"error":type(error).__name__}
            self.log("source_cards_error",error_type=type(error).__name__,detail=str(error))
        finally:
            if reader:
                reader.close()

    def close(self):
        self.stop.set()
