"""One input policy shared by API and UI; saved legacy records remain readable."""
LIMITS = {'q1':200,'q2':1000,'q3':1500,'q3_1':1500,'q3_2':600,'q4_1':1000,'founder_strength':600,
          'evidence_text':1500,'evidence_total':6000,'evidence_count':8,
          'target_field':300,'question':500,'card_json':14000,'annotation_json':30000}

def check_input(idea):
    for name,limit in LIMITS.items():
        if (name.startswith('q') and name!='question' or name=='founder_strength') and len(getattr(idea,name,''))>limit:
            raise ValueError(f'{name.upper()}는 {limit}자까지 입력할 수 있습니다 (현재 {len(getattr(idea,name))}자).')
    # Legacy heading fields are accepted by the API under the same new-input limits.
    for name in ('q4',):
        if len(getattr(idea,name))>1500: raise ValueError(f'{name.upper()}는 1500자까지 입력할 수 있습니다.')
    if any(len(e.text)>LIMITS['evidence_text'] for e in idea.evidence):
        raise ValueError('근거 자료는 항목별 1500자까지 입력하세요. 원문에서 관련 부분을 나누어 제출하세요.')
    if sum(len(e.text) for e in idea.evidence)>LIMITS['evidence_total']:
        raise ValueError('근거 자료의 text 합계는 6000자까지 입력할 수 있습니다.')

def check_target(target):
    if not target.segment_name.strip() or target.segment_name.strip()=='UNKNOWN':
        raise ValueError('어떤 이용자인지 입력하세요. 검증 과제 대신 사람·기관의 유형을 적어 주세요.')
    if not target.why_relevant.strip(): raise ValueError('이 이용자를 추천하는 이유를 입력하세요.')
    for key in ('segment_name','why_relevant','problem_exposure','expected_current_alternative','buying_role'):
        if len(getattr(target,key))>LIMITS['target_field']: raise ValueError(f'{key}는 300자까지 입력하세요.')
    if len(target.critical_unknowns)>8 or any(len(s)>200 for s in target.critical_unknowns):
        raise ValueError('critical_unknowns는 최대 8개, 각 200자까지 입력하세요.')
