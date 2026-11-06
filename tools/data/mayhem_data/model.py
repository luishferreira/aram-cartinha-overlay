"""Contract used by all adapters. Uncertain source fields stay uncertain."""
from dataclasses import dataclass, field
from collections import defaultdict
from .common import digest, entity_id, normalized_name

SOURCES = {
    'blitz': {'family':'blitz', 'tier_scale':{'1':'S','2':'A','3':'B','4':'C','5':'D'}},
    'opgg': {'family':'opgg', 'tier_scale':{'0':'S','1':'A','2':'B','3':'C','4':'D','5':'E'}},
    'aramkit': {'family':'aramkit'},
    'arammayhem': {'family':'arammayhem', 'download_license':'CC-BY-4.0'},
    'aramgg': {'family':'aramgg', 'coverage':'developer_api_when_complete_otherwise_published_top20'},
    'metasrc': {'family':'metasrc', 'coverage':'global_and_one_champion_browser_snapshot'},
}


@dataclass
class Batch:
    source: str
    metadata: dict = field(default_factory=dict)
    artifacts: dict = field(default_factory=dict)
    catalog: list = field(default_factory=list)
    observations: list = field(default_factory=list)
    relations: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    issues: list = field(default_factory=list)
    build_resources: list = field(default_factory=list)

    def issue(self, code, detail, severity='warning'):
        self.issues.append({'source':self.source, 'code':code, 'detail':detail, 'severity':severity})

    def artifact(self, path, url=None, collected_at=None, **meta):
        path = path.resolve()
        sha = digest(path.read_bytes())
        self.artifacts.setdefault(sha, {'sha256':sha, 'local_path':str(path),
            'url':url, 'collected_at':collected_at, 'bytes':path.stat().st_size, **meta})
        return sha

    def catalog_row(self, kind, native_id, artifact, names=None, descriptions=None,
                    attributes=None, namespace='game'):
        row = {'entity_id':entity_id(kind, native_id, namespace), 'kind':kind,
            'native_id':str(native_id), 'artifact':artifact, 'names':names or {},
            'descriptions':descriptions or {}, 'attributes':attributes or {}}
        self.catalog.append(row)
        return row['entity_id']

    def observe(self, entity, artifact, context, metrics, patch=None, stats_date=None,
                selector=None, flags=None):
        self.observations.append({'entity_id':entity, 'artifact':artifact,
            'context':context, 'metrics':metrics, 'patch':patch, 'stats_date':stats_date,
            'selector':selector, 'flags':flags or []})


class Identity:
    """Exact, unique aliases only. Namespaced fallback survives incomplete catalogs."""
    def __init__(self):
        self.champions = {}
        self.english = defaultdict(set)
        self.site_augments = {}
        self.site_items = {}
        self.mapping_evidence = []
        self.reviewed_aliases = {}

    def add_name(self, name, native):
        self.english[normalized_name(name)].add(entity_id('augment', native))

    def augment(self, native, name=None):
        if str(native) in self.site_augments:
            return self.site_augments[str(native)]
        reviewed=self.reviewed_aliases.get(str(native))
        if reviewed:
            resolved=reviewed['entity_id']
            self.site_augments[str(native)]=resolved
            self.mapping_evidence.append({'source':'arammayhem','native_id':str(native),
                'entity_id':resolved,'method':'reviewed_internal_key_and_effect',
                'candidate_ids':[resolved],'name':name,'evidence':reviewed})
            return resolved
        candidates = set(self.english.get(normalized_name(name or ''), set()))
        if not candidates and (name or '').startswith('Quest: '):
            candidates = set(self.english.get(normalized_name(name[7:]), set()))
        resolved = next(iter(candidates)) if len(candidates) == 1 else entity_id('augment', native, 'arammayhem')
        self.site_augments[str(native)] = resolved
        self.mapping_evidence.append({'source':'arammayhem','native_id':str(native),
            'entity_id':resolved, 'method':'unique_exact_english_alias' if len(candidates)==1 else 'unresolved',
            'candidate_ids':sorted(candidates), 'name':name})
        return resolved

    def champion(self, key):
        return self.champions.get(str(key), entity_id('champion', key, 'arammayhem'))


def metric(value, unit, meaning, denominator=None):
    return {'value':value, 'unit':unit, 'meaning':meaning, 'denominator':denominator}


def stats(row, percent=False):
    result = {}
    for field, output, unit, meaning in [
        ('tier','tier','source_label','source_specific_strength_classification'),
        ('rank','rank','ordinal','source_specific_ranking'),
        ('sampleCount','sample_count','count','published_observation_sample'),
        ('winRate','win_rate','proportion','observed_win_rate'),
        ('pickRate','pick_rate','proportion','published_popularity'),
        ('synergyDelta','synergy_delta','proportion_points','source_reported_unadjusted_delta'),
    ]:
        if row.get(field) is not None:
            value = row[field]
            if field in ('winRate','pickRate'):
                value = float(str(value).rstrip('%')) / (100 if percent else 1)
            result[output] = metric(value, unit, meaning)
    return result
