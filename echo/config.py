from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Echo"
    app_version: str = "0.1.0"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8004

    # Database
    database_url: str = "postgresql://localhost:5432/echo"

    # LLM
    anthropic_api_key: str = ""
    llm_model: str = "claude-sonnet-4-20250514"
    llm_max_tokens: int = 4096

    # Storage
    upload_dir: str = "data/uploads"
    sample_dir: str = "data/sample"

    # Auth
    secret_key: str = "change-me-in-production"
    session_expire_minutes: int = 1440  # 24 hours

    model_config = {"env_file": ".env", "env_prefix": "ECHO_"}


settings = Settings()
