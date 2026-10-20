"""Synthetic queue/retry simulation and event-level evaluation, not a payment model.

Labels and fault metadata live in manifests and are never detector inputs.
"""
from pathlib import Path
import json, hashlib, time
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
FEATURES=['arrival_tps','attempt_tps','provider_latency_ms','queue_depth','queue_wait_seconds','retry_fraction','error_fraction','capacity_tps']
KINDS=['provider_slow','retry_storm','capacity_loss','normal_surge','transient_spike','healthy']

def config(seed,kind,partition):
    r=np.random.default_rng(seed)
    return dict(seed=seed,kind=kind,partition=partition,steps=180,step_seconds=60,
        fault_start=int(r.integers(48,66)),fault_duration=int(r.integers(38,58)),
        arrival_tps=float(r.uniform(55,65)),capacity_tps=float(r.uniform(80,90)),
        latency_base=float(r.uniform(140,220)),latency_increase=float(r.uniform(350,650)),
        capacity_drop=float(r.uniform(.30,.42)),ramp_steps=int(r.integers(10,20)),
        shape={'train':'linear','validation':'ease','test':'sigmoid'}[partition])

def simulate(c,action_at=None):
    r=np.random.default_rng(c['seed']);n=c['steps'];q=0.;last_retry=.01;rows=[]
    # Pre-generated arrays keep paired action/no-action worlds on common noise.
    demand_noise=r.normal(0,1.3,n);latency_noise=r.normal(0,9,n);capacity_noise=r.normal(0,.7,n)
    for t in range(n):
        active=c['fault_start']<=t<c['fault_start']+c['fault_duration']
        x=np.clip((t-c['fault_start'])/c['ramp_steps'],0,1) if active else 0.
        if c['shape']=='ease':x=x*x
        if c['shape']=='sigmoid':x=float((1/(1+np.exp(-8*(x-.5)))-1/(1+np.exp(4)))/(1/(1+np.exp(-4))-1/(1+np.exp(4)))) if active else 0.
        arrival=max(1,c['arrival_tps']*(1+.025*np.sin(t/13))+demand_noise[t])
        capacity=c['capacity_tps']+capacity_noise[t]
        latency=max(1,c['latency_base']+latency_noise[t])
        kind=c['kind']
        if kind in ['provider_slow','retry_storm']:latency+=c['latency_increase']*x
        if kind=='capacity_loss':capacity*=1-c['capacity_drop']*x
        if kind=='normal_surge' and active:arrival*=1.65;capacity*=1.65
        if kind=='transient_spike' and c['fault_start']<=t<c['fault_start']+2:latency+=600
        # Retry amplification consumes shared worker capacity; retries are attempts,
        # never assumed unique financial transactions.
        retry=float(np.clip(.01+.00065*max(0,latency-250)+.0015*max(0,q/capacity-15),.005,.65))
        if kind=='retry_storm' and active:retry=max(retry,.18*x)
        if action_at is not None and t>=action_at:retry=min(retry,.02)
        attempts=arrival*(1+last_retry)
        q=max(0.,q+(attempts-capacity)*60)
        wait=q/capacity
        error=float(np.clip(.001+.0008*max(0,wait-60)+.00003*max(0,latency-850),0,.95))
        rows.append(dict(step=t,arrival_tps=arrival,attempt_tps=attempts,provider_latency_ms=latency,
            queue_depth=q,queue_wait_seconds=wait,retry_fraction=retry,error_fraction=error,capacity_tps=capacity))
        last_retry=retry
    return pd.DataFrame(rows)

def sustained(mask,n):
    return pd.Series(mask).rolling(n,min_periods=n).sum().eq(n).to_numpy()

def ground_truth(d):
    bad=(d.queue_wait_seconds>120)|(d.error_fraction>.05)
    hits=np.flatnonzero(sustained(bad,3))
    if not len(hits):return None,None
    onset=int(hits[0]-2)  # retrospective first window in sustained breach
    last=int(np.flatnonzero(bad)[-1])
    return onset,last

def detect(d,method='hybrid',z_limit=4.):
    # Only explicit causal-prefix feature series. No manifests, IDs or target columns.
    x=d[FEATURES].copy()
    if method=='static':return sustained((x.provider_latency_ms>800)|(x.queue_wait_seconds>120)|(x.error_fraction>.05),2)
    base=x.provider_latency_ms.iloc[:30]
    scale=max(1.4826*(base-base.median()).abs().median(),15.)
    z=(x.provider_latency_ms-base.median())/scale
    latency_signal=z>z_limit
    retry_signal=x.retry_fraction>.08
    growth=x.queue_depth.diff(3).fillna(0)/180
    queue_signal=(growth>2)&(x.queue_wait_seconds>20)
    return sustained((latency_signal&retry_signal)|queue_signal,3)&(np.arange(len(d))>=30)

