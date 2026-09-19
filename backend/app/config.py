from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "SAHILABEL"
    app_version: str = "1.0.0"
    environment: str = "development"
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    frontend_url: str = "http://localhost:5173"
    postgres_url: str = "postgresql://postgres:postgres@localhost:5432/legal_metrology"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret_key: str = "replace-with-a-secure-secret"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
