"""PII redaction applied before any text reaches an LLM, log sample or UI.

* MSISDN (``03xxxxxxxxx``, ``+923xxxxxxxxx``, ``0300-1234567``) -> ``03xx-xxxx123``
* PAN: 13-19 digits (spaces/dashes allowed) that pass the Luhn check -> ``****-****-****-1234``
* CNIC ``#####-#######-#`` -> ``*****-*******-#``

Digit strings that fail Luhn are not treated as PANs.

Boundary tradeoff: the bare ``03...`` and ``92 3...`` MSISDN forms and the PAN rule require
that the match is not glued to a preceding digit (the PAN rule also not to a preceding
``.``), so ids, epoch-ms values and float decimals are left alone. The guarantee is
therefore that no *standalone* ``03\\d{9}`` survives; one embedded in a longer digit run is
not masked. The ``+92`` and ``0092`` forms carry their own prefix and need no boundary.
"""

from __future__ import annotations

import re

_CNIC = re.compile(r"(?<!\d)\d{5}-\d{7}-(\d)(?!\d)")
_PAN = re.compile(r"(?<![\d.])\d(?:[ -]?\d){12,18}(?!\d)")
_MSISDN = re.compile(r"(?:\+92[ -]?|0092[ -]?|(?<!\d)92[ -]?|(?<!\d)0)3(\d{2})[ -]?(\d{4})(\d{3})")


def _luhn_ok(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _mask_pan(m: re.Match[str]) -> str:
    digits = re.sub(r"\D", "", m.group(0))
    if 13 <= len(digits) <= 19 and _luhn_ok(digits):
        return f"****-****-****-{digits[-4:]}"
    return m.group(0)


def _redact_once(text: str) -> str:
    text = _CNIC.sub(lambda m: f"*****-*******-{m.group(1)}", text)
    text = _PAN.sub(_mask_pan, text)
    return _MSISDN.sub(lambda m: f"03xx-xxxx{m.group(3)}", text)


def redact(text: str) -> str:
    """Mask MSISDNs, Luhn-valid PANs and CNICs. Idempotent."""
    while (out := _redact_once(text)) != text:
        text = out
    return text


def contains_pii(text: str) -> bool:
    """True when ``redact`` would change the text."""
    return redact(text) != text
