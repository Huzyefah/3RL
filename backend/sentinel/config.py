from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent


def _default_csv() -> Path:
    # Repo layout locally; /app/data in the container (Cloud Build copies the root data/ dir).
    for p in (REPO_ROOT / "data" / "ps02_system_telemetry.csv", Path("/app/data/ps02_system_telemetry.csv")):
        if p.exists():
            return p
    return REPO_ROOT / "data" / "ps02_system_telemetry.csv"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(REPO_ROOT / ".env",), extra="ignore")

    env: str = "dev"
    gcp_project: str = "mda-atomcamp"
    gcp_region: str = "us-central1"
    ps02_csv_path: Path = _default_csv()
    config_dir: Path = BACKEND_DIR / "data"

    openai_api_key: str = ""
    openai_fast_model: str = ""
    openai_smart_model: str = ""
    openai_embed_model: str = ""
    vertex_model: str = ""

    chat_webhook_url: str = ""
    operator_token: str = ""
    sim_base_url: str = "http://localhost:8081"


settings = Settings()
