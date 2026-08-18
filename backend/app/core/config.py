from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "AI Sales Intelligence Platform"
    app_version: str = "1.0.0"
    app_env: str = "development"

    database_url: str
    supabase_url: str
    supabase_service_role_key: str
    supabase_publishable_key: str
    supabase_jwt_issuer: str
    supabase_jwt_audience: str
    supabase_jwks_url: str

    tavily_api_key: str | None = None
    groq_api_key: str | None = None
    gemini_api_key: str | None = None
    llm_provider: Literal["groq", "gemini"] = "groq"
    groq_model: str = "openai/gpt-oss-20b"
    gemini_model: str = "gemini-3.5-flash"


settings = Settings()
