from pydantic_settings import BaseSettings
from pydantic import Field

import logging
logger = logging.getLogger(__name__)

class Config(BaseSettings):
    bot_token: str = Field(..., alias="TELEGRAM_BOT_TOKEN")
    db_host: str = Field(..., alias="DB_HOST")
    db_port: int = Field(..., alias="DB_PORT")
    db_user: str = Field(..., alias="DB_USER")
    db_pass: str = Field(..., alias="DB_PASSWORD")
    db_name: str = Field(..., alias="DB_NAME")
    cryptography_key: str = Field(..., alias="CRYPTOGRAPHY_KEY")

    aws_access_key_id: str = Field(..., alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str = Field(..., alias="AWS_SECRET_ACCESS_KEY")
    s3_endpoint_url: str = Field(..., alias="S3_ENDPOINT_URL")
    s3_bucket: str = Field(..., alias="S3_BUCKET")
    s3_region: str = Field(..., alias="S3_REGION")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

def load_config():
    config = Config()
    logger.debug(f"Loaded config: {config.dict()}")
    return config