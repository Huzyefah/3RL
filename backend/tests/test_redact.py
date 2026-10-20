import pytest

from sentinel.redact import PIIError, assert_no_pii, redact


def test_redact_msisdn_pan_cnic():
    raw = "user 03001234567 paid with 4111111111111111 cnic 35202-1234567-1 ref 1234567890123456"
    out = redact(raw)
    assert "03001234567" not in out and "03xx-xxxx567" in out
    assert "4111111111111111" not in out and "****1111" in out
    assert "35202-1234567-1" not in out
    # Not Luhn-valid, so not treated as a card number.
    assert "1234567890123456" in out
    assert_no_pii(out)


def test_assert_no_pii_helper():
    with pytest.raises(PIIError):
        assert_no_pii({"prompt": "call 03211234567"})
    with pytest.raises(PIIError):
        assert_no_pii(["card 5500005555555559"])
    with pytest.raises(PIIError):
        assert_no_pii("id 61101-7654321-9")
    assert_no_pii({"ok": "masked 03xx-xxxx567, latency 1234567 ms"})
