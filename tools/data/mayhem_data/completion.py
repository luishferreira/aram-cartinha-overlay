"""Audit and promote a complete MCP acquisition, keeping prior research intact."""
import shutil
from collections import Counter
from pathlib import Path
from .common import ROOT, read, write, atomic_json, digest
from .mcp import structured


def audit(workspace):
    workspace=Path(workspace)
    state=read(workspace/'intake.json')
    if state.get('status')!='complete':raise ValueError('Intake is not complete; resume collection before promotion.')
    folder=workspace/'research/arammayhem-mcp/bulk'
    manifest=read(folder/'manifest.json')
    source=workspace/'data/sources/arammayhem'
    pointer=read(source/'current.json');snapshot=source/pointer['snapshot']
    index=read(snapshot/'index.json')
    if not manifest.get('complete') or manifest['release_id']!=index['releaseId']:
        raise ValueError('MCP release completeness or identity mismatch')
    if len(manifest['files'])!=manifest['expected_requests']:raise ValueError('MCP request count mismatch')
    if digest((folder/'tools.json').read_bytes())!=manifest['tools_sha256']:raise ValueError('MCP tools hash mismatch')
    expected_champions={r['championId'] for r in read(snapshot/'latest/champions.json')['rows']}
    expected_augments=set()
    latest_augments={r['augmentId'] for r in read(snapshot/'latest/augments.json')['rows']}
    for path in snapshot.rglob('augments.json'):expected_augments.update(r['augmentId'] for r in read(path)['rows'])
    expected_combos={r['url'] for r in read(snapshot/'latest/combos.json')['rows']}
    for row in read(snapshot/'latest/combos.json')['rows']:expected_augments.update(row['augmentIds'])
    requests=set();files=set();methods=Counter();request_champions={'get_champion_build':set(),'get_top_combos':set()}
    requested_augments=set();available_augments=set();build_champions=set();tier_ids=[]
    combo_urls=set();described_urls=set();weak_descriptions=[];availability=Counter();patches=Counter();live_without_popularity_row=[]
    unavailable=[];errors=[];truncated=[];notes=[];skill_orders=0;skill_paths=0;build_options=0;effect_tokens=[];sequence_lengths=Counter()
    for record in manifest['files']:
        filename=record['file']
        if Path(filename).name!=filename or filename in files:raise ValueError('Duplicate or unsafe MCP file identity')
        files.add(filename)
        path=folder/filename
        if digest(path.read_bytes())!=record['sha256']:raise ValueError('MCP response hash mismatch: '+filename)
        request_id=(record['tool'],tuple(sorted(record['arguments'].items())))
        if request_id in requests:raise ValueError('Duplicate MCP request identity')
        requests.add(request_id)
        method=record['tool'];args=record['arguments'];methods[method]+=1
        if method in request_champions:request_champions[method].add(args['champion'])
        if method=='get_augment':requested_augments.add(args['augment'])
        response=read(path);data=structured(response)
        if data is None:
            if record.get('unavailable'):unavailable.append({'file':filename,'method':method,'arguments':args})
            else:errors.append({'file':filename,'reason':'error_or_unstructured_response'})
            continue
        if data.get('patch'):patches[data['patch']]+=1
        if method!='get_patch_notes' and data.get('patch') and data['patch']!=index['latestPatch']:
            errors.append({'file':filename,'reason':'current_response_patch_mismatch','patch':data['patch']})
        if method=='get_champion_build':
            if not isinstance(data.get('builds'),dict):
                unavailable.append({'file':filename,'method':method,'arguments':args,'reason':'no_structured_builds'})
                continue
            if data.get('championId')!=args['champion']:
                errors.append({'file':filename,'reason':'champion_identity_mismatch'})
            build_champions.add(data['championId'])
            build_options+=sum(len(group) for group in data['builds'].values())
            skill_orders+=len(data.get('skillOrders',[]))
            skill_paths+=sum(len(row.get('paths',[])) for row in data.get('skillOrders',[]))
            for row in data.get('skillOrders',[]):
                for skill_path in row.get('paths',[]):sequence_lengths[len(skill_path['sequence'].split())]+=1
        elif method=='get_top_combos':
            combos=data.get('combos',[])
            if data.get('total',len(combos))>len(combos):truncated.append({'champion':args['champion'],'total':data['total'],'returned':len(combos)})
            for combo in combos:
                combo_urls.add(combo['url'])
                if combo.get('championId')!=args['champion']:
                    errors.append({'file':filename,'reason':'combo_champion_mismatch'})
                description=combo.get('description') or ''
                if description.strip():described_urls.add(combo['url'])
                if description.strip().casefold() in ('','nothing.','nothing','none','no description'):
                    weak_descriptions.append(combo['url'])
        elif method=='get_augment':
            if not data.get('id') or 'availability' not in data:
                unavailable.append({'file':filename,'method':method,'arguments':args,'reason':'no_structured_augment'})
                continue
            available_augments.add(data['id']);availability[data['availability']]+=1
            if data['availability']=='live' and data['id'] not in latest_augments:
                live_without_popularity_row.append({'id':data['id'],'name':data.get('name'),'pick_rate':data.get('pickRate')})
            if data['id']!=args['augment']:errors.append({'file':filename,'reason':'augment_identity_mismatch'})
            if '@' in (data.get('description') or ''):effect_tokens.append(data['id'])
        elif method=='get_tier_list':tier_ids.extend(r['championId'] for r in data.get('entries',[]))
        elif method=='get_patch_notes':
            requested=args.get('patch',index['latestPatch'])
            if data.get('patch')!=requested:
                errors.append({'file':filename,'reason':'patch_note_identity_mismatch','requested':requested,'received':data.get('patch')})
            notes.append({'patch':data.get('patch'),'date':data.get('dataDate'),'file':filename})
    if requested_augments!=expected_augments:errors.append({'reason':'augment_request_coverage_mismatch',
        'missing':sorted(expected_augments-requested_augments),'unexpected':sorted(requested_augments-expected_augments)})
    for method,ids in request_champions.items():
        if ids!=expected_champions:errors.append({'reason':'champion_request_coverage_mismatch','method':method,'missing':sorted(expected_champions-ids)})
    if set(tier_ids)!=expected_champions or len(tier_ids)!=len(expected_champions):errors.append({'reason':'tier_pagination_incomplete_or_duplicate'})
    if truncated:errors.append({'reason':'combo_endpoint_truncated','details':truncated})
    expected_patches={r['patch'] for r in index['patches']}
    unexpected_current_patches={p for p in patches if p not in expected_patches}
    if unexpected_current_patches:errors.append({'reason':'unexpected_response_patches','patches':sorted(unexpected_current_patches)})
    report={'release_id':index['releaseId'],'latest_patch':index['latestPatch'],
        'responses_verified':len(files),'methods':dict(methods),
        'expected_champions':len(expected_champions),'champions_with_build_responses':len(build_champions),
        'champion_tier_entries':len(tier_ids),'expected_augment_ids':len(expected_augments),
        'augment_details_available':len(available_augments),'augment_availability':dict(availability),
        'mcp_live_augments_absent_from_latest_popularity_download':live_without_popularity_row,
        'expected_combo_urls':len(expected_combos),'combo_urls_received':len(combo_urls),
        'combos_with_explanations':len(described_urls),'combos_with_weak_or_empty_explanations':weak_descriptions,
        'missing_combo_urls':sorted(expected_combos-combo_urls),'extra_combo_urls':sorted(combo_urls-expected_combos),
        'build_options':build_options,'skill_orders':skill_orders,'skill_paths':skill_paths,
        'skill_sequence_token_counts':dict(sequence_lengths),
        'patch_notes':notes,'patch_note_coverage_missing':sorted(expected_patches-{r['patch'] for r in notes}),
        'effect_descriptions_with_unresolved_tokens':effect_tokens,
        'unavailable':unavailable,'errors':errors,'truncated':truncated,
        'complete_requests':not errors,'source_limits':[
            'Combos are editorial and do not supply measured combination win rates.',
            'Build groups contain at most three published options and are not augment-conditioned.',
            'Historical patch notes are third-party summaries, not official Riot validation.',
            'English acquisition; PT-BR uses the separate localized catalogs.',
            'Skill path sequences preserve source tokens; level range and initial allocations are not inferred.',
            'Search has unbounded query space; catalog/history IDs define this acquisition universe.']}
    if expected_combos-combo_urls:report['errors'].append({'reason':'downloaded_combos_missing_from_mcp'})
    report['complete_requests']=not report['errors']
    write(workspace/'mcp-completion-report.json',report)
    return report


