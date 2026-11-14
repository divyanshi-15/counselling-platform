import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "development")
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@postgres:5432/counselling",
    )
    jwt_secret: str = os.getenv("JWT_SECRET", "dev-secret")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    jwt_expire_minutes: int = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))
    model_fast: str = os.getenv("MODEL_FAST", "claude-haiku-5-5")
    model_smart: str = os.getenv("MODEL_SMART", "claude-sonnet-5-5")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
    fastembed_cache: str = os.getenv("FASTEMBED_CACHE_PATH", "/opt/fastembed")
    kb_dir: str = os.getenv("KB_DIR", "kb")
    kb_min_similarity: float = float(os.getenv("KB_MIN_SIMILARITY", "0.80"))


settings = Settings()
