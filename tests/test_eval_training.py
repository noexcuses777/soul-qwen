import json,pytest
from pathlib import Path
from backend.llm import LLMClient
from backend.schemas import IdeaInput
from eval.metrics import Annotations,metrics
from eval.schema import JudgeScores,AXES
from eval.run_eval import aggregate,compare_pair,run
from eval.experiment import prepare,condition,bootstrap_differences
from training.prepare import prepare as prepare_training

def test_calibration():
    a=Annotations.model_validate_json(Path('examples/calibration_synthetic.json').read_text(encoding='utf-8'));m=metrics(a)
    assert m['theme_recall']==pytest.approx(2/3) and m['false_insight_rate']==pytest.approx(1/3)
    assert m['alternative_recall']==.5 and m['barrier_recall']==1 and m['confidence_brier']==pytest.approx(.365)
    assert metrics(Annotations())['theme_recall'] is None
    with pytest.raises(ValueError):Annotations(predicted_themes=['a'],valid_ids=['b'])

def test_judge_aggregation_swap():
    rows=[JudgeScores(scores={a:{'score':score,'rationale':'test'} for a in AXES}) for score in [3,4,4]]
    assert aggregate(rows)[AXES[0]]['score']==4 and aggregate(rows)[AXES[0]]['majority']
    class Biased(LLMClient):
        def call(self,task,payload,schema,**kw): return schema(winner='A',reason='position bias fixture')
    r=compare_pair({},'one','two',Biased('mock'),3)
    assert r['winner']=='tie' and r['votes']==['A']*3+['B']*3

def test_eval_smoke(tmp_path):
    result=run('eval/data/synthetic_demo.jsonl',tmp_path,judges=3,swap=True)
    assert result['synthetic_cases']==3 and all(x is None for x in result['means'].values())
    assert (tmp_path/'scores.csv').exists() and len((tmp_path/'candidates.jsonl').read_text(encoding='utf-8').splitlines())==3

def test_experiment_budget_and_independence():
    idea=IdeaInput(q1='idea',q5='IT');llm=LLMClient('mock');b,t,c=prepare(idea,llm)
    for name in 'ABCD':
        r=condition(name,idea,b,t,c,llm,6000)
        assert r['completion_used_or_mock_reserved']<=6000 and r['annotation_required']
        assert len(r['responses'])==(8 if name in 'AB' else 24)
        if name=='C':assert all(x['reply_to'] is None for x in r['responses'])
    assert bootstrap_differences([], 'theme_recall')['ci95'] is None

def test_training_export_and_leak(tmp_path):
    for kind,file in [('sft','sft_demo'),('preference','preference_demo')]:
        assert prepare_training(f'training/data/{file}.jsonl',str(tmp_path/f'{kind}.jsonl'),kind,'eval/data/synthetic_demo.jsonl')==1
    source=json.loads(Path('training/data/sft_demo.jsonl').read_text(encoding='utf-8'))
    source['source_id']='demo-eval-1';bad=tmp_path/'bad.jsonl';bad.write_text(json.dumps(source),encoding='utf-8')
    with pytest.raises(ValueError,match='leakage'):prepare_training(bad,tmp_path/'out.jsonl','sft','eval/data/synthetic_demo.jsonl')

def test_experiment_analysis(tmp_path):
    from eval.analyze_experiment import analyze
    runs=tmp_path/'runs.jsonl'; annotations=tmp_path/'annotations.jsonl'
    rows=[{'case_id':'one','condition':n,'seed':s,'mode':'mock','latency_s':.1,'generation_usage':[]} for n in 'ABCD' for s in [42,43]]
    runs.write_text('\n'.join(json.dumps(r) for r in rows),encoding='utf-8')
    labels=[{'case_id':r['case_id'],'condition':r['condition'],'seed':r['seed'],'annotations':{'dataset_kind':'synthetic','predicted_themes':['a'],'real_themes':['a','b']}} for r in rows]
    annotations.write_text('\n'.join(json.dumps(r) for r in labels),encoding='utf-8')
    result=analyze(runs,annotations,tmp_path/'analysis')
    assert result['annotated_runs']==8 and result['D_minus_baseline']['B']['theme_recall']['pairs']==1
    assert (tmp_path/'analysis/metrics.csv').exists()