def promote(workspace,root=ROOT):
    workspace=Path(workspace);root=Path(root)
    report=audit(workspace)
    if not report['complete_requests']:raise ValueError('MCP completeness audit rejected promotion')
    bulk=workspace/'research/arammayhem-mcp/bulk'
    manifest=read(bulk/'manifest.json');snapshot_id=digest(manifest)[:20]
    target=root/'research/arammayhem-mcp/snapshots'/snapshot_id
    if not target.exists():
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(bulk,target)
    else:
        if digest((target/'manifest.json').read_bytes())!=digest((bulk/'manifest.json').read_bytes()):
            raise ValueError('Promoted manifest hash mismatch')
        if digest((target/'tools.json').read_bytes())!=manifest['tools_sha256']:
            raise ValueError('Promoted tool discovery hash mismatch')
        for record in manifest['files']:
            if digest((target/record['file']).read_bytes())!=record['sha256']:raise ValueError('Promoted response hash mismatch')
    write(target/'coverage.json',report)
    # Keep downloaded data and MCP channel on the same publisher release.
    source=workspace/'data/sources/arammayhem';pointer=read(source/'current.json')
    official_target=root/'data/sources/arammayhem'/pointer['snapshot']
    if not official_target.exists():shutil.copytree(source/pointer['snapshot'],official_target)
    atomic_json(root/'data/sources/arammayhem/current.json',pointer)
    atomic_json(root/'research/arammayhem-mcp/current.json',{
        'snapshot':'snapshots/'+snapshot_id,'release_id':manifest['release_id'],
        'manifest_sha256':digest((target/'manifest.json').read_bytes()),'complete':True})
    return {'snapshot':str(target),'responses':len(manifest['files']),
            'champions':report['champions_with_build_responses'],'combo_explanations':report['combos_with_explanations'],
            'augment_details':report['augment_details_available'],'unavailable':len(report['unavailable'])}
