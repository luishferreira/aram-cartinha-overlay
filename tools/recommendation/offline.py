"""Offline review bench: native build paths, offered cards and path-switch replays.

All database access is read-only. No game-client integration or final strength
ranking. Stored observations are not fabricated expected recommendations.
"""
import argparse
import copy
import hashlib
import json
import sqlite3
from collections import Counter,defaultdict
from pathlib import Path
import policy as compatibility
import card_evidence

ROOT=Path(__file__).resolve().parents[2]
LABELS={'ad':'AD','ap':'AP','bruiser':'Lutador','crit':'Crítico','hybrid':'Híbrido',
        'lethality':'Letalidade','on_hit':'Efeitos ao contato','tank':'Tanque','utility':'Utilidade'}
PROFILE_COLUMNS='id,champion_id,augment_id,selection,archetype,patch,artifact,selector,context_json,metrics_json,item_set_json'


def read(path):return compatibility.read(path)


def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


def connect(root,run):
    directory=root/'data/pipeline/runs'/run
    if directory.parent.resolve()!=(root/'data/pipeline/runs').resolve():raise ValueError('Invalid data run')
    manifest=read(directory/'manifest.json')
    if manifest['run']!=run:raise ValueError('Data manifest mismatch')
    db=sqlite3.connect(f'file:{(directory/"mayhem.sqlite3").resolve().as_posix()}?mode=ro',uri=True)
    db.row_factory=sqlite3.Row
    return db,directory


def path_id(champion,key):return f'aramkit:{champion}:{key}'


def names(db):
    result={};priority={'opgg':0,'blitz':1,'aramkit':2,'arammayhem':3,'aramgg':4}
    records=list(db.execute('SELECT c.entity_id,c.names_json,s.source FROM catalog c JOIN snapshots s ON s.id=c.snapshot_id'))
    records.sort(key=lambda r:priority.get(r['source'],99))
    for locale in ('pt-BR','en-US'):
        for row in records:
            value=json.loads(row['names_json']).get(locale)
            if value:result.setdefault(row['entity_id'],{'text':value,'locale':locale,'fallback':locale!='pt-BR'})
    return result


def extract_registry(root,run):
    db,directory=connect(root,run)
    try:
        lookup=names(db);state=read(directory/'source-state.json')['aramkit'];paths=[]
        conditional={}
        for row in db.execute('SELECT champion_id,archetype,count(*) AS profiles,count(distinct augment_id) AS cards FROM build_profiles WHERE augment_id IS NOT NULL GROUP BY champion_id,archetype'):
            conditional[row['champion_id'],row['archetype']]={'profiles':row['profiles'],'cards':row['cards']}
        for row in db.execute('SELECT champion_id,archetype,count(*) AS profiles FROM build_profiles WHERE augment_id IS NULL AND selection="filtered" GROUP BY champion_id,archetype ORDER BY champion_id,archetype'):
            champion=row['champion_id'];key=row['archetype'];counts=conditional.get((champion,key),{'profiles':0,'cards':0})
            paths.append({'id':path_id(champion,key),'champion_id':champion,
                'champion_name':lookup.get(champion,{'text':champion,'fallback':True}),
                'source':'aramkit','native_key':key,'label_pt_BR':LABELS.get(key,key),
                'release':state['release'],'snapshot_id':state['snapshot_id'],
                'general_profiles':row['profiles'],'conditional_profiles':counts['profiles'],
                'cards_with_conditional_profiles':counts['cards']})
        expected={r[0] for r in db.execute('SELECT DISTINCT entity_id FROM catalog WHERE entity_id LIKE "champion:game:%"')}
        actual={r['champion_id'] for r in paths}
        if actual!=expected:raise ValueError(f'Build-path coverage mismatch: missing {sorted(expected-actual)}')
        return {'schema_version':1,'data_run':run,'source':'aramkit',
            'data_manifest_sha256':compatibility.sha(directory/'manifest.json'),
            'paths':paths,'coverage':{'champions':len(actual),'paths':len(paths),
                'path_count_distribution':dict(Counter(Counter(p['champion_id'] for p in paths).values())),
                'native_keys':dict(Counter(p['native_key'] for p in paths)),
                'conditional_paths_not_exposed_without_general_path':len(set(conditional)-{(p['champion_id'],p['native_key']) for p in paths})},
            'note':'Only source-published general filtered paths are selectable. Conditional-only labels are not invented as general paths. No item-set export is performed.'}
    finally:db.close()


