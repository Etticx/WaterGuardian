from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / '.env', extra='ignore')
    groq_api_key: str = ''
    groq_model: str = 'openai/gpt-oss-120b'
    gemini_api_key: str = ''
    gemini_model: str = 'gemini-2.5-flash'
    ollama_base_url: str = 'http://127.0.0.1:11434'
    ollama_model: str = 'qwen3.5:2b-q4_K_M'
    ollama_models_dir: str = ''
    llm_timeout_seconds: float = 35
    backend_port: int = 9000
    database_url: str = 'sqlite:///data/water_guardian.db'
    workflow_database_path: str = 'data/workflow_checkpoints.db'
    dataset_dir: str = 'WDSEventDB'
    ml_model_path: str = 'models/monitor.joblib'
    ml_evaluation_path: str = 'models/evaluation.json'
    cors_origins: str = 'http://localhost:3000,http://127.0.0.1:3000'

    def path(self, value: str) -> Path:
        p = Path(value)
        return p if p.is_absolute() else ROOT / p


settings = Settings()

