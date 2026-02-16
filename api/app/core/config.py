from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Co-PE API"
    secret_key: str = "change-me"
    access_token_expire_minutes: int = 60 * 8
    database_url: str = "sqlite:///./data/cope.db"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "pdf_chunks"
    ollama_url: str = "http://localhost:11434"
    ollama_chat_model: str = "llama3.1"
    ollama_embedding_model: str = "nomic-embed-text"
    storage_root: str = "./data"
    obsidian_vault_path: str | None = None
    obsidian_rest_api_base_url: str | None = None
    obsidian_api_key: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
