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

# LLM_PROVIDER selects an entry below (default: openrouter). Add a new provider
# by adding one entry here — no other file needs to change.
LLM_PROVIDERS = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": os.getenv("OPENROUTER_API_KEY", ""),
        "default_model": "poolside/laguna-xs-2.1:free",
        "timeout": 30,
        # free-tier model is rate-limited upstream fairly often (openai.RateLimitError,
        # 429) — retry a few times instead of failing the whole request on the first hit.
        "max_retries": 5,
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": os.getenv("GROQ_API_KEY", ""),
        "default_model": "qwen/qwen3.6-27b",
        "timeout": 30,
        "max_retries": 1,
    },
    "ollama": {
        "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        "api_key": "ollama",  # ollama's OpenAI-compat endpoint ignores the key but the client requires one
        "default_model": "granite4.1:3b",
        "timeout": 180,  # local CPU cold start (~2 min)
        "max_retries": 1,
    },
}

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openrouter")
LLM_MODEL = os.getenv("LLM_MODEL") or LLM_PROVIDERS[LLM_PROVIDER]["default_model"]

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_DIM = 384

RERANK_MODEL = os.getenv("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
