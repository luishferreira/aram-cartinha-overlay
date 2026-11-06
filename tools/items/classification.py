"""Overlapping item affinities: build families and specializations are separate axes."""
from collections import Counter, defaultdict
import html
import re

from tools.items.classification_prototypes import (
    Classifier as PrototypeClassifier, POLICY as PROTOTYPE_POLICY,
    item_id, significant, signature, vector, cosine,
)

VERSION = 'build-path-classifier-3'
POLICY = {
    'minimum_core_items': 2, 'minimum_family_affinity': 0.30,
    'utility_family_affinity': 0.40, 'utility_relative_affinity': 0.60,
    'hybrid_minimum_each': 0.35, 'hybrid_minimum_ratio': 0.60,
    'specialization_affinity': 0.35, 'specialization_relative_affinity': 0.60,
    'minimum_specialization_support': 2,
    'high_affinity': 0.65, 'high_metadata_coverage': 0.80,
}
PATHS = ('ad','ap','tank','utility','crit','lethality','on_hit','bruiser','hybrid')


def plain(text):
    return ' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', text or '')).split()).lower()


class Classifier(PrototypeClassifier):
    def __init__(self, profiles, catalog, policy=None):
        super().__init__(profiles, catalog, PROTOTYPE_POLICY)
        self.affinity_policy = dict(POLICY if policy is None else policy)
        self.names = defaultdict(list)
        for ident, meta in catalog.items():
            if meta.get('name'):
                self.names[meta['name'].casefold()].append(int(ident))
        self.families = {int(i):int(i) for i in catalog}
        for ident, meta in catalog.items():
            target = meta.get('transforms_into_name')
            choices = self.names.get(target.casefold(), []) if target else []
            if len(choices) == 1:
                # Explicit published transformations, never modulo-ID guesses.
                a, b = self.family(int(ident)), self.family(choices[0])
                self.families[a] = self.families[b] = min(a,b)
        self.learned = defaultdict(Counter)
        for profile in self.profiles:
            for ident in profile['core']:
                self.learned[self.family(ident)][profile['path']] += 1
        self.item_cache = {}

    def family(self, ident):
        while self.families.get(ident,ident) != ident:
            ident = self.families[ident]
        return ident

    def item_affinity(self, ident):
        if ident in self.item_cache:
            return self.item_cache[ident]
        meta = self.catalog.get(str(ident), {})
        tags = set(meta.get('categories', []))
        text = meta.get('description', '')
        match = re.search(r'<stats>(.*?)</stats>',text,re.S|re.I)
        stats = plain(match.group(1) if match else meta.get('stats_text', ''))
        description = plain(text)
        ad = 'Damage' in tags or 'attack damage' in stats
        ap = 'SpellDamage' in tags or 'ability power' in stats
        health = 'Health' in tags or bool(re.search(r'\bhealth\b',stats))
        defense = bool(tags & {'Armor','SpellBlock','MagicResist'})
        critical = 'CriticalStrike' in tags or 'critical strike chance' in stats
        lethality = 'lethality' in stats
        healing = 'heal and shield power' in stats
        mana_regen = 'ManaRegen' in tags or 'mana regen' in stats
        healing_attack = bool(re.search(r'(basic attacks|attacks on.hit).*?(allied|ally).*?(heal|healed)',description))
        values = {p:0.0 for p in PATHS}
        on_hit = (1.0 if 'AttackSpeed' in tags and 'spellblade' not in description else 0.35) if 'OnHit' in tags else 0.0
        values.update(ad=float(ad), ap=float(ap), crit=float(critical), lethality=float(lethality), on_hit=on_hit)
        if healing:
            values['utility'] = 1.0
        elif mana_regen and not ad:
            values['utility'] = 0.70
        if healing_attack:
            values['utility'] = 1.0
        # AP in a healing item is compatible, but less indicative of an offensive AP path.
        if ap and values['utility']:
            values['ap'] *= 1 - 0.60*values['utility']
        if defense:
            values['tank'] = 0.65 if ad or ap else 1.0
        elif health:
            values['tank'] = 0.35 if ad or ap else (0.45 if healing else 0.85)
        if ad and health:
            values['bruiser'] = 1.0
        elif ad and ('AbilityHaste' in tags or 'CooldownReduction' in tags) and not critical and not lethality:
            values['bruiser'] = 0.40
        values['hybrid'] = float(ad and ap)
        basis = 'catalog_properties'
        if not tags and not stats:
            observed = self.learned.get(self.family(ident), {})
            total = sum(observed.values())
            if total:
                for path,count in observed.items():
                    values[path] = count/total
                values['ad'] = min(1.0,sum(observed.get(p,0) for p in ['ad','crit','lethality','on_hit','bruiser'])/total)
                basis = 'reference_membership_fallback'
            else:
                basis = 'unknown'
        result = {'item_id':ident, 'comparison_family_id':self.family(ident),
                  'name':meta.get('name'), 'affinities':values, 'basis':basis,
                  'mechanics': ['healing_on_attack'] if healing_attack else [],
                  'metadata_origins':meta.get('origins',[])}
        self.item_cache[ident] = result
        return result

    def classify(self, champion_id, items, source_patch=None, choice_groups=None):
        base = super().classify(champion_id,items,source_patch)
        base['prototype_candidates'] = base['candidates']
        base.update(classifier_version=VERSION, assignments=[], compatible_paths=[],
                    primary_family=None, primary_path=None, affinity_percentages={},
                    item_contributions=[], mechanics=[], status='unclassified', confidence='insufficient',
                    affinity_is_probability=False,
                    flags=[f for f in base['flags'] if f not in {
                        'insufficient_overlap_or_margin','too_many_compatible_paths',
                        'multiple_compatible_paths_not_a_confirmed_hybrid','insufficient_core_items'}])
        groups = sorted([[item_id(i)] for i in items] + [sorted(map(item_id,g)) for g in (choice_groups or [])],key=tuple)
        slots, seen = [], set()
        for options in groups:
            eligible = []
            for ident in options:
                core,_,_ = significant([ident],self.catalog)
                if core:
                    eligible.append(item_id(ident))
            key = tuple(sorted({self.family(i) for i in eligible}))
            if not key or key in seen:
                continue
            seen.add(key)
            # Each OR group occupies one slot; average without generating combinations.
            contributions = [self.item_affinity(i) for i in sorted(set(eligible))]
            slots.append({'kind':'choose_one' if len(options)>1 else 'item',
                          'options':contributions,
                          'affinities': {p:sum(i['affinities'][p] for i in contributions)/len(contributions) for p in PATHS}})
        if len(slots) < self.affinity_policy['minimum_core_items']:
            base['flags'].append('insufficient_core_items')
            return base
        scores = {p:sum(s['affinities'][p] for s in slots)/len(slots) for p in PATHS}
        scores['hybrid'] = min(1.0,2*min(scores['ad'],scores['ap']))
        support = {p:sum(s['affinities'][p]>=0.5 for s in slots) for p in PATHS}
        base['affinity_percentages'] = {p:round(v*100,2) for p,v in scores.items()}
        base['candidates'] = [{'path':p, 'affinity_percentage':round(scores[p]*100,2),
                               'axis':'specialization' if p in {'crit','lethality','on_hit','bruiser'} else 'family'}
                              for p in PATHS]
        base['specialization_support_slots'] = support
        base['item_contributions'] = slots
        base['mechanics'] = sorted({m for s in slots for i in s['options'] for m in i['mechanics']})
        base['relevant_slots'] = len(slots)
        base['comparison_item_families'] = sorted({i['comparison_family_id'] for s in slots for i in s['options']})
        base['unknown_feature_item_ids'] = sorted({i['item_id'] for s in slots for i in s['options'] if i['basis'] != 'catalog_properties'})
        if not base['unknown_feature_item_ids']:
            base['flags'] = [f for f in base['flags'] if f != 'some_item_features_unknown']
        ad, ap, tank, utility = (scores[p] for p in ['ad','ap','tank','utility'])
        if utility >= self.affinity_policy['utility_family_affinity'] and utility >= self.affinity_policy['utility_relative_affinity']*max(ad,ap,tank):
            family = 'utility'
        elif min(ad,ap) >= self.affinity_policy['hybrid_minimum_each'] and min(ad,ap)/max(ad,ap) >= self.affinity_policy['hybrid_minimum_ratio']:
            family = 'hybrid'
        else:
            family = max(('ad','ap','tank'),key=lambda p:scores[p])
        if scores[family] < self.affinity_policy['minimum_family_affinity']:
            base['flags'].append('insufficient_item_affinity')
            return base
        specials = []
        if family != 'utility':
            for path in ['lethality','crit','on_hit']:
                if scores[path] >= self.affinity_policy['specialization_affinity'] and support[path] >= self.affinity_policy['minimum_specialization_support']:
                    specials.append(path)
        strongest = max((scores[p] for p in specials),default=0)
        specials = [p for p in specials if scores[p] >= strongest*self.affinity_policy['specialization_relative_affinity']]
        specials.sort(key=lambda p:(-scores[p],['lethality','crit','on_hit'].index(p)))
        primary = specials[0] if specials else family
        assignments = [primary] + [p for p in specials if p != primary]
        if family not in assignments:
            assignments.append(family)
        if scores['bruiser'] >= 0.45 and family in {'ad','hybrid'} and 'bruiser' not in assignments:
            assignments.append('bruiser')
        known = sum(sum(i['basis']=='catalog_properties' for i in s['options'])/len(s['options']) for s in slots)/len(slots)
        confidence = 'high' if scores[primary] >= self.affinity_policy['high_affinity'] and known >= self.affinity_policy['high_metadata_coverage'] else 'medium'
        base.update(status='assigned', confidence=confidence, primary_family=family, primary_path=primary,
                    assignments=assignments, compatible_paths=assignments,
                    metadata_coverage=round(known,6))
        published = {p['path'] for p in self.by_champion.get(champion_id,[])}
        if set(assignments)-published:
            base['flags'].append('some_paths_not_published_for_champion_in_reference')
        if choice_groups:
            base['flags'].append('alternative_groups_averaged_not_synthetic_builds')
        base['flags'].append('permissive_multilabel_affinity_not_strength')
        return base
