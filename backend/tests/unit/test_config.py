import pytest
from pydantic import ValidationError

from sentinel.config import Settings, get_settings


@pytest.fixture(autouse=True)
def _clean(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in (
        "LLM_PROVIDER", "SIM_SPEED", "KILL_SWITCH", "DEMO_CONTROLS", "STORE", "BUS",
        "OPENAI_FAST_MODEL", "SECURITY_AUTONOMY", "EVAL_MAX_USD", "GCP_REGION",
        "ENV", "SIM_ADMIN_TOKEN",
    ):  # fmt: skip
        monkeypatch.delenv(k, raising=False)
    get_settings.cache_clear()


@pytest.mark.unit
def test_defaults_match_env_example() -> None:
    s = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]
    assert s.llm_provider == "scripted"
    assert s.openai_fast_model == "gpt-6-luna"
    assert s.openai_smart_model == "gpt-6.1-sol"
    assert s.openai_judge_model == "gpt-5.5"
    assert s.gcp_region == "asia-south1"
    assert s.bus == "memory" and s.store == "memory"
    assert s.security_autonomy == "shadow"
    assert s.kill_switch is False and s.demo_controls is True
    assert s.sim_speed == 1.0 and s.eval_max_usd == 5.0
    assert s.emit_mode == "http" and s.pubsub_verify_oidc is False


@pytest.mark.unit
def test_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("SIM_SPEED", "10")
    monkeypatch.setenv("KILL_SWITCH", "1")
    monkeypatch.setenv("OPENAI_FAST_MODEL", "x-model")
    s = get_settings()
    assert s.llm_provider == "openai" and s.sim_speed == 10.0
    assert s.kill_switch is True and s.openai_fast_model == "x-model"


@pytest.mark.unit
def test_invalid_provider_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "vertex")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # pyright: ignore[reportCallIssue]


@pytest.mark.unit
def test_get_settings_cached() -> None:
    assert get_settings() is get_settings()


@pytest.mark.unit
def test_every_env_example_var_has_a_field() -> None:
    from pathlib import Path

    text = (Path(__file__).parents[3] / ".env.example").read_text()
    names = {
        line.split("=", 1)[0].strip().lower()
        for line in text.splitlines()
        if "=" in line and not line.lstrip().startswith("#")
    }
    assert names <= set(Settings.model_fields)


@pytest.mark.unit
def test_env_defaults_to_dev_with_dev_token() -> None:
    s = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]
    assert s.env == "dev" and s.sim_admin_token == "dev-sim-token"


@pytest.mark.unit
@pytest.mark.parametrize("token", ["dev-sim-token", ""])
def test_non_dev_env_rejects_default_or_empty_admin_token(
    monkeypatch: pytest.MonkeyPatch, token: str
) -> None:
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("SIM_ADMIN_TOKEN", token)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # pyright: ignore[reportCallIssue]


@pytest.mark.unit
def test_non_dev_env_accepts_real_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("SIM_ADMIN_TOKEN", "s3cret-value")
    assert Settings(_env_file=None).sim_admin_token == "s3cret-value"  # pyright: ignore[reportCallIssue]
