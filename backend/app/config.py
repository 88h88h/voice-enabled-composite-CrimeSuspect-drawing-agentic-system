from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Reachable by Agora's cloud (the ngrok tunnel) -- used only for the
    # llm.url embedded in the agent config, since that's the one thing an
    # external service actually needs to reach.
    public_base_url: str = "http://localhost:8000"

    # Reachable by the browser, which runs on this same machine. Sketch
    # images and any other browser-facing URL should use this, NOT the
    # ngrok tunnel -- routing local-to-local traffic through an external
    # tunnel is unnecessary and, in practice, unreliable (a real live-tested
    # bug: ngrok's free tier reset the connection serving a ~800KB sketch
    # PNG through the tunnel; fetching it directly from localhost has no
    # such limit).
    local_base_url: str = "http://localhost:8000"

    agora_app_id: str = ""
    agora_app_certificate: str = ""
    agora_customer_id: str = ""
    agora_customer_secret: str = ""

    gemini_api_key: str = ""

    vobiz_auth_id: str = ""
    vobiz_auth_token: str = ""
    vobiz_caseworker_whatsapp_number: str = ""

    database_url: str = "sqlite:///./case_files.db"

    @property
    def vobiz_configured(self) -> bool:
        return bool(self.vobiz_auth_id and self.vobiz_auth_token and self.vobiz_caseworker_whatsapp_number)


settings = Settings()
