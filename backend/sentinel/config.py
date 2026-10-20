"""Settings: every variable in .env.example, typed. Model IDs live only here (and the env)."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

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
    sim_admin_token: str = "dev-sim-token"
    sim_speed: float = 1.0
    emit_mode: Literal["http", "pubsub"] = "http"

    # Wiring and tests
    api_internal_url: str = "http://localhost:8080"
    evidence_phase: str = "phase-00-foundation"
    eval_max_usd: float = 5.0
    pubsub_verify_oidc: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