def episodes(mask,cooldown=10):
    starts=[];last=-10000;was=False
    for i,v in enumerate(mask):
        if v and not was and i-last>=cooldown:starts.append(i);last=i
        was=bool(v)
    return starts

def evaluate(runs,configs,method,z=4.):
    records=[];tp=fp=fn=tn=0;latencies=[]
    for key,d in runs.items():
        started=time.perf_counter();mask=detect(d,method,z);latencies.append(1000*(time.perf_counter()-started))
        onset,end=ground_truth(d);alarms=episodes(mask)
        # At-risk windows include up to 20 minutes before onset through incident end.
        target=np.zeros(len(d),dtype=bool)
        if onset is not None:target[max(0,onset-20):end+1]=True
        tp+=int((target&mask).sum());fp+=int((~target&mask).sum());fn+=int((target&~mask).sum());tn+=int((~target&~mask).sum())
        early=[a for a in alarms if onset is not None and max(30,onset-20)<=a<onset]
        late=[a for a in alarms if onset is not None and onset<=a<=end]
        unmatched=[a for a in alarms if onset is None or a<onset-20 or a>end]
        records.append(dict(run_key=key,kind=configs[key]['kind'],method=method,onset_step=onset,end_step=end,
            first_early_step=early[0] if early else None,lead_minutes=onset-early[0] if early else None,
            late_only=bool(late and not early),missed=bool(onset is not None and not early and not late),
            alarm_episodes=len(alarms),unmatched_episodes=len(unmatched),early_matched=int(bool(early)),
            event_detected=int(bool(early or late)),has_incident=int(onset is not None)))
    table=pd.DataFrame(records);events=int(table.has_incident.sum());matched=int(table.event_detected.sum());unmatched=int(table.unmatched_episodes.sum());leads=table.lead_minutes.dropna()
    summary=dict(method=method,z_limit=z,runs=len(runs),incident_runs=events,negative_runs=len(runs)-events,
        tp=tp,fp=fp,fn=fn,tn=tn,window_precision=tp/(tp+fp) if tp+fp else None,window_recall=tp/(tp+fn) if tp+fn else None,
        window_f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0,window_fpr=fp/(fp+tn),
        event_precision=matched/(matched+unmatched) if matched+unmatched else None,event_recall=matched/events if events else None,
        early_event_recall=int(table.early_matched.sum())/events if events else None,
        negative_run_false_alarm_rate=float((table.loc[table.has_incident==0,'alarm_episodes']>0).mean()),
        unmatched_alarm_episodes=unmatched,late_only=int(table.late_only.sum()),missed=int(table.missed.sum()),
        lead_minutes_quantiles=leads.quantile([0,.25,.5,.75,1]).to_dict() if len(leads) else {},
        local_detector_ms_per_180row_run_p50=float(np.median(latencies)),local_detector_ms_per_180row_run_p95=float(np.quantile(latencies,.95)))
    return table,summary

