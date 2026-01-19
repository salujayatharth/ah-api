from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    ah_base_url: str = "https://api.ah.nl"
    ah_user_agent: str = "Appie/9.27.0"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
