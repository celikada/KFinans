from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Veritabanı
    database_url: str

    # JWT
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 480
    refresh_token_expire_days: int = 7

    # Exchange API key şifreleme
    fernet_key: str

    # Claude API — finansal tavsiye özelliği etkinleştirilene kadar opsiyonel
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-6"
    claude_max_tokens: int = 1024

    # Blockchain RPC
    sonic_rpc_url: str = "https://rpc.soniclabs.com"
    avalanche_p_api_url: str = "https://api.avax.network/ext/bc/P"
    avalanche_c_rpc_url: str = "https://api.avax.network/ext/bc/C/rpc"
    infura_api_key: str = ""

    # CORS — production'da frontend domain'i ekle
    cors_origins: list[str] = ["http://localhost:3000"]

    # E-posta (Resend) — kullanıcı kayıt doğrulama
    resend_api_key: str = ""
    email_from: str = "KFinans <noreply@kfinans.app>"
    frontend_url: str = "http://localhost:3000"
    verify_token_expire_hours: int = 24

    @property
    def ethereum_rpc_url(self) -> str:
        if self.infura_api_key:
            return f"https://mainnet.infura.io/v3/{self.infura_api_key}"
        return "https://eth.llamarpc.com"


settings = Settings()
