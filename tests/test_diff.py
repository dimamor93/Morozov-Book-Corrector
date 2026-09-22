
from corrector.diff import diff


def rendered(original, corrected):
    return "".join(text for _, text in diff(original, corrected))


def changed_text(original, corrected):
    return "".join(
        text for kind, text in diff(original, corrected)
        if kind == "changed"
    )


def test_punctuation_insertion():
    original = "Она идеально держала осанку будто пыталась показаться выше."
    corrected = "Она идеально держала осанку, будто пыталась показаться выше."
    assert rendered(original, corrected) == corrected
    assert "," in changed_text(original, corrected)


def test_punctuation_and_word_change():
    original = "Мы встретили новый год в центре."
    corrected = "Мы встретили Новый год в центре."
    assert rendered(original, corrected) == corrected
    assert "Н" in changed_text(original, corrected)


def test_dialogue_punctuation():
    original = "— Если только о вечном сне, — зевая ответил я."
    corrected = "— Если только о вечном сне, — зевая, ответил я."
    assert rendered(original, corrected) == corrected


def test_complex_punctuation():
    original = "Когда за нами щёлкнул замок, мы остались наедине."
    corrected = "Когда за нами щёлкнул замок, мы остались наедине."
    assert rendered(original, corrected) == corrected
    assert changed_text(original, corrected) == ""


def test_yo():
    original = "Он пошол к двери."
    corrected = "Он пошёл к двери."
    assert rendered(original, corrected) == corrected
    assert "ё" in changed_text(original, corrected)
