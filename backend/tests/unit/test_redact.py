import re

import pytest
from hypothesis import given
from hypothesis import strategies as st

from sentinel.redact import contains_pii, redact

MSISDN = re.compile(r"(?<!\d)03\d{9}")


@pytest.mark.unit
def test_redact_msisdn_pan_cnic():
    assert redact("call 03001234567 now") == "call 03xx-xxxx567 now"
    assert redact("call +923001234567") == "call 03xx-xxxx567"
    assert redact("call 0300-1234567") == "call 03xx-xxxx567"
    # Luhn-valid test PAN is masked, last four kept
    assert redact("card 4111 1111 1111 1111 ok") == "card ****-****-****-1111 ok"
    assert redact("card 4111111111111111") == "card ****-****-****-1111"
    # Same length but Luhn-invalid: not a PAN
    assert redact("ref 4111111111111112") == "ref 4111111111111112"
    assert redact("cnic 35202-1234567-1") == "cnic *****-*******-1"
    assert redact("no pii here, 12 users, 500 errors") == "no pii here, 12 users, 500 errors"


@pytest.mark.unit
def test_contains_pii():
    assert contains_pii("03001234567")
    assert contains_pii("4111111111111111")
    assert contains_pii("35202-1234567-1")
    assert not contains_pii("4111111111111112")
    assert not contains_pii(redact("03001234567 4111111111111111 35202-1234567-1"))


@pytest.mark.unit
@given(st.text(alphabet="0123456789 -+x", max_size=60))
def test_redact_leaves_no_msisdn(text: str):
    out = redact(text)
    assert not MSISDN.search(out)
    assert redact(out) == out  # idempotent


@pytest.mark.unit
@given(st.text(max_size=40), st.from_regex(r"03\d{9}", fullmatch=True), st.text(max_size=40))
def test_redact_embedded_msisdn_never_survives(a: str, m: str, b: str):
    assert not MSISDN.search(redact(a + " " + m + b))


@pytest.mark.unit
@pytest.mark.parametrize(
    "text",
    [
        "at 2026-10-20T10:15:30Z ok",
        "2026-10-20 10:15:30.123456+05:00",
        "ts 1789900000000",
        "id 1020030123456789",
        "score 0.9503012345678",
        "value 12345.0382",
        "evidence segment:3fa1c2d9",
        "INC-2026-1020-004",
        "INC-0007",
        "num 1234567890123",
        "num 4111111111112",
    ],
)
def test_redact_leaves_non_pii_untouched(text: str):
    assert redact(text) == text
    assert not contains_pii(text)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("0300-1234567", "03xx-xxxx567"),
        ("+92 300 1234567", "03xx-xxxx567"),
        ("92 300 1234567", "03xx-xxxx567"),
        ("923001234567", "03xx-xxxx567"),
        ("call 0092-300-1234567.", "call 03xx-xxxx567."),
        ("pan 4111-1111-1111-1111", "pan ****-****-****-1111"),
        ("pan 4111 1111 1111 1111", "pan ****-****-****-1111"),
        ("cnic 35202-1234567-1", "cnic *****-*******-1"),
    ],
)
def test_redact_formats(text: str, expected: str):
    assert redact(text) == expected
    assert redact(expected) == expected
