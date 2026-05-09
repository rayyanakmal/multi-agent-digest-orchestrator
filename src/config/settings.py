"""Settings and environment configuration for the daily digest app"""

from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # LLM Provider Configuration
    llm_provider: str = Field(default="deepseek", env="LLM_PROVIDER")
    llm_model: str = Field(default="deepseek-chat", env="LLM_MODEL")
    deepseek_api_key: Optional[str] = Field(default=None, env="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(default="https://api.deepseek.com/v1", env="DEEPSEEK_BASE_URL")
    
    # Alternative providers
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")

    # News and Content Sources
    newsapi_key: Optional[str] = Field(default=None, env="NEWSAPI_KEY")
    github_token: Optional[str] = Field(default=None, env="GITHUB_TOKEN")
    rss_feeds: str = Field(
        default=(
            "https://news.ycombinator.com/rss,"
            "https://feeds.arstechnica.com/arstechnica/index,"
            "https://arxiv.org/list/cs.AI/rss,"
            "https://www.zdnet.com/topic/artificial-intelligence/rss.xml,"
            "https://blog.google/technology/ai/rss/,"
            "https://aws.amazon.com/blogs/machine-learning/feed/,"
            "https://cloudblog.withgoogle.com/topics/ai-ml/rss/"
        ),
        env="RSS_FEEDS"
    )

    # Digest Configuration
    digest_topic: str = Field(default="Technology,Artificial Intelligence", env="DIGEST_TOPIC")
    digest_time: str = Field(default="07:00", env="DIGEST_TIME")
    digest_tz: str = Field(default="UTC", env="DIGEST_TZ")
    max_articles: int = Field(default=20, env="MAX_ARTICLES")
    max_retries: int = Field(default=2, env="MAX_RETRIES")
    max_run_seconds: int = Field(default=300, env="MAX_RUN_SECONDS")

    # Cost and Budget Controls
    cost_limit_usd: float = Field(default=0.05, env="COST_LIMIT_USD")
    token_budget: int = Field(default=10000, env="TOKEN_BUDGET")

    # Google Drive Configuration
    google_application_credentials: str = Field(
        default="/app/credentials/google-service-account.json",
        env="GOOGLE_APPLICATION_CREDENTIALS"
    )
    google_drive_folder_id: Optional[str] = Field(default=None, env="GOOGLE_DRIVE_FOLDER_ID")
    google_service_account_json: Optional[str] = Field(
        default=None,
        env="GOOGLE_SERVICE_ACCOUNT_JSON",
        description="Service account JSON for Cloud Run (env-injected from Secret Manager). If present, takes precedence over OAuth credentials."
    )

    # Runtime Configuration
    run_mode: str = Field(default="scheduler", env="RUN_MODE")  # once | scheduler
    output_format: str = Field(default="pdf", env="OUTPUT_FORMAT")  # pdf | html | markdown
    data_dir: str = Field(default="./data", env="DATA_DIR")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")

    # Development/Debug
    debug: bool = Field(default=False, env="DEBUG")

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    def get_rss_feeds_list(self) -> list[str]:
        """Parse RSS feeds from comma-separated string"""
        return [feed.strip() for feed in self.rss_feeds.split(",") if feed.strip()]

    def validate_llm_provider(self) -> bool:
        """Validate that required API keys are set for the chosen provider"""
        if self.llm_provider == "deepseek":
            return self.deepseek_api_key is not None
        elif self.llm_provider == "openai":
            return self.openai_api_key is not None
        elif self.llm_provider == "anthropic":
            return self.anthropic_api_key is not None
        return False


_settings_instance: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create settings singleton"""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance


def reload_settings() -> Settings:
    """Reload settings from environment (useful for testing)"""
    global _settings_instance
    _settings_instance = Settings()
    return _settings_instance
