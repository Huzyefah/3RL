"""Settings: every variable in .env.example, typed. Model IDs live only here (and the env)."""

from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SIM_TOKEN = "dev-sim-token"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    env: Literal["dev", "test", "staging", "prod"] = "dev"

    # LLM (OpenAI only, D15)
    openai_api_key: str = ""
    openai_fast_model: str = "gpt-6-luna"
    openai_smart_model: str = "gpt-6.1-sol"
    openai_embed_model: str = "text-embedding-3-small"
    openai_judge_model: str = "gpt-5.5"
    llm_provider: Literal["openai", "scripted", "fake"] = "scripted"

    # GCP
    gcp_project: str = ""
    gcp_region: str = "asia-south1"

    # Infrastructure
    bus: Literal["memory", "pubsub"] = "memory"
    store: Literal["memory", "bigquery"] = "memory"
    chat_webhook_url: str = ""

    # Policy and demo
    security_autonomy: Literal["off", "shadow", "enforce"] = "shadow"
    kill_switch: bool = False
    demo_controls: bool = True
    demo_passcode: str = ""

    # Simulator
    sim_base_url: str = "http://localhost:8081"
    sim_admin_token: str = DEV_SIM_TOKEN
    sim_speed: float = 1.0
    emit_mode: Literal["http", "pubsub"] = "http"

    # Wiring and tests
    api_internal_url: str = "http://localhost:8080"
    evidence_phase: str = "phase-00-foundation"
    eval_max_usd: float = 5.0
    pubsub_verify_oidc: bool = False

    @model_validator(mode="after")
    def _require_real_admin_token_outside_dev(self) -> "Settings":
        if self.env != "dev" and self.sim_admin_token in ("", DEV_SIM_TOKEN):
            raise ValueError("SIM_ADMIN_TOKEN must be set to a non-default value when ENV != dev")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
