"""Reproduce PS-02 descriptive EDA and fixed-rule point baselines. No API calls."""
from pathlib import Path
import json, hashlib, platform
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'reports/eda'
FIG = OUT/'figures'
for p in [OUT, FIG, ROOT/'reports/evaluation', ROOT/'data/processed']:
    p.mkdir(parents=True, exist_ok=True)

def md(df):
    def fmt(x):
        if pd.isna(x): return 'NA'
        if isinstance(x,(float,np.floating)): return f'{x:.5g}'
        return str(x)
    return '| '+' | '.join(map(str,df.columns))+' |\n|'+'|'.join(['---']*len(df.columns))+'|\n'+'\n'.join('| '+' | '.join(fmt(x) for x in row)+' |' for row in df.itertuples(index=False,name=None))

def wilson(k,n):
    if not n: return [None,None]
    z=1.96; p=k/n; a=1+z*z/n; c=(p+z*z/(2*n))/a
    h=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/a
    return [c-h,c+h]

def metrics(y,p):
    y=np.asarray(y,dtype=bool);p=np.asarray(p,dtype=bool)
    tp=int((y&p).sum());fp=int((~y&p).sum());fn=int((y&~p).sum());tn=int((~y&~p).sum())
    return dict(n=len(y),tp=tp,fp=fp,fn=fn,tn=tn,precision=tp/(tp+fp) if tp+fp else None,
                recall=tp/(tp+fn) if tp+fn else None,f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0,
                fpr=fp/(fp+tn) if fp+tn else None,recall_wilson=wilson(tp,tp+fn),fpr_wilson=wilson(fp,fp+tn))

