"""Deterministic synthetic fixtures. These are not evidence of Qwen capability."""
from .schemas import SECTIONS

def fixture(task,p):
    if task=='followup_plan':
        return {'candidates':[],'missing_information':['실제 고객의 사용 상황과 판단 조건'],
                'evidence_question':'최근 이 문제를 겪은 상황과 지금 해결하는 방법을 실제 고객에게 확인해 주세요.',
                'why':'합성 테스트 fixture에서는 새 대화 쟁점의 의미 품질을 판단하지 않습니다.'}
    if task=='followup_review':
        return {'reviews':[{'index':c['index'],'novel':False,'answerable':False,
            'why':'합성 fixture는 질문의 실제 의미 품질을 평가하지 않습니다.'} for c in p['candidates']]}
    if task=='target_review':
        return {'items':[{'index':t['index'],'is_participant':True,'fits_idea':True,
                         'reason':'합성 검사 fixture: 모델 품질 증거가 아님'} for t in p['targets']]}
    if task=='targets':
        names=['문제를 자주 마주치는 직접 사용자','기존 대안을 유지하는 사용자','도입을 결정하는 운영 담당자','사용을 지원하는 협업 담당자','구매 예산을 승인하는 담당자','문제가 드문 비사용 후보']
        exposures=['반복 업무에서 문제에 노출될 가능성','현재 방식과 비교하며 문제에 노출될 가능성','팀 도입 결정 과정에서 문제에 노출될 가능성','협업 전달 과정에서 문제에 노출될 가능성','비용 승인 과정에서 문제에 노출될 가능성','문제 빈도가 낮은 환경']
        roles=['사용자','사용자','결정자','영향자','지불자','비사용자']
        return {'targets':[{'segment_name':n,'why_relevant':p['brief']['one_line']+'와 관련된 검토 후보 (synthetic)',
                           'problem_exposure':exposures[i],'buying_role':roles[i],
                           'critical_unknowns':['실제 문제 빈도','현재 대안','예산 및 사용 장벽'],'relevance':.9-i*.1} for i,n in enumerate(names)]}
    if task=='build':
        t=p['target']
        return {'id':p['persona_id'],'immutable_core':{'identity_context':{'segment':t['segment_name'],'role':t.get('buying_role','UNKNOWN'),'use_context':t['problem_exposure']},
                 'problem_context':{'current_alternative':t.get('expected_current_alternative','UNKNOWN')},'decision_model':{'buying_role':t.get('buying_role','UNKNOWN')},
                 'reasoning_rules':[{'id':'r1','trigger':'새로운 방법을 검토한다면','value':'조건에 맞는 문제 해결 가능성','tradeoff':'준비 노력과 확인 가능한 효과',
                    'conditional_choice':'확인 가능한 효과가 준비 노력보다 크다면 검토할 수 있음',
                    'basis_fields':['identity_context.segment'],'unknowns':t.get('critical_unknowns',[])[:3]}]}}
    if task=='questions':
        return {'suggestions':[{'question':q,'topic':name,'why':'이 역할의 조건과 미확인 항목 확인','persona_id':None} for name,q in p['topics']]}
    if task=='validate': return {'issues':[]}
    if task=='chat':
        core=p['card']['immutable_core']; rule=next(iter(core.get('reasoning_rules',[])),{})
        parent=p.get('required_parent'); role=core['decision_model']['buying_role']
        text=f"[synthetic demo] {role} 관점의 가설입니다. {rule.get('conditional_choice','필요한 조건이 아직 없습니다.')} "
        if parent: text+=f"동료의 조건 [{parent['id']}]이 제 상황에도 적용되는지, 준비 노력과 확인 가능한 효과를 비교해야 합니다. "
        text+='실제 선택은 대안의 비용과 문제 빈도를 확인한 뒤 판단할 수 있습니다.'
        return {'content':text,'stance':'conditional','reason':'카드의 조건과 확인할 효과를 비교하는 synthetic 응답',
                'reasoning_rule_ids':[rule['id']] if rule else [],'dialogue_act':'answer',
                'unresolved_issues':['실제 대안 비용'],'reply_to':parent['id'] if parent else None,
                'addressed_to':None,'followup_question':'','followup_kind':'none'}
    if task=='interact':
        base=fixture('agent',p); last=p.get('group',{}).get('recent',[])
        peer=next((x for x in reversed(last) if x['persona_id']!=p['card']['id']),None)
        closing=p.get('round')=='Closing check'
        base.update(dialogue_act='close' if closing else 'question',addressed_to=peer['persona_id'] if peer and not closing else None)
        # Synthetic Korean interaction signals exercise the controller, not model quality.
        if peer and not closing: base['content']=f"{peer['persona_id']}님의 조건과 제 역할은 같다고 단정할 수 없습니다. 역할별 필요한 조건이 다른지 확인하고 싶습니다."
        base['followup_question']='역할별 필요한 조건이 다른가요?' if not closing else ''
        return base
    if task=='agent':
        c=p.get('card'); core=c['immutable_core'] if c else None
        if core:
            name=core['identity_context']['segment']; role=core['decision_model']['buying_role']
            text=f'{name} 관점의 가설로 보면, {role} 역할에서 조건을 확인해야 합니다. '
        else: text='일반적인 가설로 보면, 실제 사용자 조건을 확인해야 합니다. '
        rnd=p.get('round','')
        phrases={
          'Problem Reality':'문제 빈도와 현재 대안은 아직 모릅니다. 실제로 언제 불편한지 확인하고 싶습니다.',
          'Solution Reaction':'문제 해결에 도움이 된다면 검토할 수 있지만, 실제 효과와 장벽은 모릅니다.',
          'Cross-reaction':'다른 참여자의 조건이 제게도 적용되는지는 모릅니다. 역할 차이를 확인해야 합니다.',
          'Conflict Probe':'역할의 차이를 검토할 수 있지만 의견 차이가 있다고 단정할 근거는 없습니다.',
          'Adoption/Payment Reality':'예산과 전환비용, 지불 주체는 모릅니다. 실제 구매 의사를 확정할 수 없습니다.',
          'Failure Condition':'현재 대안보다 나아지지 않는다면 검토를 중단할 수 있습니다. 실제 비교가 필요합니다.',
        }
        return {'content':text+phrases.get(rnd,'현재 대안과 제약은 모릅니다. 실제 인터뷰에서 조건을 확인한 뒤 판단해야 합니다.'),
                'stance':'conditional','reason':'문제 빈도·대안·제약이 확인되지 않아 조건부 판단을 유지합니다.',
                'unresolved_issues':['실제 문제 빈도','현재 대안','도입 장벽'],
                'reply_to':p.get('group',{}).get('recent',[])[-1]['id'] if p.get('group',{}).get('recent') else None}
    if task=='report':
        turns=p['transcript']; ids=[t.split('|')[0] if isinstance(t,str) else t['id'] for t in turns]
        sections={s:[{'text':f'{s}: synthetic 시뮬레이션에서 확인할 가설이며 실제 고객 근거가 필요합니다.','utterance_ids':ids[-3:]}] for s in SECTIONS}
        sections['Real Interview Next Steps']=[{'text':'최근 문제를 겪은 순간, 현재 대안, 결정·지불 주체, 전환비용을 실제 고객에게 질문하세요.'}]
        return {'sections':sections}
    if task=='judge':
        return {'scores':{axis:{'score':None,'rationale':'Synthetic smoke judge: semantic performance is not assessed.'} for axis in p['axes']}}
    if task=='pair': return {'winner':'tie','reason':'Synthetic smoke judge; no real preference judgment.'}
    raise ValueError('unknown mock task '+task)
