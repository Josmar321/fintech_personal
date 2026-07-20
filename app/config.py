from typing import Optional

from pydantic_settings import BaseSettings
from sqlalchemy import URL as DBURL


class Settings(BaseSettings):
    APP_NAME: str = "Fintech Personal"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    DB_HOST: str = "localhost"
    DB_PORT: int = 1433
    DB_NAME: str = "fintech_personal"
    DB_USER: str = "sa"
    DB_PASS: str

    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 60

    IMAP_HOST: Optional[str] = None
    IMAP_PORT: int = 993
    IMAP_USER: Optional[str] = None
    IMAP_PASS: Optional[str] = None
    IMAP_POLL_INTERVAL: int = 300
    IMAP_UNSEEN_ONLY: bool = True

    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None
    TELEGRAM_WEBHOOK_SECRET: Optional[str] = None

    GOOGLE_SHEETS_CREDENTIALS_PATH: Optional[str] = None
    CONDO_SHEET_ID: Optional[str] = None

    @property
    def database_url(self) -> str:
        return str(
            DBURL.create(
                "mssql+aioodbc",
                username=self.DB_USER,
                password=self.DB_PASS,
                host=self.DB_HOST,
                port=self.DB_PORT,
                database=self.DB_NAME,
                query={
                    "driver": "ODBC Driver 18 for SQL Server",
                    "TrustServerCertificate": "yes",
                },
            )
        )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "frozen": True,
    }


settings = Settings()
