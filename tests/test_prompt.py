from corrector.prompt import SYSTEM_PROMPT, user_prompt
from corrector.models import Sentence


def test_system_prompt_contains_json_contract():
    assert "corrections" in SYSTEM_PROMPT
    assert "JSON" in SYSTEM_PROMPT
    assert "Ё" in SYSTEM_PROMPT or "ё" in SYSTEM_PROMPT


def test_system_prompt_forbids_rewriting():
    low = SYSTEM_PROMPT.lower()
    assert "не переписывай" in low or "не улучшай" in low


def test_user_prompt_lists_ids_and_texts():
    ss = [
        Sentence(id=1, text="Первое.", paragraph_id=0, paragraph_order=0),
        Sentence(id=42, text="Второе!", paragraph_id=0, paragraph_order=1),
    ]
    p = user_prompt(ss)
    assert "[1] Первое." in p
    assert "[42] Второе!" in p


def test_user_prompt_empty():
    p = user_prompt([])
    assert isinstance(p, str)
    assert "Проверь" in p
