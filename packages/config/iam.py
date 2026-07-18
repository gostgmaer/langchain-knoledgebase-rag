from pydantic_settings import BaseSettings, SettingsConfigDict


class IAMSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="IAM_",
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    base_url: str
    client_id: str
    client_secret: str
    introspection_api_key: str

    timeout: int = 30
    verify_ssl: bool = True
    max_retries: int = 3
