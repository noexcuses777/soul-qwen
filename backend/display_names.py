"""Fictional aliases only: never a source for persona traits or model judgments."""
import random
import secrets

# The combinations are cosmetic Korean names; neither name component encodes a
# target's age, gender, occupation, buying role, or the model's stance.
SURNAMES = ('김', '이', '박', '최', '정', '강', '윤', '장', '임', '한', '오', '서', '신', '권', '황', '안')
GIVEN_NAMES = ('하늘', '다온', '시온', '유진', '지우', '서준', '서아', '도윤', '지안', '수현',
               '유나', '재윤', '서연', '도현', '하윤', '서우', '지유', '현우', '민서', '은우',
               '예린', '지호', '수빈', '주원', '시우', '채원', '준서', '연우', '가온', '다인',
               '예원', '태윤', '지수', '민재', '나윤', '승우', '서진', '하진', '유빈', '재인',
               '은서', '시현', '도원', '윤재', '해솔', '한결', '보민', '지율')
ALIASES = tuple(surname + given for surname in SURNAMES for given in GIVEN_NAMES)


def random_name(used=(), rng=None):
    used = set(used)
    available = [name for name in ALIASES if name not in used]
    if not available:
        raise ValueError('No unused fictional aliases remain')
    return (rng.choice if rng is not None else secrets.choice)(available)


def ensure_names(cards, rng=None):
    """Preserve saved/user names; fill blanks uniquely instead of using p1/p2 order."""
    used = {card.presentation.display_name for card in cards if card.presentation.display_name}
    for card in cards:
        if not card.presentation.display_name:
            card.presentation.display_name = random_name(used, rng)
            used.add(card.presentation.display_name)


def ensure_session_names(session, fresh_recommendation=False):
    """Persist new recommendation aliases, and keep legacy reads stable without writes.

    A legacy payload lacking metadata uses its random session UUID as the seed.
    New recommendations use system entropy and avoid the preceding name set.
    Mapping lives on Session, outside Target/Immutable Core and LLM target inputs.
    """
    rng = None if fresh_recommendation else random.Random(session.id)
    previous = dict(session.target_display_names)
    aliases = {} if fresh_recommendation else previous.copy()
    blocked = set(previous.values()) if fresh_recommendation else set()
    # Unnamed legacy cards first reuse their saved target aliases when available.
    associations = {}
    for index, card in enumerate(session.cards):
        target_id = (session.selected_target_ids[index] if index < len(session.selected_target_ids)
                     else next((target.id for target in session.targets
                                if target.segment_name == card.immutable_core.identity_context.segment), None))
        if target_id:
            associations[card.id] = target_id
            if not card.presentation.display_name and aliases.get(target_id):
                card.presentation.display_name = aliases[target_id]
    ensure_names(session.cards, rng)
    # A saved card/user rename wins over stale recommendation metadata.
    for card in session.cards:
        if card.id in associations:
            aliases[associations[card.id]] = card.presentation.display_name
    reserved = {card.presentation.display_name for card in session.cards}
    used = reserved | blocked | set(aliases.values())
    ordered_ids = list(dict.fromkeys(list(associations.values()) + [target.id for target in session.targets]))
    result = {}
    for target_id in ordered_ids:
        name = aliases.get(target_id)
        is_card = target_id in associations.values()
        if not name or name in result.values() or (name in reserved and not is_card):
            name = random_name(used, rng)
        result[target_id] = name
        used.add(name)
    session.target_display_names = result
    return session
