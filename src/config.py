import os

from dotenv import load_dotenv

load_dotenv()

POSTGRES_USER = os.getenv("POSTGRES_USER", "factchecker")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "factchecker")
POSTGRES_DB = os.getenv("POSTGRES_DB", "factchecker")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")

DATABASE_URL = (
    f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)

FRED_API_KEY = os.getenv("FRED_API_KEY", "")

# LLM_PROVIDER=openrouter (default, needs OPENROUTER_API_KEY) or ollama (local, no key)
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openrouter")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
LLM_MODEL = os.getenv(
    "LLM_MODEL", "tencent/hy3:free" if LLM_PROVIDER == "openrouter" else "ornith:latest"
)

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_DIM = 384
