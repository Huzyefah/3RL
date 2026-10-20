import pytest


@pytest.mark.unit
def test_smoke():
    import finpay_sim

    assert finpay_sim is not None
