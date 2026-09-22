from __future__ import annotations
from difflib import SequenceMatcher


def validate_response(chunk, response):
    expected = {s.id: s.text for s in chunk}
    valid = []
    suspicious = []
    seen = set()

    for item in response.corrections:
        if item.id in seen:
            suspicious.append({"id": item.id, "reason": "duplicate_sentence_id"})
            continue
        seen.add(item.id)

        if item.id not in expected:
            suspicious.append({"id": item.id, "reason": "unknown_sentence_id"})
            continue

        original = expected[item.id].strip()
        corrected = item.corrected.strip()

        if not corrected or corrected == original:
            continue

        similarity = SequenceMatcher(None, original, corrected).ratio()
        if similarity < 0.55:
            suspicious.append({
                "id": item.id,
                "reason": "large_edit",
                "similarity": round(similarity, 3),
                "original": original,
                "corrected": corrected
            })
        else:
            valid.append({
                "id": item.id,
                "original": original,
                "corrected": corrected
            })

    return valid, suspicious
