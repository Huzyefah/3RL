"""PII masking. Tools, SSE, Chat cards, BigQuery rows and evidence must pass `assert_no_pii`."""

from __future__ import annotations

import json
import re
from typing import Any

MSISDN = re.compile(r"(?<!\d)03\d{9}(?!\d)")
CNIC = re.compile(r"(?<!\d)\d{5}-\d{7}-\d(?!\d)")
CARD_CANDIDATE = re.compile(r"(?<!\d)\d{13,19}(?!\d)")


class PIIError(AssertionError):
    pass


def luhn_ok(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def redact(text: str) -> str:
    text = MSISDN.sub(lambda m: f"03xx-xxxx{m.group()[-3:]}", text)
    text = CNIC.sub(lambda m: f"*****-*******-{m.group()[-1]}", text)
    return CARD_CANDIDATE.sub(lambda m: f"****{m.group()[-4:]}" if luhn_ok(m.group()) else m.group(), text)


def find_pii(text: str) -> list[str]:
    hits = MSISDN.findall(text) + CNIC.findall(text)
    hits += [m for m in CARD_CANDIDATE.findall(text) if luhn_ok(m)]
    return hits


def assert_no_pii(obj: Any) -> None:
    text = obj if isinstance(obj, str) else json.dumps(obj, default=str)
    hits = find_pii(text)
    if hits:
        raise PIIError(f"PII found ({len(hits)} matches)")