def decode_profile(row,lookup):
    data=dict(row)
    for key in ('context_json','metrics_json','item_set_json'):data[key[:-5]]=json.loads(data.pop(key))
    data['item_names']=[lookup.get(i,{'text':i,'fallback':True}) for i in data['item_set']]
    return data


class Bench:
    def __init__(self,root=ROOT,policy=None,registry=None):
        self.root=Path(root);self.policy=policy or compatibility.load_policy(self.root)
        registry_path=self.root/self.policy['build_paths']['registry_path']
        if registry is None:
            if compatibility.sha(registry_path)!=self.policy['build_paths']['registry_sha256']:
                raise ValueError('Build registry changed')
            registry=read(registry_path)
        self.registry=registry
        if registry['data_run']!=self.policy['data_run']:raise ValueError('Registry and policy reference different data')
        self.db,self.directory=connect(self.root,self.policy['data_run'])
        if compatibility.sha(self.directory/'manifest.json')!=registry['data_manifest_sha256']:
            raise ValueError('Pinned data manifest changed')
        self.lookup=names(self.db)
        self.rarities={r['entity_id']:json.loads(r['attributes_json']).get('rarity')
            for r in self.db.execute('SELECT c.entity_id,c.attributes_json FROM catalog c JOIN snapshots s ON s.id=c.snapshot_id WHERE s.source="opgg" AND c.entity_id LIKE "augment:%"')}
        self.paths={p['id']:p for p in registry['paths']}
        self.profiles={};self.baselines={};self.popularity={}

    def close(self):self.db.close()

    def get_path(self,champion,key):
        pid=path_id(champion,key)
        if pid not in self.paths:raise ValueError(f'No predefined path for champion: {pid}')
        return self.paths[pid]

    def get_profiles(self,champion,key,augment=None):
        cache=(champion,key,augment)
        if cache not in self.profiles:
            sql='SELECT '+PROFILE_COLUMNS+' FROM build_profiles WHERE champion_id=? AND archetype=?'
            args=[champion,key]
            if augment is None:sql+=' AND augment_id IS NULL AND selection="filtered"'
            else:sql+=' AND augment_id=? AND selection="single_augment"';args.append(augment)
            records=[decode_profile(r,self.lookup) for r in self.db.execute(sql,args)]
            # A reproducible, largest-sample illustration; never select maximum WR.
            records.sort(key=lambda r:(-r['metrics'].get('sample_count',{}).get('value',0),r['id']))
            self.profiles[cache]=records
        return self.profiles[cache]

    def baseline(self,champion,augment,stage):
        key=(champion,augment,stage)
        if key not in self.baselines:
            rows=[]
            for row in self.db.execute('SELECT o.*,s.source FROM observations o JOIN snapshots s ON s.id=o.snapshot_id WHERE entity_id=? AND champion_id=? AND scope="champion" ORDER BY s.source,o.id',(augment,champion)):
                c=json.loads(row['context_json']);flags=json.loads(row['flags_json'])
                if c.get('ranking_scope'):continue
                if c.get('stage') not in (None,'all',str(stage)):continue
                rows.append({'source':row['source'],'patch':row['patch'],'stats_date':row['stats_date'],
                    'stage':c.get('stage'),'context':c,'metrics':json.loads(row['metrics_json']),
                    'artifact':row['artifact'],'selector':row['selector'],'flags':flags,
                    'historical':any('historical' in f for f in flags),
                    'path_specific':False})
            self.baselines[key]=rows
        return self.baselines[key]

    def assess(self,state,candidate,review_facts=None):
        champion=state['champion_id'];path=self.get_path(champion,state['active_path'])
        profiles=self.get_profiles(champion,path['native_key'],candidate)
        context={'candidate_id':candidate,'champion_id':champion,'build_id':path['id'],
            'selected_augments':list(state['selected_augments']),'items':list(state['items']),
            'stage':state['stage'],'decision_horizon':'remainder_of_match',
            'data_run':self.policy['data_run'],'policy_version':self.policy['policy_version'],
            'path_snapshot_id':path['snapshot_id'],'facts':review_facts or {}}
        fit=compatibility.evaluate(self.policy,context)
        references=self.baseline(champion,candidate,state['stage'])
        assessment={'candidate_id':candidate,'name':self.lookup.get(candidate,{'text':candidate,'fallback':True}),
            'path_id':path['id'],'compatibility':fit,'conditional_profile_count':len(profiles),
            'representative_profile':profiles[0] if profiles else None,
            'reference_metrics':references,'evidence_scope':'champion_path_single_augment' if profiles else
                'champion_only' if references else 'missing',
            'selected_augments_jointly_conditioned':False,
            'current_items_conditioned':False,
            'limitations':['Profiles describe completed three-item sets; selection/survival bias remains.',
                'No profile counts or samples are summed. Largest sample is illustrative, not a best-build claim.',
                'Single-augment profiles do not estimate the joint effect of previously selected augments.',
                'Missing path profiles do not imply a weak, incompatible or impossible card.']}
        if champion not in self.popularity:self.popularity[champion]=card_evidence.popularity_ranks(self.db,champion)
        assessment['evidence_card']=card_evidence.describe(self.db,assessment,state,self.popularity[champion])
        return assessment

    def snapshot(self,state,review_facts=None):
        path=self.get_path(state['champion_id'],state['active_path'])
        general=self.get_profiles(state['champion_id'],state['active_path'])
        return {'state':copy.deepcopy(state),'active_path':path,
            'owned_item_names':[self.lookup.get(i,{'text':i,'fallback':True}) for i in state['items']],
            'selected_augment_names':[self.lookup.get(a,{'text':a,'fallback':True}) for a in state['selected_augments']],
            'available_paths':[p for p in self.registry['paths'] if p['champion_id']==state['champion_id']],
            'general_item_profiles':general,
            'selected_card_item_evidence':[{'augment_id':a,'profiles':self.get_profiles(state['champion_id'],state['active_path'],a)}
                                          for a in state['selected_augments']],
            'offered_cards':[self.assess(state,a,(review_facts or {}).get(a)) for a in state['offered_augments']],
            'final_recommendation':None,'strength_tier':None,
            'review_status':'needs_human_judgment_not_labeled_ground_truth'}

    def audit_all_paths(self):
        probes=['augment:game:1205','augment:game:1206','augment:game:3086']
        records=[]
        for path in self.registry['paths']:
            general=self.get_profiles(path['champion_id'],path['native_key'])
            if not general:raise AssertionError('Selectable path has no source profiles')
            cards=[]
            for candidate in probes:
                profiles=self.get_profiles(path['champion_id'],path['native_key'],candidate)
                if any(p['champion_id']!=path['champion_id'] or p['archetype']!=path['native_key'] or p['augment_id']!=candidate for p in profiles):
                    raise AssertionError('Conditional profile leaked across path/champion/card')
                cards.append({'candidate_id':candidate,'conditional_profiles':len(profiles)})
            records.append({'path_id':path['id'],'champion_id':path['champion_id'],
                'general_profiles':len(general),'probe_cards':cards,'passed':True})
        return {'champions':len({r['champion_id'] for r in records}),'paths':len(records),
            'passed':all(r['passed'] for r in records),'records':records,
            'scope':'All selectable paths; probes test data retrieval, not offer eligibility or recommendation quality.'}

    def replay(self,scenario):
        if scenario.get('kind')!='simulated_offers_real_data':raise ValueError('Unsupported replay kind')
        state=copy.deepcopy(scenario['initial_state']);state.setdefault('selected_augments',[])
        state.setdefault('items',[]);state.setdefault('offered_augments',[])
        self.get_path(state['champion_id'],state['active_path'])
        facts=copy.deepcopy(scenario.get('review_facts',{}));steps=[]
        for number,event in enumerate(scenario['events'],1):
            previous=copy.deepcopy(state);action=event['action']
            if action=='offer':
                offered=list(event['augments'])
                if len(set(offered))!=len(offered):raise ValueError('Duplicate offered card')
                if set(offered).intersection(state['selected_augments']):raise ValueError('Already-owned card offered in fixture')
                if scenario.get('require_same_rarity'):
                    rarities={self.rarities.get(a) for a in offered}
                    if None in rarities or len(rarities)!=1:raise ValueError('Scenario offer has unknown or mixed rarities')
                state['offered_augments']=offered
            elif action=='switch_path':
                self.get_path(state['champion_id'],event['path']);state['active_path']=event['path']
                if previous['items']!=state['items'] or previous['selected_augments']!=state['selected_augments']:
                    raise AssertionError('Path switch lost actual state')
            elif action=='pick':
                if event['augment'] not in state['offered_augments']:raise ValueError('Pick was not offered')
                state['selected_augments'].append(event['augment']);state['offered_augments']=[]
            elif action=='buy':
                # Records a simulated real purchase, not a target-build editor.
                if self.db.execute('SELECT 1 FROM entities WHERE id=? AND kind="item"',(event['item'],)).fetchone() is None:
                    raise ValueError('Unknown purchased item')
                state['items'].append(event['item'])
            elif action=='advance_stage':
                if event['stage']<=state['stage']:raise ValueError('Stage must advance')
                state['stage']=event['stage']
            else:raise ValueError(f'Unknown action: {action}')
            snapshot=self.snapshot(state,facts)
            snapshot.update(step=number,event=event,
                context_review_invalidated=any(previous.get(k)!=state.get(k) for k in ('active_path','items','selected_augments','stage')))
            steps.append(snapshot)
        return {'scenario_id':scenario['id'],'kind':scenario['kind'],'policy_version':self.policy['policy_version'],
            'data_run':self.policy['data_run'],'steps':steps,
            'note':'Offers and gameplay are simulated. Data rows are real preserved observations, not proof these cards can be offered together or a validated recommendation.'}


