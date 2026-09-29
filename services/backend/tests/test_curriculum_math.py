"""Math curriculum tables: every unit id has Japanese and English text; CSAT units are complete."""

from __future__ import annotations

from typing import Any

import pytest

from studymate.i18n import use_lang
from studymate.solve import curriculum, curriculum_en, curriculum_ja
from studymate.solve.curriculum_math_csat import CSAT_MATH_UNITS

CSAT_GRADES = {"수학Ⅰ", "수학Ⅱ", "확률과 통계", "미적분", "기하"}


def test_math_units_have_all_languages() -> None:
    ids = [u.id for u in curriculum.UNITS]
    assert len(ids) == len(set(ids))
    for uid in ids:
        assert uid in curriculum_ja.TEXT, uid
        assert uid in curriculum_en.TEXT, uid


def test_csat_units_cover_every_subject() -> None:
    assert {u.grade for u in CSAT_MATH_UNITS} == CSAT_GRADES
    assert 15 <= len(CSAT_MATH_UNITS) <= 25
    for u in CSAT_MATH_UNITS:
        assert u.is_math and u.examples and u.concept and u.notation and u.pitfalls, u.id
        assert len(u.method) >= 3, u.id
        assert "①" in u.notation  # CSAT answer conventions
        assert curriculum.is_advanced(u), u.id
    assert all(u in curriculum.UNITS for u in CSAT_MATH_UNITS)


@pytest.mark.parametrize("lang", ["ko", "ja", "en"])
def test_teaching_guide_and_classifier(lang: str) -> None:
    with use_lang(lang):  # type: ignore[arg-type]
        for u in CSAT_MATH_UNITS:
            local = curriculum.unit(u.id)
            assert local.id == u.id and local.grade and local.name
            guide = curriculum.teaching_guide(local)
            assert local.name in guide and local.concept in guide
        prompt = curriculum.classifier_prompt()
    assert all(u.id in prompt for u in CSAT_MATH_UNITS)
    schema: Any = curriculum.classifier_schema()
    assert set(schema["properties"]["unit_id"]["enum"]) >= {u.id for u in CSAT_MATH_UNITS}
