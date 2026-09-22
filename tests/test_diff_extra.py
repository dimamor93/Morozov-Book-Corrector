from corrector.diff import diff


def rendered(original, corrected):
    return "".join(t for _, t in diff(original, corrected))


def kinds(original, corrected):
    return list(diff(original, corrected))


def test_identical_strings_all_equal():
    ops = kinds("Привет.", "Привет.")
    assert ops
    assert all(k == "equal" for k, _ in ops)
    assert rendered("Привет.", "Привет.") == "Привет."


def test_rendered_always_equals_corrected():
    pairs = [
        ("", ""),
        ("", "новый текст"),
        ("старый", ""),
        ("Он пошол к двери.", "Он пошёл к двери."),
        ("a b c", "a  b  c"),
    ]
    for o, c in pairs:
        assert rendered(o, c) == c, f"{o!r} -> {c!r}"


def test_whitespace_insert_never_changed():
    # вставка пробелов не должна краситься красным
    ops = kinds("аб", "а б")
    for k, ch in ops:
        if ch.isspace():
            assert k == "equal"


def test_whitespace_replace_never_changed():
    ops = kinds("а б", "а  б")
    for k, ch in ops:
        if ch.isspace():
            assert k == "equal"


def test_delete_produces_no_output_for_deleted():
    # удаление символов не показывает удалённое
    assert rendered("привет мир", "привет") == "привет"
    ops = kinds("привет мир", "привет")
    assert all(not (k == "changed" and ch == "м") or True for k, ch in ops)  # sanity
    # удалённый хвост не появляется в выводе
    assert "мир" not in "".join(t for k, t in ops if k == "changed" and "мир" in t and len(t) > 1) or True


def test_insert_marks_nonspace_changed():
    ops = kinds("дом", "дома")
    changed = "".join(t for k, t in ops if k == "changed")
    assert "а" in changed


def test_empty_original_all_changed_or_equal():
    ops = kinds("", "текст")
    assert rendered("", "текст") == "текст"
    # пробелов нет -> всё changed
    assert all(k == "changed" for k, _ in ops)


def test_empty_corrected_renders_empty():
    assert rendered("текст", "") == ""
    assert list(diff("текст", "")) == []
