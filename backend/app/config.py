from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    public_base_url: str = "http://localhost:8000"

    agora_app_id: str = ""
    agora_app_certificate: str = ""
    agora_customer_id: str = ""
    agora_customer_secret: str = ""

    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""

    gemini_api_key: str = ""

    vobiz_auth_id: str = ""
    vobiz_auth_token: str = ""
    vobiz_caseworker_whatsapp_number: str = ""

    database_url: str = "sqlite:///./case_files.db"

    @property
    def vobiz_configured(self) -> bool:
        return bool(self.vobiz_auth_id and self.vobiz_auth_token and self.vobiz_caseworker_whatsapp_number)


settings = Settings()
