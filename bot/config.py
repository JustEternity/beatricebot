from pydantic_settings import BaseSettings
from pydantic import Field

class Config(BaseSettings):
    bot_token: str = Field(..., alias="TELEGRAM_BOT_TOKEN")
    db_host: str = Field(..., alias="DB_HOST")
    db_port: int = Field(..., alias="DB_PORT")
    db_user: str = Field(..., alias="DB_USER")
    db_pass: str = Field(..., alias="DB_PASSWORD")
    db_name: str = Field(..., alias="DB_NAME")
    cryptography_key: str = Field(..., alias="CRYPTOGRAPHY_KEY")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

def load_config():
    return Config()