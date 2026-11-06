"""Decision-support cards. Source tiers and observation scopes remain separate.

No inferred champion abilities, synthesized S/A score or recommendation winner.
"""
import json
import re
from html import escape
from html.parser import HTMLParser

MODULE_VERSION='0.1.0'


class PlainText(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.parts=[];self.hidden=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'):self.hidden+=1
        if tag in ('br','p','li') and not self.hidden:self.parts.append(' ')
    def handle_endtag(self,tag):
        if tag in ('script','style') and self.hidden:self.hidden-=1
        if tag in ('p','li') and not self.hidden:self.parts.append(' ')
    def handle_data(self,data):
        if not self.hidden:self.parts.append(data)


def plain(value):
    if isinstance(value,dict):
        value=' '.join(span.get('text','') for block in value.get('blocks',[]) for span in block.get('spans',[]) if span.get('type')=='text')
    if not isinstance(value,str):return ''
    parser=PlainText();parser.feed(value)
    return re.sub(r'\s+',' ',''.join(parser.parts)).strip()


def value(row,key):return row.get('metrics',{}).get(key,{}).get('value')


def provenance(row):
    return {k:row.get(k) for k in ('source','patch','stats_date','stage','context','artifact','selector','flags','historical','path_specific')}


def reference(rows,source,stage=None,group=None):
    candidates=[r for r in rows if r['source']==source and not r.get('historical')]
    if group:candidates=[r for r in candidates if r.get('context',{}).get('metric_group')==group]
    if source=='aramkit':
        exact=[r for r in candidates if r.get('stage')==str(stage)]
        candidates=exact or [r for r in candidates if r.get('stage') in (None,'all')]
    return candidates[0] if candidates else None


def identity(db,candidate,locale='pt-BR'):
    rows=list(db.execute('SELECT c.*,s.source FROM catalog c JOIN snapshots s ON s.id=c.snapshot_id WHERE entity_id=?',(candidate,)))
    priority={'opgg':0,'blitz':1,'aramkit':2,'arammayhem':3,'aramgg':4}
    rows.sort(key=lambda r:priority.get(r['source'],99))
    names={};effect=None;rarity=None
    for row in rows:
        attrs=json.loads(row['attributes_json']);rarity=rarity or attrs.get('rarity')
        for lang,text in json.loads(row['names_json']).items():
            if text:names.setdefault(lang,text)
    for lang in dict.fromkeys((locale,'en-US','pt-BR')):
        for row in rows:
            description=json.loads(row['descriptions_json']).get(lang,{})
            raw=description.get('description') or description.get('tooltip')
            text=plain(raw)
            if not text:continue
            effect={'text':text,'locale':lang,'fallback':lang!=locale,'source':row['source'],
                'artifact':row['artifact'],'unresolved_values':bool('?' in text or re.search(r'@[^@\s]+@',text)),
                'source_encoding_warning':'\ufffd' in text}
            break
        if effect:break
    requested=names.get(locale);english=names.get('en-US')
    return {'entity_id':candidate,'name':requested or english or candidate,'english_name':english,
        'locale':locale if requested else 'en-US' if english else None,'fallback':not bool(requested),
        'rarity':rarity,'effect':effect or {'text':'Descrição não disponível na base.','locale':None,'fallback':True,'source':None}}


def popularity_ranks(db,champion):
    rows=[]
    for row in db.execute('SELECT o.entity_id,o.metrics_json FROM observations o JOIN snapshots s ON s.id=o.snapshot_id WHERE s.source="opgg" AND o.champion_id=? AND o.scope="champion"',(champion,)):
        metrics=json.loads(row['metrics_json']);popular=metrics.get('popular_raw',{}).get('value')
        performance=metrics.get('performance_raw',{}).get('value')
        if popular is None or (popular==0 and performance==0):continue
        rows.append((row['entity_id'],popular))
    rows.sort(key=lambda r:(-r[1],r[0]));result={};previous=None;rank=None
    for position,(candidate,popular) in enumerate(rows,1):
        if popular!=previous:rank=position
        result[candidate]={'rank':rank,'published_entries':len(rows),'raw_value':popular,
            'method':'descending_published_popular_raw_competition_ranks',
            'meaning':'Calculated position among published nonempty champion entries, not a verified offered-choice pick rate.'}
        previous=popular
    return result


def editorial(db,state,candidate):
    bundles=[];selected=set(state['selected_augments'])
    for row in db.execute('SELECT r.data_json FROM relations r JOIN snapshots s ON s.id=r.snapshot_id WHERE s.source="arammayhem" AND r.champion_id=? AND r.kind="editorial_bundle"',(state['champion_id'],)):
        relation=json.loads(row['data_json'])
        if candidate not in relation['augment_ids']:continue
        bundles.append({'url':relation.get('url'),'listed_augments':relation['augment_ids'],
            'selected_members':sorted(selected.intersection(relation['augment_ids'])),
            'explanation':relation.get('explanation'),'artifact':relation.get('explanation_artifact',relation['artifact']),
            'member_semantics':relation['member_semantics'],'validation':'editorial_hypothesis_not_verified_mechanic'})
    global_tier=None
    for row in db.execute('SELECT o.metrics_json,o.artifact,o.patch,o.stats_date FROM observations o JOIN snapshots s ON s.id=o.snapshot_id WHERE s.source="arammayhem" AND o.entity_id=? AND o.scope="global"',(candidate,)):
        tier=json.loads(row['metrics_json']).get('tier',{}).get('value')
        if tier is not None:
            global_tier={'value':tier,'scope':'global_augment_not_champion_or_build',
                'patch':row['patch'],'stats_date':row['stats_date'],'artifact':row['artifact']}
            break
    return {'source':'arammayhem','global_tier':global_tier,'bundles':bundles,
        'bundles_listing_selected_members':sum(bool(b['selected_members']) for b in bundles),
        'note':'Listed membership does not establish required cards, an active synergy or current availability.'}


def describe(db,assessment,state,popularity=None):
    rows=assessment['reference_metrics'];stage=state['stage'];candidate=assessment['candidate_id']
    info=identity(db,candidate);tiers={};performance=[]
    for source in ('blitz','opgg'):
        row=reference(rows,source)
        tiers[source]={'value':value(row,'tier') if row else None,'scope':'champion_not_build',
            'provenance':provenance(row) if row else None}
    opgg=reference(rows,'opgg')
    tiers['opgg']['popularity']=popularity.get(candidate) if popularity is not None else None
    tiers['opgg']['stats_patch_known']=bool(opgg and opgg.get('patch'))
    for source,group in [('aramkit',None),('aramgg','uploaded_performance')]:
        row=reference(rows,source,stage,group)
        exact=bool(row and row.get('stage')==str(stage))
        performance.append({'source':source,'scope':'champion_stage_not_build' if exact else 'champion_overall_not_build',
            'win_rate':value(row,'win_rate') if row else None,'sample_count':value(row,'sample_count') if row else None,
            'stage':str(stage) if exact else None,'provenance':provenance(row) if row else None})
    profile=assessment['representative_profile']
    path={'scope':'champion_path_single_augment_completed_item_profile',
        'profile_count':assessment['conditional_profile_count'],'profile':profile,
        'not_an_estimate_of_card_uplift':True,'selected_augments_jointly_conditioned':False,
        'current_items_conditioned':False}
    source_values=[r['value'] for r in tiers.values() if r['value'] is not None]
    return {'module_version':MODULE_VERSION,'identity':info,'source_tiers':tiers,
        'performance':performance,'path_evidence':path,'compatibility':assessment['compatibility'],
        'tier_disagreement':len(set(source_values))>1,'combined_tier':None,'selected_winner':False,
        'advanced_reference_metrics':rows,'editorial':editorial(db,state,candidate),
        'notes':['Source tiers describe the champion, not the selected build path.',
            'OP.GG performance_raw is an undefined index, never win rate; popular_raw is not rendered as a percent.',
            'ARAMKit stage performance and ARAMGG overall performance are different cohorts, not independent votes.',
            'Missing data is not evidence of weakness.']}


def pct(number):return f'{number*100:.2f}%' if number is not None else 'sem dado'
def count(number):return f'{number:,}'.replace(',','.') if number is not None else 'não informada'


def md(text):
    text=escape(str(text),quote=False)
    return re.sub(r'([\\`*_{}\[\]()!|])',r'\\\1',text)


def markdown(card,path_label):
    info=card['identity'];en=info['english_name'];name=info['name']
    suffix=f' · {md(en)}' if en and en!=name else ''
    lines=[f'#### {md(name)}{suffix}', '',md(info['effect']['text']),'']
    if info['effect'].get('fallback'):lines.append('Descrição em idioma alternativo; tradução solicitada indisponível.')
    if info['effect'].get('unresolved_values'):lines.append('A descrição da fonte contém valores dinâmicos não resolvidos.')
    blitz=card['source_tiers']['blitz'];opgg=card['source_tiers']['opgg']
    lines.extend(['| Referência | Indicador para este campeão |','|---|---|',
        f'| Blitz | Tier **{md(blitz["value"] or "sem dado")}** |',
        f'| OP.GG | Tier **{md(opgg["value"] or "sem dado")}** |'])
    popularity=opgg.get('popularity')
    if popularity:lines.append(f'| Popularidade OP.GG | Posição calculada **{popularity["rank"]}/{popularity["published_entries"]}** |')
    for perf in card['performance']:
        scope=f'etapa {perf["stage"]}' if perf['stage'] else 'geral do campeão'
        lines.append(f'| {perf["source"].upper()} · {scope} | WR **{pct(perf["win_rate"])}** · amostra **{count(perf["sample_count"])}** |')
    if not opgg['stats_patch_known']:lines.extend(['','OP.GG: patch das estatísticas não informado.'])
    if card['tier_disagreement']:lines.extend(['','**Blitz e OP.GG divergem na classificação.**'])
    fit=card['compatibility']
    if fit['compatibility'] in ('excluded','avoid','conditional'):
        lines.extend(['',f'**Compatibilidade: {md(fit["label"])} — {md(fit["description_pt_BR"])}.**'])
    else:lines.extend(['','Compatibilidade mecânica: ainda sem regra revisada para este contexto.'])
    path=card['path_evidence'];profile=path['profile']
    lines.extend(['',f'**Caminho {md(path_label)}:** {path["profile_count"]} perfis publicados para esta carta.'])
    if not profile:lines.append('Sem perfil específico publicado. Isso não significa carta ruim ou incompatível.')
    lines.extend(['','<details><summary>Detalhes da build e da evidência</summary>',''])
    if profile:
        metrics=profile['metrics'];items=', '.join(n['text'] for n in profile['item_names'])
        lines.extend([f'Perfil de maior amostra: {md(items)}.',
            f'WR desse perfil: {pct(value({"metrics":metrics},"win_rate"))}; amostra: {count(value({"metrics":metrics},"sample_count"))}.',
            'É uma observação de build concluída, não a previsão de escolher esta carta.'])
    if opgg['provenance']:
        raw=next((r for r in card['advanced_reference_metrics'] if r['source']=='opgg'),None)
        if raw:lines.append(f'OP.GG: índice bruto de desempenho {value(raw,"performance_raw")}; unidade não confirmada, não é win rate.')
    for perf in card['performance']:
        p=perf['provenance']
        if p:lines.append(f'{perf["source"]}: patch {p.get("patch") or "desconhecido"}; data estatística {p.get("stats_date") or "não informada"}.')
    ed=card['editorial'];global_tier=ed['global_tier']
    if global_tier:lines.append(f'arammayhem: tier global da carta **{md(global_tier["value"])}**, não específico deste campeão ou caminho.')
    lines.append(f'arammayhem: {len(ed["bundles"])} conjuntos editoriais incluem esta carta no campeão; {ed["bundles_listing_selected_members"]} também listam cartas já escolhidas. São hipóteses, não sinergias confirmadas.')
    lines.extend(['Métricas gerais não são recalculadas como se fossem específicas do caminho.',
        'Os detalhes completos, artefatos e escopos ficam no JSON.','', '</details>',''])
    return '\n'.join(lines)
