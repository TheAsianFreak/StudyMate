"""User profile: how the character addresses the user.

The address goes into every prompt that makes the character speak, so it is screened:
short, plain text only (no quotes, braces, markup or line breaks that could steer the
prompt), and nothing the safety filter would refuse to say (sexual, slurs, attacks).
"""

from __future__ import annotations

import re
import unicodedata

from studymate.errors import UserFacingError
from studymate.solve.safety import is_unsafe, is_unsafe_request

ADDRESS_MAX = 20
# Letters (any script), digits, spaces and a few name punctuation marks.
_ALLOWED = re.compile(r"^[\w .'·・ー~\-]+$")
# Romantic-partner addresses: the character is a teacher and never does romantic role-play
# (safety prompt, EULA).
_ROMANTIC = re.compile(
    r"여보|자기야|허니|달링|애인|남친|여친|남자\s*친구|여자\s*친구|서방님|신랑|신부|마누라"
    r"|ダーリン|ハニー|旦那様|恋人|彼氏|カレシ|カノジョ|お嫁さん|お婿さん"
    r"|\b(?:darling|honey|babe|baby|sweetheart|sweetie|boyfriend|girlfriend|husband|wife|hubby|daddy|mommy|lover)\b",
    re.IGNORECASE,
)


def clean_address(raw: str | None) -> str:
    """Normalized address, "" for the default; raises UserFacingError when not acceptable."""
    text = unicodedata.normalize("NFKC", raw or "")
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    if len(text) > ADDRESS_MAX:
        raise UserFacingError("invalid_address", f"호칭은 {ADDRESS_MAX}자 이내로 적어 주세요.")
    if not _ALLOWED.match(text) or "_" in text:
        raise UserFacingError("invalid_address", "호칭에는 글자, 숫자, 띄어쓰기만 쓸 수 있어요.")
    if is_unsafe(text) or is_unsafe_request(text) or _ROMANTIC.search(text):
        raise UserFacingError("unsafe_address", "그 호칭은 쓸 수 없어요. 다른 호칭을 골라 주세요.")
    return text
