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

    # ─── Güvenlik header'ları (FAZ C2) ────────────────────────────────
    # Production'da True; testlerde header beklemek için açık tutulur.
    # Dev ortamda Swagger UI deneyimini bozmamak için False yapılabilir.
    enable_security_headers: bool = True
    hsts_max_age: int = 31536000  # 1 yıl
    # Backend JSON-only; Swagger UI kullanımı için override:
    #   "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; ..."
    csp_policy: str = (
        "default-src 'none'; "
        "frame-ancestors 'none'; "
        "base-uri 'none'; "
        "form-action 'none'"
    )

    # ─── TrustedHost (FAZ C3) ─────────────────────────────────────────
    # Host header injection koruması. Prod'da override edilir; dev'de "*"
    # (tüm Host header'larına izin) çünkü localhost + 127.0.0.1 + IP karışık.
    allowed_hosts: list[str] = ["*"]

    # E-posta (Resend) — kullanıcı kayıt doğrulama
    resend_api_key: str = ""
    email_from: str = "KFinans <noreply@kfinans.app>"
    frontend_url: str = "http://localhost:3000"
    verify_token_expire_hours: int = 24

    # ─── DBA-004 (FAZ H): Connection pool ─────────────────────────────
    # FastAPI async + APScheduler haftalik snapshot + asyncio.gather (10+ paralel)
    # default 5+10=15 max conn'i tuketir. Production'da PostgreSQL max_connections
    # 100 oldugu dusunulurse 30 backend safe (1 replica). Multi-replica icin
    # her replica `db_pool_size + db_max_overflow <= 30`.
    db_pool_size: int = 20         # idle pool size
    db_max_overflow: int = 10      # peak'te ek connection
    db_pool_recycle: int = 1800    # 30 dk — stale connection (PG idle_in_transaction_session_timeout)
    db_pool_timeout: int = 30      # pool tukenince istek 30sn bekler, sonra fail

    @property
    def ethereum_rpc_url(self) -> str:
        if self.infura_api_key:
            return f"https://mainnet.infura.io/v3/{self.infura_api_key}"
        return "https://eth.llamarpc.com"


settings = Settings()
