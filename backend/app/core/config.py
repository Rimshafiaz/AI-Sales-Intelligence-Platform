from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
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

    cors_origins: str = "http://localhost:5173,http://localhost:4173"

    database_url: str
    supabase_url: str
    supabase_service_role_key: str
    supabase_publishable_key: str
    supabase_jwt_issuer: str
    supabase_jwt_audience: str
    supabase_jwks_url: str

    tavily_api_key: str | None = None
    open_places_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPEN_PLACES_API_KEY", "Open_Places_API_KEY"),
    )
    serper_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SERPER_API_KEY", "Serper_API_KEY"),
    )
    pagespeed_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("PAGESPEED_API_KEY", "PageSpeed_API_KEY"),
    )
    apify_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices("APIFY_TOKEN", "Apify_Token"),
    )
    apify_instagram_actor_id: str = "apify/instagram-profile-scraper"
    apify_facebook_actor_id: str = "apify/facebook-pages-scraper"
    apify_tiktok_actor_id: str = "coregent/tiktok-profile-scraper"
    groq_api_key: str | None = None
    gemini_api_key: str | None = None
    llm_provider: Literal["groq", "gemini"] = "groq"
    groq_model: str = "openai/gpt-oss-20b"
    gemini_model: str = "gemini-3.5-flash"

    google_oauth_client_id: str | None = None
    google_oauth_client_secret: SecretStr | None = None
    google_oauth_redirect_uri: str = "http://localhost:8000/integrations/gmail/callback"
    gmail_oauth_frontend_redirect_url: str = "http://localhost:5173/settings"
    gmail_token_encryption_key: SecretStr | None = None


settings = Settings()
