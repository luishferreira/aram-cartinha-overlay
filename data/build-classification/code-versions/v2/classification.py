"""Deterministic, abstaining classification of build identity, never build strength."""
from collections import Counter, defaultdict
import math

VERSION = 'build-path-classifier-2'
POLICY = {
    'item_similarity_weight': 0.8, 'feature_similarity_weight': 0.2,
    'minimum_similarity': 0.50, 'high_similarity': 0.75,
    'minimum_margin': 0.10, 'maximum_ambiguous_paths': 3,
    'minimum_core_items': 2,
}


def item_id(value):
    if isinstance(value, str) and value.startswith('item:game:'):
        value = value.rsplit(':', 1)[1]
    if isinstance(value, bool) or not str(value).isdigit() or int(value) <= 0:
        raise ValueError('Expected a positive native game item ID')
    return int(value)


def significant(items, catalog):
    """Strip known support items for classification only; preserve unknown native IDs."""
    kept, ignored, unknown = set(), [], set()
    for value in items:
        ident = item_id(value)
        meta = catalog.get(str(ident))
        if meta is None:
            kept.add(ident)
            unknown.add(ident)
            continue
        tags = set(meta.get('categories', []))
        category = meta.get('category', '')
        reason = None
        if tags & {'Boots', 'Consumable', 'Trinket'} or category.startswith('boots'):
            reason = 'boots_consumable_or_trinket'
        elif category in {'starter', 'component', 'basic'}:
            reason = 'starter_or_component'
        elif meta.get('upgrades') and (meta.get('cost') or 0) < 1800 and category not in {'legendary', 'mythic'}:
            reason = 'low_cost_component'
        if reason:
            ignored.append({'item_id': ident, 'reason': reason})
        else:
            kept.add(ident)
            if not tags:
                unknown.add(ident)
    return frozenset(kept), ignored, sorted(unknown)


def vector(items, catalog):
    result = Counter()
    for ident in items:
        for tag in catalog.get(str(ident), {}).get('categories', []):
            if tag not in {'Boots', 'Consumable', 'Trinket', 'Active', 'Lane', 'Jungle', 'Vision'}:
                result[tag] += 1 / len(items)
    return dict(result)


def cosine(a, b):
    norm = math.sqrt(sum(v*v for v in a.values()) * sum(v*v for v in b.values()))
    return sum(v*b.get(k, 0) for k, v in a.items()) / norm if norm else 0.0


def signature(items):
    return ','.join(map(str, sorted(items)))


class Classifier:
    def __init__(self, profiles, catalog, policy=None):
        self.policy = dict(POLICY if policy is None else policy)
        self.catalog = catalog
        self.by_champion = defaultdict(list)
        self.centroids = defaultdict(Counter)
        # Duplicated routes, samples, WR and popularity never increase a prototype's vote.
        seen = set()
        self.profiles = []
        for row in sorted(profiles, key=lambda p: p['id']):
            core, _, _ = significant(row['items'], catalog)
            if len(core) < self.policy['minimum_core_items']:
                continue
            key = row['champion_id'], row['path'], core
            if key in seen:
                continue
            seen.add(key)
            profile = {**row, 'core': core, 'features': vector(core, catalog)}
            self.profiles.append(profile)
            self.by_champion[row['champion_id']].append(profile)
            self.centroids[row['path']].update(profile['features'])

    def classify(self, champion_id, items, source_patch=None):
        core, ignored, unknown = significant(items, self.catalog)
        base = {'classifier_version': VERSION, 'significant_item_ids': sorted(core),
                'ignored_items': ignored, 'unknown_feature_item_ids': unknown,
                'assignments': [], 'compatible_paths': [], 'candidates': [], 'feature_suggestions': [],
                'status': 'unclassified', 'confidence': 'insufficient',
                'similarity_is_probability': False, 'flags': []}
        if len(core) < self.policy['minimum_core_items']:
            base['flags'].append('insufficient_core_items')
            return base
        query_features = vector(core, self.catalog)
        prototypes = self.by_champion.get(champion_id, [])
        paths = {p['path'] for p in prototypes}
        presence = defaultdict(set)
        for profile in prototypes:
            for ident in profile['core']:
                presence[ident].add(profile['path'])
        def weight(ident):
            return 1 + math.log((len(paths) + 1) / (len(presence[ident]) + 1))
        candidates = {}
        for profile in prototypes:
            intersection = core & profile['core']
            overlap = sum(weight(i) for i in intersection) / sum(weight(i) for i in core | profile['core'])
            features = cosine(query_features, profile['features'])
            score = self.policy['item_similarity_weight']*overlap + self.policy['feature_similarity_weight']*features
            candidate = {'path': profile['path'], 'similarity': round(score, 6),
                'item_similarity': round(overlap, 6), 'feature_similarity': round(features, 6),
                'shared_item_ids': sorted(intersection), 'reference_profile_id': profile['id'],
                'reference_item_ids': sorted(profile['core']), 'reference_patch': profile.get('patch'),
                'exact_core': core == profile['core']}
            current = candidates.get(profile['path'])
            if current is None or score > current['similarity'] + 1e-6:
                candidates[profile['path']] = candidate
        ranked = sorted(candidates.values(), key=lambda c: (-c['similarity'], c['path']))
        base['candidates'] = ranked
        base['feature_suggestions'] = sorted(
            [{'path': path, 'similarity': round(cosine(query_features, values), 6),
              'already_published_for_champion': path in paths}
             for path, values in self.centroids.items()], key=lambda c: (-c['similarity'], c['path']))[:3]
        if not ranked:
            base['flags'].append('no_same_champion_references')
            return base
        top = ranked[0]
        margin = top['similarity'] - (ranked[1]['similarity'] if len(ranked) > 1 else 0)
        base['margin'] = round(margin, 6)
        eligible = [c for c in ranked if c['similarity'] >= self.policy['minimum_similarity']
                    and len(c['shared_item_ids']) >= self.policy['minimum_core_items']]
        nearby = [c for c in eligible if top['similarity'] - c['similarity'] < self.policy['minimum_margin']]
        if len(nearby) > self.policy['maximum_ambiguous_paths']:
            base['flags'].append('too_many_compatible_paths')
        elif len(nearby) > 1:
            base.update(status='ambiguous', confidence='ambiguous', compatible_paths=[c['path'] for c in nearby])
            base['flags'].append('multiple_compatible_paths_not_a_confirmed_hybrid')
        elif nearby and margin >= self.policy['minimum_margin']:
            confidence = 'high' if top['similarity'] >= self.policy['high_similarity'] and not unknown else 'medium'
            base.update(status='assigned', confidence=confidence, assignments=[top['path']], compatible_paths=[top['path']])
        else:
            base['flags'].append('insufficient_overlap_or_margin')
        if unknown:
            base['flags'].append('some_item_features_unknown')
        if source_patch and any(p.get('patch') != source_patch for p in prototypes):
            base['flags'].append('native_patch_equality_not_established')
        return base
