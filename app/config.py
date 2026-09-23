import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return f"sqlite:///{(BASE_DIR / 'pesasense.db').as_posix()}"

    sqlite_prefix = "sqlite:///"
    if not database_url.startswith(sqlite_prefix):
        return database_url

    sqlite_path = database_url.removeprefix(sqlite_prefix)
    if sqlite_path == ":memory:":
        return database_url

    path = Path(sqlite_path)
    if path.is_absolute():
        return database_url

    return f"sqlite:///{(BASE_DIR / path).resolve().as_posix()}"


def get_bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    APP_NAME = os.getenv("APP_NAME", "PesaSense AI")
    DATABASE_URL = get_database_url()
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://127.0.0.1:5173")
    SMTP_HOST = os.getenv("SMTP_HOST")
    SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
    EMAIL_FROM = os.getenv("EMAIL_FROM")

    SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-key")
    ALGORITHM = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30)
    )
    AUTO_CREATE_TABLES = get_bool_env("AUTO_CREATE_TABLES", True)


settings = Settings()
