from pydantic_settings import BaseSettings, SettingsConfigDict # Changed import
from pydantic import HttpUrl, Field # HttpUrl and Field are from pydantic
import os
from typing import Optional

class Settings(BaseSettings):
    # LLM Provider Selection
    LLM_PROVIDER: str = Field(default="openai", description="LLM provider to use: 'openai' or 'ollama'")

    # OpenAI Configuration
    OPENAI_API_KEY: Optional[str] = Field(default=None, validation_alias='OPENAI_API_KEY', description="API Key for OpenAI services") # Keep validation_alias if needed for env var name
    OPENAI_MODEL_NAME: str = Field(default="gpt-3.5-turbo", description="Default OpenAI model for ZenSQL and chart suggestions")
    OPENAI_MODEL_INSIGHTS: str = Field(default="gpt-3.5-turbo", description="OpenAI model for generating textual insights")

    # Ollama Configuration
    OLLAMA_BASE_URL: HttpUrl | None = Field(default="http://localhost:11434", description="Base URL for Ollama server") # Use | None for Optional with default
    OLLAMA_MODEL_ZENSQL: str = Field(default="llama3.1:8b", description="Ollama model for ZenSQL generation and chart suggestions")
    OLLAMA_MODEL_CHART: str = Field(default="llama3.1:8b", description="Ollama model for chart suggestions (can be same as ZenSQL model, often is)")
    OLLAMA_MODEL_INSIGHTS: str = Field(default="llama3.1:8b", description="Ollama model for generating textual insights")

    # OpenMetadata Configuration - Fields are now commented out as the feature is removed
    # OM_SERVER_URL: HttpUrl | None = Field(default=None, description="URL of the OpenMetadata server (e.g., http://localhost:8585/api)")
    # OM_AUTH_PROVIDER: str = Field(default="no-auth", description="Authentication provider for OpenMetadata: no-auth, openmetadata, google")
    # OM_JWT_TOKEN: str | None = Field(default=None, description="JWT Token for 'openmetadata' auth provider")
    # OM_SECRET_KEY: str | None = Field(default=None, description="Client secret key for 'google' auth provider (path to JSON or string)")
    # OM_GOOGLE_CREDENTIALS_PATH: str | None = Field(default=None, description="Path to Google credentials JSON file for 'google' auth provider")

    # Pydantic V2 model_config
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding='utf-8',
        extra='ignore' # Allow extra fields in .env that are not defined in Settings
    )


try:
    settings = Settings()
    if settings.LLM_PROVIDER == "openai":
        if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == "your_openai_api_key_here":
            print("WARNING: LLM_PROVIDER is 'openai' but OPENAI_API_KEY is missing or set to the placeholder. OpenAI LLM features will not work.")
    elif settings.LLM_PROVIDER == "ollama":
        if not settings.OLLAMA_BASE_URL or str(settings.OLLAMA_BASE_URL).strip() == "": # OLLAMA_BASE_URL can be None now if not set
             print("WARNING: LLM_PROVIDER is 'ollama' but OLLAMA_BASE_URL is not set or is empty. Ollama LLM features will not work.")
    # else: # This check might be too strict if LLM_PROVIDER has a default and is not always required
    #     print(f"WARNING: LLM_PROVIDER is set to an unsupported value: '{settings.LLM_PROVIDER}'. LLM features may not work as expected.")

except Exception as e: # Catching generic Exception as ValidationError might not be directly raised by Pydantic V2 at instantiation this way
    print(f"CRITICAL Configuration Error during settings initialization: {e}")
    # In a real app, you might want to exit or disable LLM features more formally here.
    # For now, printing a critical error is a strong indication.
    # Depending on how Settings is used, Pydantic might raise errors later when attributes are accessed if parsing failed.
    # If `validate_assignment=True` in model_config, validation error could happen here.
    # For now, assume initialization itself or first access will show issues.
    raise e

# Example of accessing a setting:
# from zenbi.core.config import settings
# print(settings.LLM_PROVIDER)
# print(settings.OLLAMA_MODEL_INSIGHTS)
