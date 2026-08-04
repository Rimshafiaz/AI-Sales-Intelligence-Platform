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


settings = Settings()