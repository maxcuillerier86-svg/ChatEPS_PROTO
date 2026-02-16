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
    obsidian_mode: str = "filesystem"
    obsidian_vault_path: str | None = None
    obsidian_rest_api_base_url: str = "http://127.0.0.1:27124"
    obsidian_api_key: str | None = None
    obsidian_included_folders: str = ""
    obsidian_excluded_folders: str = ".obsidian,templates,attachments"
    obsidian_excluded_patterns: str = ".obsidian/**,templates/**,attachments/**"
    obsidian_max_notes_to_index: int = 5000
    obsidian_max_note_bytes: int = 500000
    obsidian_incremental_indexing: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
