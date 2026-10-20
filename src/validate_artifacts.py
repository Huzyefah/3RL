"""Validate evidence integrity and causal experiment invariants; no app/cloud tests."""
from pathlib import Path
import json, hashlib, re
import numpy as np
import pandas as pd
from jsonschema import Draft202012Validator, FormatChecker
from scenarios import simulate, detect, ground_truth, FEATURES

ROOT=Path(__file__).resolve().parents[1]

def run():
    checks=[]
    def check(name,condition,detail):
        checks.append(dict(check=name,passed=bool(condition),detail=detail))
        if not condition:raise AssertionError(name+': '+detail)
    raw=ROOT/'data/raw/ps02_system_telemetry.csv';d=pd.read_csv(raw)
    provenance=json.loads((ROOT/'docs/provenance.json').read_text())
    check('source_hash',hashlib.sha256(raw.read_bytes()).hexdigest()==provenance['sources']['telemetry_csv']['sha256'],'Raw output copy exactly matches supplied CSV hash.')
    check('source_inventory',d.shape==(500,10) and int(d.is_incident.sum())==28,'500x10, 28 positives.')
    check('ratio_label_partition',np.array_equal(np.select([d.value/d.threshold>=.95,d.value/d.threshold>=.75],['CRITICAL','WARNING'],default='NORMAL'),d.alert_level),'Diagnostic exact partition, not predictive validation.')
    expected={'exceed_supplied_threshold':[0,0,28,472],'ratio_ge_0.95':[28,22,0,450]}
    base=pd.read_csv(ROOT/'reports/evaluation/organizer_baseline_results.csv')
    for name,values in expected.items():
        r=base[(base.split=='all_exploratory')&(base.detector==name)].iloc[0]
        check('confusion_'+name,[int(r[x]) for x in ['tp','fp','fn','tn']]==values,'Independent stored-count reconciliation.')
    config=json.loads((ROOT/'data/scenarios/experiment_config.json').read_text());manifest=json.loads((ROOT/'data/scenarios/manifest.json').read_text())
    check('seed_disjoint',len({x['seed'] for x in manifest})==96,'96 unique seeds across partitions.')
    check('feature_scope',FEATURES==config['feature_allowlist'],'Detector uses only explicit metrics, no run ID, timestamp or fault/target.')
    hashes={};total=0
    for split,n in [('train',24),('validation',24),('test',48)]:
        data=pd.read_csv(ROOT/f'data/processed/synthetic/{split}_features.csv');total+=len(data)
        check('partition_'+split,len(data)==n*180 and data.run_key.nunique()==n and not data.isna().any().any(),'Expected full sequences and no missing values.')
        hashes[split]=set()
        for key,g in data.groupby('run_key'):
            c=next(x for x in manifest if x['run_key']==key);fresh=simulate(c)
            check('reproduce_'+key,np.allclose(g[FEATURES],fresh[FEATURES],atol=1e-7,rtol=1e-9),'Saved feature values reproduce fixed seed and rules.')
            check('onset_'+key,ground_truth(g)[0]==c['incident_onset_step'],'Ground truth computed independently from breach rule.')
            hashes[split].add(hashlib.sha256(g[FEATURES].to_csv(index=False).encode()).hexdigest())
    check('total_synthetic_rows',total==17280,'96 sequences x 180 windows.')
    check('no_exact_sequence_overlap',not hashes['train']&hashes['validation'] and not hashes['train']&hashes['test'] and not hashes['validation']&hashes['test'],'No exact cross-partition feature sequence duplicates.')
    c=next(x for x in manifest if x['partition']=='test' and x['kind']=='retry_storm');normal=simulate(c);acted=simulate(c,action_at=80)
    check('paired_pre_action',np.array_equal(normal[FEATURES].iloc[:80],acted[FEATURES].iloc[:80]),'Intervention cannot affect earlier windows.')
    check('paired_exogenous_noise',np.array_equal(normal[['arrival_tps','provider_latency_ms','capacity_tps']],acted[['arrival_tps','provider_latency_ms','capacity_tps']]),'Demand/provider/capacity identical in both branches.')
    for prefix in [35,60,90,120]:
        full=detect(normal,'hybrid',config['chosen_z']);part=detect(normal.iloc[:prefix],'hybrid',config['chosen_z'])
        check('causal_prefix_'+str(prefix),np.array_equal(full[:prefix],part),'Future rows do not alter past detector outputs after warmup.')
    schema=json.loads((ROOT/'contracts/telemetry_event.schema.json').read_text());Draft202012Validator.check_schema(schema)
    validator=Draft202012Validator(schema,format_checker=FormatChecker())
    examples=json.loads((ROOT/'contracts/example_events.json').read_text())
    for example in examples:validator.validate(example)
    check('four_event_examples',len(examples)==4,'Metric/log/event/span examples validate with timezone-aware timestamps.')
    for name in ['incident_assessment.schema.json','model_assessment.schema.json']:
        Draft202012Validator.check_schema(json.loads((ROOT/'contracts'/name).read_text()))
    check('json_schemas_valid',True,'All contracts parse and pass Draft 2020-12 schema validation.')
    for p in ROOT.rglob('*.json'):
        json.loads(p.read_text())
    check('all_json_parse',True,'No malformed JSON artifact.')
    broken=[]
    for p in ROOT.rglob('*.md'):
        for link in re.findall(r'\]\(([^)]+)\)',p.read_text()):
            if '://' in link or link.startswith('#'):continue
            target=(p.parent/link.split('#')[0]).resolve()
            if target==(ROOT/'reports/verification.json').resolve():continue
            if not target.exists():broken.append(str(p.relative_to(ROOT))+': '+link)
    check('relative_document_links',not broken,'All local Markdown links resolve: '+str(broken))
    figs=list(ROOT.glob('reports/*/figures/*.png'))
    from PIL import Image
    for p in figs:
        with Image.open(p) as im:check('image_'+p.stem,im.width>=800 and im.height>=400,'PNG opens with useful resolution.')
    summary=dict(passed=True,checks_run=len(checks),figure_count=len(figs),checks=checks,
        scope='Artifact integrity and statistical/simulation invariants only; no deployed application, model quality, agent action, or cloud checks.')
    (ROOT/'reports/verification.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps({k:summary[k] for k in ['passed','checks_run','figure_count','scope']},indent=2))
    return summary

if __name__=='__main__':run()