def markdown(report):
    coverage=report['coverage'];lines=['# Bancada offline de caminhos e cartas','',
        f'Política: {report["policy_version"]}. Base: {report["data_run"]}.',
        f'Cobertura: {coverage["champions"]} campeões, {coverage["paths"]} caminhos prontos.',
        '', 'As ofertas são simuladas; as evidências são dos snapshots reais. As cartas mostram efeitos e indicadores das fontes, sem tier agregado.',
        'O objetivo inicial é apoiar sua escolha. Não é necessário conhecer os nomes ou fornecer uma escolha correta para usar o módulo.',
        'Tiers são por campeão. WR da etapa, WR geral e perfis de build têm escopos diferentes.', '']
    for replay in report['replays']:
        lines.extend(['## '+replay['scenario_id'],''])
        for step in replay['steps']:
            state=step['state'];path=step['active_path']
            event_label={'offer':'Oferta de cartas','switch_path':'Troca de caminho','buy':'Compra registrada',
                         'pick':'Carta escolhida','advance_stage':'Avanço de etapa'}[step['event']['action']]
            owned=', '.join(n['text'] for n in step['owned_item_names']) or 'nenhum'
            selected=', '.join(n['text'] for n in step['selected_augment_names']) or 'nenhuma'
            lines.extend([f'### Etapa {step["step"]}: {event_label} — {path["label_pt_BR"]}',
                '',f'Campeão: {path["champion_name"]["text"]}. Etapa da oferta: {state["stage"]}.',
                f'Cartas adquiridas: {selected}. Itens comprados: {owned}.',
                f'Caminhos disponíveis no Arsenal planejado: {len(step["available_paths"])}. Nenhuma importação foi executada.', ''])
            if step['offered_cards']:
                lines.extend(['Os números das fontes continuam separados; não representam votos independentes.', ''])
            for card in step['offered_cards']:
                lines.append(card_evidence.markdown(card['evidence_card'],path['label_pt_BR']))
            if step['offered_cards']:
                lines.extend(['','**Feedback opcional:** a informação foi suficiente para decidir? O que ficou confuso ou faltando?', ''])
    lines.extend(['## Limitações','',
        '- WR de perfis concluídos sofre viés de seleção e não mede o efeito causal da carta.',
        '- Dados de uma carta não são combinados como se descrevessem todas as cartas adquiridas.',
        '- Perfis não condicionam automaticamente os itens já comprados.',
        '- Compatibilidade desconhecida (?) não é veto e não significa carta ruim.',
        '- Os perfis e amostras permanecem separados; tiers das fontes não são somados.',''])
    return '\n'.join(lines)


