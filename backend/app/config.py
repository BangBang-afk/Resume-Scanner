import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./shortlistiq.db")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "none").lower()
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
DEFAULT_WEIGHTS = {"must": 0.40, "preferred": 0.20, "experience": 0.20, "projects": 0.10, "education": 0.10}
