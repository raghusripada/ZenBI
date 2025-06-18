from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, ValidationError, HttpUrl # HttpUrl was already there but confirmed
import os
from typing import Optional

class Settings(BaseSettings):
    # OpenAI Configuration
    OPENAI_API_KEY: Optional[str] = Field(None, validation_alias='OPENAI_API_KEY', description="API Key for OpenAI services")
    OPENAI_MODEL_NAME: str = Field("gpt-3.5-turbo", description="Default OpenAI model for ZenSQL and chart suggestions")

    # Ollama Configuration
    OLLAMA_BASE_URL: Optional[HttpUrl] = Field("http://localhost:11434", description="Base URL for Ollama server")
    OLLAMA_MODEL_ZENSQL: str = Field("llama3.1:8b", description="Ollama model for ZenSQL generation")
    OLLAMA_MODEL_CHART: str = Field("llama3.1:8b", description="Ollama model for chart suggestions (can be same as ZenSQL model)")

    # LLM Provider Selection
    LLM_PROVIDER: str = Field("openai", description="LLM provider to use: 'openai' or 'ollama'")

    # OpenMetadata Configuration
    OM_SERVER_URL: Optional[HttpUrl] = Field(None, description="URL of the OpenMetadata server (e.g., http://localhost:8585/api)")
    OM_AUTH_PROVIDER: str = Field("no-auth", description="Authentication provider for OpenMetadata: no-auth, openmetadata, google")
    OM_JWT_TOKEN: Optional[str] = Field(None, description="JWT Token for 'openmetadata' auth provider")
    OM_SECRET_KEY: Optional[str] = Field(None, description="Client secret key for 'google' auth provider (path to JSON or string)")
    OM_GOOGLE_CREDENTIALS_PATH: Optional[str] = Field(None, description="Path to Google credentials JSON file for 'google' auth provider")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_file_encoding='utf-8')


try:
    settings = Settings()
    if settings.LLM_PROVIDER == "openai" and settings.OPENAI_API_KEY == "your_openai_api_key_here":
        print("WARNING: LLM_PROVIDER is 'openai' but OPENAI_API_KEY is set to the placeholder. LLM features will not work correctly.")
    elif settings.LLM_PROVIDER == "openai" and not settings.OPENAI_API_KEY:
         print("WARNING: LLM_PROVIDER is 'openai' but OPENAI_API_KEY is not set. LLM features will not work correctly.")

except ValidationError as e:
    print(f"Configuration Error during settings initialization: {e}")
    # Depending on how critical the settings are, you might re-raise or exit
    # For now, allow to proceed so other parts of app might work if not LLM dependent.

# Example of accessing a setting:
# from zenbi.core.config import settings
# print(settings.LLM_PROVIDER)
# print(settings.OLLAMA_BASE_URL)
