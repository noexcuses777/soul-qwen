"""Structural diagnostics, deliberately separate from human usefulness/fidelity scores."""
import argparse,json
from pathlib import Path
from backend.schemas import Session

def structural_metrics(s):
    public={t.id:t for t in s.transcript if t.phase=='group'}
    replies=[t for t in public.values() if t.reply_to]
    invalid=[t.id for t in replies if t.reply_to not in public or public[t.reply_to].persona_id==t.persona_id
             or list(public).index(t.reply_to)>=list(public).index(t.id)]
    for t in replies:
        parent=public.get(t.reply_to)
        if parent and t.thread_id and parent.thread_id!=t.thread_id: invalid.append(t.id)
    return {'dataset_kind':'structural_execution','public_turns':len(public),'reply_count':len(replies),
        'invalid_reply_ids':sorted(set(invalid)),'thread_count':len(s.threads),
        'threads_returned_or_closed':sum(t.status!='active' for t in s.threads),
        'unresolved_conditions_retained':sum(len(t.remaining_issues) for t in s.threads),
        'turns_by_persona':{c.id:sum(t.persona_id==c.id for t in public.values()) for c in s.cards},
        'lexical_guard_flags':{t.id:t.quality_flags for t in s.transcript if t.quality_flags},
        'human_required':['addressee_appropriateness','repair_success','rule_faithfulness','unsupported_experience_rate',
            'need_specificity','useful_followup_count','conformity_rate','founder_control','founder_usefulness'],
        'notice':'IDs and control flow only; no semantic performance or market validity score.'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('session');p.add_argument('--out',required=True);a=p.parse_args()
    result=structural_metrics(Session.model_validate_json(Path(a.session).read_text(encoding='utf-8')))
    Path(a.out).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
