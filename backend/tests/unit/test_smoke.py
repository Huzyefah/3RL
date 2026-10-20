import pytest


@pytest.mark.unit
def test_smoke():
    import sentinel

    assert sentinel is not None