def run():
    path=ROOT/'data/raw/ps02_system_telemetry.csv'
    d=pd.read_csv(path); raw=d.copy(); t=pd.to_datetime(d.timestamp,errors='coerce')
    d['parsed_timestamp']=t;d['ratio']=d.value/d.threshold
    nums=raw.select_dtypes('number').columns.tolist()
    desc=raw[nums].describe(percentiles=[.01,.05,.25,.5,.75,.95,.99]).T.rename_axis('column').reset_index()
    desc['skewness']=[stats.skew(raw[c],bias=False) for c in nums]
    desc['missing']=[raw[c].isna().sum() for c in nums]
    desc['nonfinite']=[(~np.isfinite(raw[c])).sum() for c in nums]
    desc['iqr_outliers']=[((raw[c]<raw[c].quantile(.25)-1.5*(raw[c].quantile(.75)-raw[c].quantile(.25)))|(raw[c]>raw[c].quantile(.75)+1.5*(raw[c].quantile(.75)-raw[c].quantile(.25)))).sum() for c in nums]
    desc.to_csv(OUT/'column_statistics.csv',index=False)
    cats=pd.concat([raw[c].value_counts(dropna=False).rename_axis('category').reset_index(name='count').assign(column=c) for c in ['service_name','metric_type','alert_level','is_incident']])
    cats['proportion']=cats['count']/len(d);cats[['column','category','count','proportion']].to_csv(OUT/'categorical_distributions.csv',index=False)
    sm=d.groupby(['service_name','metric_type']).agg(n=('value','size'),incidents=('is_incident','sum'),value_mean=('value','mean'),value_min=('value','min'),value_max=('value','max'),threshold_mean=('threshold','mean'),ratio_mean=('ratio','mean')).reset_index()
    sm['incident_rate']=sm.incidents/sm.n;sm.to_csv(OUT/'service_metric_analysis.csv',index=False)
    ing=[]
    for c in ['service_name','metric_type','alert_level']:
        g=d.groupby(c).is_incident.agg(['size','sum']).reset_index()
        for _,r in g.iterrows(): ing.append(dict(feature=c,category=r[c],n=r['size'],incidents=r['sum'],incident_rate=r['sum']/r['size'],wilson_low=wilson(r['sum'],r['size'])[0],wilson_high=wilson(r['sum'],r['size'])[1]))
    pd.DataFrame(ing).to_csv(OUT/'incident_analysis.csv',index=False)
    pairs=[]
    for i,a in enumerate(nums+['ratio']):
        for b in (nums+['ratio'])[i+1:]:
            p=stats.pearsonr(d[a],d[b]);s=stats.spearmanr(d[a],d[b])
            pairs.append(dict(variable_a=a,variable_b=b,pearson=p.statistic,pearson_p=p.pvalue,spearman=s.statistic,spearman_p=s.pvalue))
    pd.DataFrame(pairs).to_csv(OUT/'correlation_analysis.csv',index=False)
    assoc=[]
    for c in ['service_name','metric_type','alert_level']:
        table=pd.crosstab(d[c],d.is_incident);chi,p,df,ex=stats.chi2_contingency(table,correction=False)
        assoc.append(dict(feature=c,chi_square=chi,p_value=p,cramers_v=np.sqrt(chi/(len(d)*min(table.shape[0]-1,table.shape[1]-1))),minimum_expected=ex.min()))
    pd.DataFrame(assoc).to_csv(OUT/'categorical_associations.csv',index=False)
    effects=[]
    for c in nums[:-1]+['ratio']:
        a=d.loc[d.is_incident==1,c];b=d.loc[d.is_incident==0,c]
        u,p=stats.mannwhitneyu(a,b,alternative='two-sided')
        pool=np.sqrt(((len(a)-1)*a.var()+(len(b)-1)*b.var())/(len(a)+len(b)-2))
        effects.append(dict(feature=c,positive_mean=a.mean(),negative_mean=b.mean(),positive_median=a.median(),negative_median=b.median(),cohens_d=(a.mean()-b.mean())/pool,rank_biserial=2*u/(len(a)*len(b))-1,mw_p=p))
    pd.DataFrame(effects).to_csv(OUT/'incident_effect_sizes.csv',index=False)
    gap=t.sort_values().diff().dt.total_seconds().dropna()
    series=[]
    for (service,metric),g in d.groupby(['service_name','metric_type']):
        gg=g.parsed_timestamp.sort_values().diff().dt.total_seconds().dropna()
        series.append(dict(service_name=service,metric_type=metric,n=len(g),gap_min_seconds=gg.min(),gap_median_seconds=gg.median(),gap_max_seconds=gg.max()))
    pd.DataFrame(series).to_csv(OUT/'temporal_series_statistics.csv',index=False)
    daily=d.set_index('parsed_timestamp').resample('D').agg(records=('is_incident','size'),incidents=('is_incident','sum'))
    daily.to_csv(OUT/'daily_counts.csv')
    near=raw.drop(columns=['timestamp']).copy()
    for c in ['value','threshold']:near[c]=near[c].round(0)
    for c in ['user_count_active','response_time_ms']:near[c]=(near[c]/100).round()
    near['error_count_last_hour']=(near.error_count_last_hour/5).round()
    checks=[('missing_cells',int(raw.isna().sum().sum()),'expected 0'),('unparseable_timestamps',int(t.isna().sum()),'expected 0'),('duplicate_rows',int(raw.duplicated().sum()),'expected 0'),('duplicate_timestamps',int(t.duplicated().sum()),'global only'),('duplicates_without_timestamp',int(raw.drop(columns='timestamp').duplicated().sum()),'all other columns exact'),('coarsened_near_duplicates',int(near.duplicated().sum()),'exclude timestamp; value/threshold whole; users/response bins 100; errors bins 5'),('nonpositive_threshold',int((d.threshold<=0).sum()),'invalid for ratio'),('negative_numeric_cells',int((raw[nums]<0).sum().sum()),'semantic nonnegativity'),('invalid_incident_flags',int((~d.is_incident.isin([0,1])).sum()),'binary'),('values_over_threshold',int((d.value>d.threshold).sum()),'diagnostic, not error'),('critical_label_ratio_disagreements',int(((d.ratio>=.95)!=(d.alert_level=='CRITICAL')).sum()),'hypothesis discovered in full sample'),('normal_label_ratio_disagreements',int(((d.ratio<.75)!=(d.alert_level=='NORMAL')).sum()),'hypothesis discovered in full sample'),('timezone_designators',int(raw.timestamp.str.contains(r'Z$|[+-]\d\d:\d\d$').sum()),'0 implies unknown timezone')]
    pd.DataFrame(checks,columns=['check','count','meaning']).to_csv(OUT/'data_quality_checks.csv',index=False)
    d.sort_values('parsed_timestamp').drop(columns='parsed_timestamp').to_csv(ROOT/'data/processed/organizer_sorted_with_ratio.csv',index=False)
    result=[]
    ordered=d.sort_values('parsed_timestamp');splits={'all_exploratory':ordered,'train_first_60pct':ordered.iloc[:300],'validation_next_20pct':ordered.iloc[300:400],'test_last_20pct':ordered.iloc[400:]}
    for split,g in splits.items():
        for name,pred in [('exceed_supplied_threshold',g.value>g.threshold),('ratio_ge_0.75',g.ratio>=.75),('ratio_ge_0.90',g.ratio>=.90),('ratio_ge_0.95',g.ratio>=.95),('ratio_ge_0.98',g.ratio>=.98),('critical_label_diagnostic',g.alert_level=='CRITICAL')]:
            result.append(dict(split=split,detector=name,**metrics(g.is_incident,pred)))
    pd.DataFrame(result).to_csv(ROOT/'reports/evaluation/organizer_baseline_results.csv',index=False)
    out=dict(rows=len(d),columns=len(raw.columns),services=sorted(d.service_name.unique()),metrics=sorted(d.metric_type.unique()),incident_count=int(d.is_incident.sum()),incident_prevalence=float(d.is_incident.mean()),timestamp_start=str(t.min()),timestamp_end=str(t.max()),timezone='unspecified; do not silently convert to UTC',source_order_chronological=bool(t.is_monotonic_increasing),global_gap_seconds=gap.describe().to_dict(),series_count=len(series),series_records_min=int(sm.n.min()),series_records_max=int(sm.n.max()),series_median_gap_hours=float(pd.DataFrame(series).gap_median_seconds.median()/3600),ratio_by_alert=d.groupby('alert_level').ratio.agg(['min','max','mean']).to_dict('index'),pearson_value_threshold=float(d.value.corr(d.threshold)),baseline_all=[r for r in result if r['split']=='all_exploratory'],source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),software={'python':platform.python_version(),'pandas':pd.__version__,'numpy':np.__version__,'matplotlib':matplotlib.__version__})
    (OUT/'eda_summary.json').write_text(json.dumps(out,indent=2,allow_nan=False))
    plt.rcParams.update({'figure.dpi':140,'axes.spines.top':False,'axes.spines.right':False,'font.size':10})
    fig,axes=plt.subplots(2,3,figsize=(13,7));
    for ax,c in zip(axes.flat,nums):ax.hist(d[c],bins=25,color='#297b91');ax.set(title=c,xlabel='Observed value (source units)',ylabel='Records')
    fig.suptitle('Organizer data numerical distributions');fig.tight_layout();fig.savefig(FIG/'numeric_distributions.png');plt.close(fig)
    fig,axes=plt.subplots(2,3,figsize=(13,7))
    for ax,c in zip(axes.flat,nums):ax.boxplot([d.loc[d.is_incident==i,c] for i in [0,1]],tick_labels=['No incident','Incident']);ax.set(title=c,ylabel='Observed value (source units)')
    fig.suptitle('Numerical variables by contemporaneous incident label');fig.tight_layout();fig.savefig(FIG/'incident_boxplots.png');plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(15,5))
    for ax,c in zip(axes,['service_name','metric_type','alert_level']):
        d[c].value_counts().sort_values().plot.barh(ax=ax,color='#297b91');ax.set(title=c,xlabel='Records',ylabel='Category')
    fig.suptitle('Categorical coverage');fig.tight_layout();fig.savefig(FIG/'categorical_coverage.png');plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(11,4));d.is_incident.value_counts().sort_index().plot.bar(ax=axes[0],color=['#297b91','#d5713c']);axes[0].set(title='472 negative and 28 positive records',xlabel='Incident label',ylabel='Records');daily[['records','incidents']].plot(ax=axes[1],marker='o');axes[1].set(title='Irregular observations across August 2026',xlabel='Source date (timezone unknown)',ylabel='Records per date');fig.tight_layout();fig.savefig(FIG/'class_balance_and_timeline.png');plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,4))
    for level,g in d.groupby('alert_level'):axes[0].scatter(g.value,g.threshold,label=level,s=13,alpha=.65)
    axes[0].plot([0,140],[0,140],color='black',ls='--',label='value = threshold');axes[0].set(title='All supplied thresholds exceed values',xlabel='value (unit unknown)',ylabel='threshold (unit unknown)');axes[0].legend(fontsize=8)
    for level,g in d.groupby('alert_level'):axes[1].hist(g.ratio,bins=np.linspace(.65,1,40),alpha=.65,label=level)
    axes[1].set(title='Ratio partitions reproduce alert labels',xlabel='value / threshold (assumed comparable)',ylabel='Records');axes[1].legend(fontsize=8);fig.tight_layout();fig.savefig(FIG/'threshold_label_structure.png');plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,6));corr=d[nums+['ratio']].corr();im=ax.imshow(corr,vmin=-1,vmax=1,cmap='RdBu_r');ax.set_xticks(range(len(corr)),corr.columns,rotation=60,ha='right');ax.set_yticks(range(len(corr)),corr.columns)
    for i in range(len(corr)):
        for j in range(len(corr)):ax.text(j,i,f'{corr.iloc[i,j]:.2f}',ha='center',va='center',fontsize=8,color='white' if abs(corr.iloc[i,j])>.6 else 'black')
    ax.set_title('Pearson associations are descriptive, not causal');fig.colorbar(im,ax=ax);fig.tight_layout();fig.savefig(FIG/'correlations.png');plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(13,4));d.boxplot(column='value',by='metric_type',ax=axes[0],rot=50);axes[0].set(title='Metric values share similar numerical ranges',xlabel='Metric (units unspecified)',ylabel='value');tab=pd.crosstab(d.service_name,d.metric_type);im=axes[1].imshow(tab,cmap='Blues');axes[1].set_xticks(range(len(tab.columns)),tab.columns,rotation=50,ha='right');axes[1].set_yticks(range(len(tab.index)),tab.index);axes[1].set_title('Service and metric coverage')
    for i in range(tab.shape[0]):
        for j in range(tab.shape[1]):axes[1].text(j,i,str(tab.iloc[i,j]),ha='center',va='center',fontsize=8)
    fig.suptitle('');fig.tight_layout();fig.savefig(FIG/'metric_service_comparisons.png');plt.close(fig)
    print(json.dumps({k:out[k] for k in ['rows','incident_count','series_median_gap_hours','baseline_all']},indent=2))
    return out

if __name__=='__main__':run()
