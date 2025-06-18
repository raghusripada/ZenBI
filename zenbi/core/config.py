from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, ValidationError, HttpUrl
import os
from typing import Optional

class Settings(BaseSettings):
    # LLM Provider Selection
    LLM_PROVIDER: str = Field("openai", description="LLM provider to use: 'openai' or 'ollama'")

    # OpenAI Configuration
    OPENAI_API_KEY: Optional[str] = Field(None, validation_alias='OPENAI_API_KEY', description="API Key for OpenAI services")
    OPENAI_MODEL_NAME: str = Field("gpt-3.5-turbo", description="Default OpenAI model for ZenSQL and chart suggestions")
    OPENAI_MODEL_INSIGHTS: str = Field("gpt-3.5-turbo", description="OpenAI model for generating textual insights")

    # Ollama Configuration
    OLLAMA_BASE_URL: Optional[HttpUrl] = Field("http://localhost:11434", description="Base URL for Ollama server")
    OLLAMA_MODEL_ZENSQL: str = Field("llama3.1:8b", description="Ollama model for ZenSQL generation and chart suggestions")
    OLLAMA_MODEL_CHART: str = Field("llama3.1:8b", description="Ollama model for chart suggestions (can be same as ZenSQL model, often is)") # Kept for consistency, though current LLM service uses OLLAMA_MODEL_ZENSQL for charts
    OLLAMA_MODEL_INSIGHTS: str = Field("llama3.1:8b", description="Ollama model for generating textual insights")

    # OpenMetadata Configuration
    OM_SERVER_URL: Optional[HttpUrl] = Field(None, description="URL of the OpenMetadata server (e.g., http://localhost:8585/api)")
    OM_AUTH_PROVIDER: str = Field("no-auth", description="Authentication provider for OpenMetadata: no-auth, openmetadata, google")
    OM_JWT_TOKEN: Optional[str] = Field(None, description="JWT Token for 'openmetadata' auth provider")
    OM_SECRET_KEY: Optional[str] = Field(None, description="Client secret key for 'google' auth provider (path to JSON or string)")
    OM_GOOGLE_CREDENTIALS_PATH: Optional[str] = Field(None, description="Path to Google credentials JSON file for 'google' auth provider")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_file_encoding='utf-8')


try:
    settings = Settings()
    if settings.LLM_PROVIDER == "openai":
        if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == "your_openai_api_key_here":
            print("WARNING: LLM_PROVIDER is 'openai' but OPENAI_API_KEY is missing or set to the placeholder. OpenAI LLM features will not work.")
    elif settings.LLM_PROVIDER == "ollama":
        if not settings.OLLAMA_BASE_URL or str(settings.OLLAMA_BASE_URL).strip() == "":
             print("WARNING: LLM_PROVIDER is 'ollama' but OLLAMA_BASE_URL is not set. Ollama LLM features will not work.")
    else:
        print(f"WARNING: LLM_PROVIDER is set to an unsupported value: '{settings.LLM_PROVIDER}'. LLM features may not work as expected.")

except ValidationError as e:
    print(f"CRITICAL Configuration Error during settings initialization: {e}")
    # In a real app, you might want to exit or disable LLM features more formally here.
    # For now, printing a critical error is a strong indication.
    raise e # Re-raise to prevent app from starting with invalid critical settings

# Example of accessing a setting:
# from zenbi.core.config import settings
# print(settings.LLM_PROVIDER)
# print(settings.OLLAMA_MODEL_INSIGHTS)
