from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, ValidationError, HttpUrl # Added HttpUrl
import os
from typing import Optional

class Settings(BaseSettings):
    OPENAI_API_KEY: Optional[str] = Field(None, validation_alias='OPENAI_API_KEY')

    # OpenMetadata Configuration
    OM_SERVER_URL: Optional[HttpUrl] = Field(None, description="URL of the OpenMetadata server (e.g., http://localhost:8585/api)")
    OM_AUTH_PROVIDER: str = Field("no-auth", description="Authentication provider for OpenMetadata: no-auth, openmetadata, google")
    OM_JWT_TOKEN: Optional[str] = Field(None, description="JWT Token for 'openmetadata' auth provider")
    OM_SECRET_KEY: Optional[str] = Field(None, description="Client secret key for 'google' auth provider (path to JSON or string)")
    OM_GOOGLE_CREDENTIALS_PATH: Optional[str] = Field(None, description="Path to Google credentials JSON file for 'google' auth provider") # Kept as string, can also be audience URL depending on OM SDK version

    # model_config allows pydantic-settings to load from a .env file
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_file_encoding='utf-8')


try:
    settings = Settings()
    if settings.OPENAI_API_KEY == "your_openai_api_key_here":
        print("WARNING: Placeholder OPENAI_API_KEY detected in config. LLM features will not work correctly.")
        # Optionally, you could clear it or raise a less critical warning if it's truly optional for some flows
        # settings.OPENAI_API_KEY = None

except ValidationError as e:
    print(f"Configuration Error: {e}")
    # This part was for critical failure on OpenAI key, adjust if needed for new optional keys
    # missing_openai_key = any(
    #     err['type'] == 'missing' and 'OPENAI_API_KEY' in err['loc']
    #     for err in e.errors()
    # )
    # if missing_openai_key:
    #     print("CRITICAL: OPENAI_API_KEY is not set in the .env file or environment variables.")
    #     print("Please create a .env file in the project root with OPENAI_API_KEY='your_key_here'")
    # raise # Re-raise the exception to halt execution if config is invalid
    # For now, let validation errors print but not necessarily halt,
    # as some services might be optional. Each service will check its required config.

# You can then import 'settings' from this module elsewhere in your application
# Example: from zenbi.core.config import settings
# api_key = settings.OPENAI_API_KEY
