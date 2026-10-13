"""Conservative lexical quantity provenance; no IO or generated-memory evidence.

Arabic numbers with explicit units are checked. This is not a semantic verifier:
matching a founder's number does not prove that a claim about it is correct.
"""
import re
from decimal import Decimal

_UNITS = '퍼센트|percent|개월|시간|달러|유로|KRW|USD|EUR|회|번|건|개|명|인|팀|분|초|일|주|달|년|배|점|대|원|%'
_NUMBER = r'(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?'
_QUANTITY = re.compile(r'(?<![A-Za-z0-9_.:/-])(?P<number>[-+]?' + _NUMBER +
    r')(?:[ \t]*[~–-][ \t]*(?P<range_end>' + _NUMBER + r'))?'
    r'[ \t]*(?P<magnitude>천만|백만|십만|백|천|만|억|조)?[ \t]*(?P<unit>' +
    _UNITS + r')(?![A-Za-z0-9_])')
_CURRENCY = re.compile(r'(?<![A-Za-z0-9_.:/-])(?P<unit>[$€₩])[ \t]*(?P<number>' + _NUMBER + r')(?![\d,.])')
_PERIOD = re.compile(r'(?<![가-힣A-Za-z0-9_])(하루|일일|매일|매주|매월|매년|주간|월간|연간|주|월|연)[ \t]*$')
_PERIOD_NAMES = {'하루':'일','일일':'일','매일':'일','매주':'주','주간':'주',
                 '매월':'월','월간':'월','매년':'연','연간':'연'}
_SCALE = {'':1,'백':100,'천':1000,'만':10000,'십만':100000,'백만':1000000,
          '천만':10000000,'억':100000000,'조':1000000000000}
_IGNORED_KEYS = {'id','source_id','evidence_ids','reasoning_rule_ids','basis_fields',
                 'session_state','presentation','quality_flags','generated_content'}


def quantity_texts(*values):
    """Flatten explicitly allowed input structures; never pass an agent buffer."""
    result = []
    def visit(value):
        if hasattr(value, 'model_dump'):
            value = value.model_dump(mode='json')
        if isinstance(value, str):
            result.append(value)
        elif isinstance(value, dict):
            for key, child in value.items():
                if key not in _IGNORED_KEYS:
                    visit(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                visit(child)
    for value in values:
        visit(value)
    return result


def _quantities(text):
    # Identifiers/versions cannot match the bounded unit pattern. URLs are not
    # quantity statements even if their opaque query strings contain digits.
    text = re.sub(r'https?://[^\s<>]+', lambda match: ' ' * len(match[0]), text)
    rows = []
    for match in _QUANTITY.finditer(text):
        value = Decimal(match['number'].replace(',', '')) * _SCALE[match['magnitude'] or '']
        upper = Decimal(match['range_end'].replace(',', '')) * _SCALE[match['magnitude'] or ''] if match['range_end'] else value
        unit = {'퍼센트':'%','percent':'%','KRW':'원','USD':'달러','EUR':'유로'}.get(match['unit'],match['unit'])
        period = _PERIOD.search(text[max(0,match.start()-12):match.start()])
        cadence = _PERIOD_NAMES.get(period[1], period[1]) if period else ''
        rows.append(((value, upper, unit, cadence), text[match.start():match.end()]))
    for match in _CURRENCY.finditer(text):
        value = Decimal(match['number'].replace(',', ''))
        unit = {'$':'달러','€':'유로','₩':'원'}[match['unit']]
        rows.append(((value,value,unit,''),text[match.start():match.end()]))
    return rows


def unsupported_quantities(text, allowed_texts):
    """Return unsupported original quantity fragments, without rewriting text."""
    allowed = {key for source in allowed_texts for key, _ in _quantities(source)}
    return list(dict.fromkeys(raw for key, raw in _quantities(text) if key not in allowed))