def run_suite(root,scenario_path):
    policy=compatibility.load_policy(root);bench=Bench(root,policy)
    try:
        suite=read(scenario_path);replays=[bench.replay(s) for s in suite['scenarios']]
        audit=bench.audit_all_paths()
        report={'policy_version':policy['policy_version'],'policy_sha256':policy['_policy_sha256'],
            'evaluator_sha256':policy['_evaluator_sha256'],'bench_sha256':compatibility.sha(Path(__file__)),
            'card_evidence_module_version':card_evidence.MODULE_VERSION,
            'card_evidence_module_sha256':compatibility.sha(Path(card_evidence.__file__)),
            'scenarios_sha256':compatibility.sha(scenario_path),'registry_sha256':policy['build_paths']['registry_sha256'],
            'data_run':policy['data_run'],'coverage':bench.registry['coverage'],
            'all_paths_audit':{'champions':audit['champions'],'paths':audit['paths'],'passed':audit['passed']},'replays':replays}
        rid=digest(report)[:20];folder=root/'data/recommendation/reviews'/rid
        folder.mkdir(parents=True,exist_ok=True)
        if (folder/'report.json').exists() and read(folder/'report.json')!=report:raise ValueError('Review run conflict')
        write(folder/'report.json',report)
        write(folder/'coverage-audit.json',audit)
        (folder/'report.md').write_text(markdown(report),encoding='utf-8')
        judgments=folder/'judgments.json'
        if not judgments.exists():
            write(judgments,{'kind':'optional_user_feedback_not_required_ground_truth',
                'instructions_pt_BR':'Use os indicadores para decidir. Se desejar registrar feedback, descreva o que foi suficiente, confuso ou faltou; não é necessário conhecer os nomes nem fornecer a resposta correta. Não edite os relatórios gerados.',
                'entries':[{'scenario_id':r['scenario_id'],'step':s['step'],
                    'offered_candidates':[c['candidate_id'] for c in s['offered_cards']],
                    'preferred_candidate':None,'reason':None,'missing_evidence':[],
                    'information_sufficient':None,'unclear_indicators':[],'review_status':'optional'}
                    for r in replays for s in r['steps'] if s['offered_cards']]})
        files={p.name:compatibility.sha(p) for p in folder.iterdir() if p.name in ('report.json','report.md','coverage-audit.json')}
        write(folder/'manifest.json',{'review_run':rid,'outputs':files,'data_run':policy['data_run']})
        write(root/'data/recommendation/reviews/current.json',{'review_run':rid,'path':rid})
        return {'review_run':rid,'report':str((folder/'report.md').resolve()),'scenarios':len(replays),
            'steps':sum(len(r['steps']) for r in replays),'coverage':bench.registry['coverage']}
    finally:bench.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__);subs=parser.add_subparsers(dest='command',required=True)
    p=subs.add_parser('prepare-registry');p.add_argument('--data-run',required=True);p.add_argument('--output',type=Path,required=True)
    p=subs.add_parser('replay');p.add_argument('--scenarios',type=Path,required=True)
    p=subs.add_parser('paths');p.add_argument('--champion',required=True)
    args=parser.parse_args()
    if args.command=='prepare-registry':
        result=extract_registry(ROOT,args.data_run)
        if args.output.exists() and read(args.output)!=result:raise ValueError('Immutable registry already exists')
        write(args.output,result);print(json.dumps(result['coverage'],indent=2));return
    if args.command=='replay':result=run_suite(ROOT,args.scenarios)
    else:
        bench=Bench()
        try:result=[p for p in bench.registry['paths'] if p['champion_id']==args.champion]
        finally:bench.close()
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
