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
    # SEC-001 (FAZ H): Password reset token TTL — OWASP onerisi 1 saat.
    password_reset_expire_hours: int = 1

    # ─── SEC-003 (FAZ H): Redis URL — slowapi distributed rate limiting ──
    # Default bos = MemoryStorage (tek replica icin uygun). Multi-replica
    # K8s deploy'da `redis://kfinans-redis:6379/0` gibi set edilir.
    redis_url: str = ""

    # ─── COMP-022 (FAZ H): audit_logs retention (KVKK m.7) ────────────
    # 365 gun = forensic icin 1 yillik makul saklama. _purge_old_audit_logs_job
    # her gun 04:30 Europe/Istanbul'da bu suredan eski kayitlari fiziksel siler.
    audit_log_retention_days: int = 365

    # ─── OBS-001 (FAZ H): Sentry + OpenTelemetry ─────────────────────
    # Hepsi opt-in. DSN/endpoint bos ise no-op (dev'de aktif degil).
    sentry_dsn: str = ""
    sentry_env: str = "development"
    sentry_traces_sample_rate: float = 0.1   # %10 trace ornegi
    sentry_profiles_sample_rate: float = 0.0  # CPU profiling — kapali default
    otel_endpoint: str = ""                   # Tempo/Jaeger/Honeycomb OTLP HTTP
    otel_service_name: str = "kfinans-backend"

    # ─── SEC-009 (FAZ H): File upload validation ─────────────────────
    # 10 Excel import endpoint'i (BES, expense, income, commodity, manual_crypto,
    # wallets, stocks MKK + manuel, tefas MKK + manuel) bu limiti kullanir.
    # DoS koruma — openpyxl memory blow engellenir. 5MB tipik Excel icin yeterli.
    max_upload_size_mb: int = 5

    # ─── PERF-004 (FAZ H): Request timing middleware ─────────────────
    # >= slow_request_threshold_ms requestler WARNING log'a yazilir.
    # /metrics/performance endpoint metrics_token bos ise 404 doner
    # (production'da env ile set edilir; dev'de devre disi).
    slow_request_threshold_ms: int = 500
    metrics_token: str = ""

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
