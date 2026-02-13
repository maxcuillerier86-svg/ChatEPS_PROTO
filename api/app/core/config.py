from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Co-PE API"
    secret_key: str = "change-me"
    access_token_expire_minutes: int = 60 * 8
    database_url: str = "sqlite:///./data/cope.db"
    qdrant_url: str = "http://qdrant:6333"
    qdrant_collection: str = "pdf_chunks"
    ollama_url: str = "http://ollama:11434"
    ollama_chat_model: str = "llama3.1"
    ollama_embedding_model: str = "nomic-embed-text"
    storage_root: str = "./data"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