def run():
    dest=ROOT/'data/processed/synthetic';dest.mkdir(parents=True,exist_ok=True)
    man=ROOT/'data/scenarios';man.mkdir(parents=True,exist_ok=True)
    out=ROOT/'reports/evaluation';out.mkdir(parents=True,exist_ok=True)
    manifests=[];allruns={};cfg={};sources=[]
    for split,count,offset in [('train',4,1000),('validation',4,2000),('test',8,3000)]:
        runs={};cs={}
        for ki,kind in enumerate(KINDS):
            for j in range(count):
                seed=offset+ki*100+j;key=f'{split}-{ki*count+j:03d}';c=config(seed,kind,split);d=simulate(c)
                d.insert(0,'timestamp',pd.date_range('2026-09-01',periods=len(d),freq='min',tz='UTC').astype(str))
                d.insert(0,'run_key',key);runs[key]=d;cs[key]=c;cfg[key]=c
                onset,end=ground_truth(d)
                manifests.append(dict(run_key=key,**c,incident_onset_step=onset,incident_end_step=end,synthetic=True))
                if kind in ['provider_slow','retry_storm']:
                    sources.append(dict(run_key=key,step=c['fault_start']+5,kind='log',service='provider-adapter',code='UPSTREAM_SLOW_RESPONSE',message='Observed upstream response duration elevated; cause unverified.'))
                if kind=='normal_surge':sources.append(dict(run_key=key,step=c['fault_start'],kind='event',service='checkout',code='CAMPAIGN_STARTED',message='Scheduled campaign; capacity increased.'))
        pd.concat(runs.values()).to_csv(dest/f'{split}_features.csv',index=False,float_format='%.8f');allruns[split]=runs
    (man/'manifest.json').write_text(json.dumps(manifests,indent=2))
    (man/'context_events.jsonl').write_text('\n'.join(json.dumps(x) for x in sources)+'\n')
    # Tune on validation only; objective prefers earlier event coverage, penalizes false alarms.
    sweep=[]
    for z in [3.,4.,5.,6.]:
        _,s=evaluate(allruns['validation'],cfg,'hybrid',z);s['selection_score']=s['early_event_recall']-2*s['negative_run_false_alarm_rate'];sweep.append(s)
    chosen=sorted(sweep,key=lambda x:(-x['selection_score'],-x['z_limit']))[0]['z_limit']
    (out/'synthetic_validation_sweep.json').write_text(json.dumps(sweep,indent=2))
    (man/'experiment_config.json').write_text(json.dumps(dict(version='1.0',z_candidates=[3,4,5,6],chosen_z=chosen,selection='maximize validation early recall minus twice negative-run false-alarm rate; tie favors higher z',feature_allowlist=FEATURES,warning_horizon_minutes=20,cooldown_minutes=10,seed_ranges={'train':1000,'validation':2000,'test':3000},heldout_shape='sigmoid; same simulator family, not independent real-world validation'),indent=2))
    summaries=[];tables=[]
    for split in ['train','validation','test']:
        for method in ['static','hybrid']:
            table,s=evaluate(allruns[split],cfg,method,chosen);table['partition']=split;s['partition']=split;summaries.append(s);tables.append(table)
    pd.concat(tables).to_csv(out/'synthetic_scenario_metrics.csv',index=False)
    (out/'synthetic_results.json').write_text(json.dumps(summaries,indent=2))
    pairs=[]
    for key,d in allruns['test'].items():
        alarms=episodes(detect(d,'hybrid',chosen));act=alarms[0]+1 if alarms else None
        post=simulate(cfg[key],action_at=act)
        before_minutes=int(((d.queue_wait_seconds>120)|(d.error_fraction>.05)).sum());after_minutes=int(((post.queue_wait_seconds>120)|(post.error_fraction>.05)).sum())
        pairs.append(dict(run_key=key,kind=cfg[key]['kind'],action_at_step=act,simulation=True,
            before_breach_minutes=before_minutes,after_breach_minutes=after_minutes,breach_minutes_reduced=before_minutes-after_minutes,
            before_max_queue=float(d.queue_depth.max()),after_max_queue=float(post.queue_depth.max()),
            before_expected_failed_attempts=float((d.attempt_tps*60*d.error_fraction).sum()),after_expected_failed_attempts=float((post.attempt_tps*60*post.error_fraction).sum())))
    pd.DataFrame(pairs).to_csv(out/'paired_intervention_results.csv',index=False)
    valid=[]
    for split,runs in allruns.items():
        frame=pd.concat(runs.values());valid.append(dict(partition=split,runs=len(runs),rows=len(frame),null_cells=int(frame.isna().sum().sum()),duplicate_with_run_step=int(frame.duplicated(['run_key','step']).sum()),negative_features=int((frame[FEATURES]<0).sum().sum()),uniform_one_minute_steps=all(d.step.diff().dropna().eq(1).all() for d in runs.values()),feature_schema_no_target_or_fault_fields=not any(x in frame for x in ['kind','seed','shape','is_incident','incident_onset_step','fault_start'])))
    assert all(v['null_cells']==0 and v['duplicate_with_run_step']==0 and v['negative_features']==0 and v['uniform_one_minute_steps'] and v['feature_schema_no_target_or_fault_fields'] for v in valid)
    hashes={s:{hashlib.sha256(d[FEATURES].to_csv(index=False).encode()).hexdigest() for d in runs.values()} for s,runs in allruns.items()}
    assert not hashes['train']&hashes['test'] and not hashes['validation']&hashes['test'] and not hashes['train']&hashes['validation']
    (out/'synthetic_validation_checks.json').write_text(json.dumps(dict(partitions=valid,cross_partition_exact_sequence_overlap=0,partition_seed_sets_disjoint=True,causal_generator=True),indent=2))
    # Save complete controlled pair for a transparent offline demonstration.
    demo=next(k for k in allruns['test'] if cfg[k]['kind']=='retry_storm')
    base=allruns['test'][demo];alarms=episodes(detect(base,'hybrid',chosen));a=alarms[0]+1 if alarms else None
    base.to_csv(dest/'demo_no_action.csv',index=False);simulate(cfg[demo],a).to_csv(dest/'demo_with_retry_cap.csv',index=False)
    print(json.dumps(dict(chosen_z=chosen,test=[s for s in summaries if s['partition']=='test'],intervention_breach_reduction=sum(p['breach_minutes_reduced'] for p in pairs)),indent=2))

if __name__=='__main__':run()
