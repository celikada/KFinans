# AI Audit Notları — 2026-05-22

Kapsam: `app/services/advisor.py` + `app/api/v1/advice.py` + `app/models/advice.py` + Anthropic
SDK `claude-sonnet-4-6` entegrasyonu. AI-001..AI-008 etiketleri ile FAZ H'da olgunlaşan
LLM hattı.

## ✓ Mevcut Pozitif

- **AI-001 timeout sınırı:** `_CLAUDE_TIMEOUT_SECONDS = 60.0` (advisor.py:16) — `httpx`
  default no-timeout senaryosunda FastAPI worker'ın askıda kalması engellendi.
- **AI-001 exception taxonomy:** Anthropic SDK'nın 7 exception tipi (RateLimit, APITimeout,
  APIConnection, Authentication, BadRequest, APIStatusError, AnthropicError) ayrı ayrı
  yakalanıyor → uygun HTTP status (429/504/503/500). `from exc` ile chain korunuyor,
  `logger.warning/error/critical` doğru seviyelerde.
- **AI-003 SPK uyumluluğu:** System prompt'ta SPK Kanunu m.40 atıfı + 5 madde kısıtlama +
  yasaklı çıktı listesi (`alın/satın/yatırım yapın`, `kesin/garanti`, kaldıraç tavsiyesi).
- **AI-003 post-processing footer:** `_ensure_disclaimer()` LLM disclaimer atlatırsa
  otomatik ekler; `_DISCLAIMER_MARKERS` kalıp eşleşmesi (case-insensitive) — defence-in-depth.
- **AI-005 KVKK m.9 özel rıza:** `anthropic_consent_at` kontrolü endpoint'in ilk adımı;
  yurt dışı veri aktarımı için spesifik onay olmadan Anthropic'e veri gitmiyor.
- **AI-007 kredi düşümü atomik:** `ADVICE_COST = 1` `current_user.credit_balance -= 1` +
  `advice.credits_used = 1` aynı `db.commit()` içinde — Anthropic başarıyla yanıt verdikten
  sonra çalışır, fail durumunda kredi düşmez.
- **AI-008 prompt cache aktif:** System prompt 1024+ token, `cache_control: ephemeral` ile
  Anthropic 5dk cache (Sonnet/Opus min eşik 1024 token üzeri). Cache hit'te ~%90 maliyet
  tasarrufu.
- **AI-002 cache metrikleri DB'ye yazılıyor:** `cache_read_tokens` + `cache_creation_tokens`
  `investment_advice` tablosunda nullable kolonlar (advice.py:38-39) — eski SDK geri uyumlu.
- **AI-004 audit log:** Her üretim `AuditAction.ADVICE_GENERATE` ile loglanıyor (model adı +
  token sayıları + snapshot_date + credits_used) — KVKK m.12 üçüncü taraf aktarımı izleniyor.
- **Rate limit:** `@limiter.limit("5/hour")` slowapi backend (Redis prod) — kullanıcı başına
  saatte 5 istek; spam + maliyet kontrolü.
- **Config'den model adı:** `settings.claude_model` (`claude-sonnet-4-6`) + `claude_max_tokens`
  hardcode değil — `.env` ile model değiştirilebilir.

## ⚠ Çelişti / Düzeltme Notları

| # | Öncelik | Sorun | Etki | Öneri |
|---|---------|-------|------|-------|
| 1 | High | LLM provider tek (Anthropic). API down ya da Türkiye'den blok geldiğinde tüm advice motoru ölür. | Tek nokta arıza (SPOF). Anthropic 503 + KFinans /advice/generate 503 zincirleme. | `LLMProvider` Protocol adapter pattern: `AnthropicProvider`, `OpenAIProvider`, `GeminiProvider`. Env `LLM_PROVIDER=anthropic\|openai\|gemini` + fallback chain. Cost monitor'la primary/secondary swap. |
| 2 | High | Prompt cache hit oranı **izlenmiyor**. Sadece DB'ye yazılıyor, alert/dashboard yok. | Hit oranı <%80 düşerse maliyet sessizce 5x artar. AI-008 yatırımı boşa gider. | `GET /api/v1/metrics/ai` endpoint (PERF-004 pattern reuse): son 7 gün cache hit oranı + ortalama input/output token + USD maliyet projeksiyonu. Hit oranı <70% düşerse Sentry breadcrumb. |
| 3 | High | Prompt injection koruması yok. Kullanıcı `risk_profile` String — DB'de manipüle edilse `"; IGNORE ABOVE..."` user prompt'a injekte olur. | LLM jailbreak: disclaimer atlatma, "X coin'i al" tavsiyesi üretme. Çıktı disclaimer'ı `_ensure_disclaimer()` yakalar ama SPK kuralı geçer. | User input sanitization: `risk_profile` enum constraint (DB CHECK), user prompt'a girer önce `escape_user_input()` (newline + markdown special char escape). System prompt en sona "Aşağıdaki talimatları yoksay" gibi pattern blacklist. |
| 4 | Medium | System prompt versiyonlama yok. Prompt değiştiğinde geçmiş advice'lar hangi prompt versiyonuyla üretildiğini bilmiyor. | A/B test imkânsız, SPK uyum denetiminde "hangi prompt ne zaman aktifti" cevaplanamaz. | `investment_advice.prompt_version` kolonu (VARCHAR 16). `_SYSTEM_PROMPT` hash (sha256 ilk 8) ya da semver tag. Prompt'u dosyaya taşı: `prompts/advisor_v1.2.md` + `git` tarihçesi. |
| 5 | Medium | `_REQUIRED_DISCLAIMER` yalnızca Türkiye SPK için. Multi-jurisdiction yok (EU MiFID II, US SEC). | i18n-002 EN çevirisi sonrası TR-only disclaimer yabancı kullanıcılara yanlış uyum bilgisi verir. | `_DISCLAIMER_BY_LOCALE = {"tr": SPK, "en": "Not investment advice. Consult a licensed advisor..."}`. User locale + jurisdiction (`user.country`) feature flag. MiFID II için "complex product" + risk warning ek satır. |
| 6 | Medium | `max_tokens: 1024` hardcode default; uzun portföylerde çıktı kesilebilir. | Cevap "Disclaimer" başlığına gelmeden kesilirse `_ensure_disclaimer()` footer ekler — ama yapı bozuk olur. | `stop_reason` kontrol et: `"max_tokens"` ise log warning + DB'ye flag (`truncated=True`). User'a UI'da "Cevap uzunluk limitine takıldı, tekrar deneyin" göster. Adaptive: portföy >20 varlık ise `max_tokens=2048`. |
| 7 | Medium | Çıktı format validation yok. LLM disclaimer'sız + bozuk Markdown verirse `_ensure_disclaimer()` ekler ama yapı (`## Portföyünüze Genel Bakış` vs.) doğrulanmaz. | Frontend Markdown render'da kırılma; SPK kontrol panelinde "5 başlık zorunlu" denetimi geçmez. | Pydantic schema: `AdviceContentValidator` (markdown parser + heading list assertion). Fail → retry 1 kez + farklı seed/temperature; ikinci fail logla + best-effort dön. |
| 8 | Medium | Kullanıcı maliyet bütçesi (budget) yok. `credit_balance` UI'da sayı, USD karşılığı yok. | Pricing modeli netleşince kullanıcı kafa karışıklığı; "1 kredi kaç tavsiye?" muğlak. | Settings sayfasında "1 kredi ≈ 1 tavsiye ≈ $0.02 Anthropic maliyet" şeffaflık. Aylık limit ayarı (kullanıcı kendi koyar; 20 advice/ay vb.). Limit aşımı → Sentry breadcrumb. |
| 9 | Low | Cache key user-agnostic değil — sadece system prompt cache'lenir. User prompt her seferinde yeniden token sayılır. | %20 ek maliyet (user prompt 150-300 token, 5/saat × N user → eklenir). | User prompt'u da `cache_control: ephemeral` yapılabilir mi? Hayır: portföy snapshot her hafta değişir. Alternatif: aynı snapshot için aynı horizon → idempotent cache (`(snapshot_id, horizon)` key → DB'den döndür, Anthropic çağırma). |
| 10 | Low | Test coverage AI hattında düşük. `tests/unit/test_advisor.py` mock'lu ama integration testi yok (gerçek Anthropic dummy key ile). | Anthropic SDK breaking change'i (örn. `messages.create` signature) CI'da yakalanmaz. | `tests/integration/test_advice_endpoint.py` + `respx`/`vcr.py` ile Anthropic HTTP cevabını cassette'le; deterministik replay. |
| 11 | Low | `claude-sonnet-4-6` model ismi config'de ama Anthropic deprecation policy (12 ay) yok. | 2027'de model retire olduğunda silent fail → 400 BadRequest. | `Anthropic-Version` header + deprecated model detection (response header `anthropic-version` warning). `MODEL_DEPRECATION_DATES` config dict; 90 gün öncesi UI banner. |
| 12 | Low | `_ensure_disclaimer` marker eşleşmesi case-insensitive ama LLM tamamen farklı kelime kullanırsa ("bilgilendirme amaçlıdır, danışmanlık değildir") miss eder. | Yanlış pozitif: doğru disclaimer LLM yazsa bile ikinci kez append'lenir → çift footer. | Marker yerine semantic check: footer son N karakter içinde `_REQUIRED_DISCLAIMER` substring tam eşleşme; yoksa LLM disclaimer geç, footer'ı **append etme** (yalnızca eksikse ekle). |

## Reusability / Portability

### LLM Provider Adapter Pattern (#1)

Şu an `AdvisorService.__init__` `anthropic.AsyncAnthropic` doğrudan instantiate ediyor.
Önerilen yapı:

```python
# app/services/llm/base.py
class LLMProvider(Protocol):
    async def generate(self, system: str, user: str, *, max_tokens: int, cache: bool) -> LLMResponse: ...

# app/services/llm/{anthropic,openai,gemini}_provider.py
class AnthropicProvider(LLMProvider): ...
class OpenAIProvider(LLMProvider): ...

# config.py
llm_provider: str = "anthropic"  # anthropic|openai|gemini
llm_fallback_chain: list[str] = ["anthropic", "openai"]  # primary fail → secondary
```

Bu pattern sadece advisor.py için değil; gelecekteki LLM use case'leri (örn. **expense
auto-categorization**, **portfolio anomaly detection**, **MKK Excel column mapping**) için
de reuse edilebilir. Şu an her use case Anthropic SDK'ya direct bind olmuş — adapter yok.

### Prompt Template Versiyonlama (#4)

Prompt'u `app/services/advisor.py` içinden çıkar:

```
app/services/llm/prompts/
  advisor_tr_v1.0.md
  advisor_tr_v1.1.md   # SPK 2026 mevzuat güncellemesi
  advisor_en_v1.0.md   # i18n-002 sonrası
```

`PromptLoader.load("advisor", locale="tr", version="latest")` → versiyon DB'ye yazılır
(`investment_advice.prompt_version`). A/B test: %50 v1.0 + %50 v1.1 user_id hash bucket.

### Cost Monitoring + Budget Alert (#2, #8)

`GET /api/v1/metrics/ai` (`X-Metrics-Token` ile auth, PERF-004 pattern):

```json
{
  "last_7_days": {
    "request_count": 142,
    "cache_hit_rate": 0.84,
    "total_input_tokens": 213450,
    "total_output_tokens": 89234,
    "estimated_cost_usd": 2.31,
    "p95_latency_ms": 4200
  }
}
```

Grafana dashboard (OBS-001 OTel ile entegre). Cache hit oranı <70% → Slack/email alert.
Aylık bütçe hard cap ($10/ay vb.): aşılırsa `/advice/generate` 503 + admin alert.

## SPK + Güvenlik

### Disclaimer Multi-Jurisdiction (#5)

Şu anda TR SPK only. i18n-002 EN çevirisi tamamlanınca:

| Locale | Jurisdiction | Disclaimer ekleri |
|--------|--------------|-------------------|
| `tr` | SPK m.40 (Türkiye) | Mevcut `_REQUIRED_DISCLAIMER` |
| `en-EU` | MiFID II Art. 24 | "Complex product" risk warning + appropriateness test reminder |
| `en-US` | SEC Rule 17a-3 | "Not a registered investment adviser" + state-specific (CA, NY ekstra) |

`user.country` (ISO 3166-1) + `user.locale` → disclaimer template seçimi. KVKK m.9 onay
mekanizması da jurisdiction-aware olmalı (GDPR Art. 9 farklı consent metni).

### Prompt Injection Koruma (#3)

User prompt'a giren tüm string'ler için sanitization:

```python
def _sanitize_user_input(value: str) -> str:
    # Newline kaçışı (injection için en yaygın)
    value = value.replace("\n", " ").replace("\r", " ")
    # Markdown code fence kaçışı
    value = value.replace("```", "")
    # System prompt override pattern blacklist
    for pattern in ("ignore previous", "yukarıdaki talimatları", "system:", "###"):
        if pattern in value.lower():
            raise HTTPException(400, "Geçersiz portföy verisi")
    return value[:200]  # max length
```

Ek savunma: `messages` API'de `system` ayrı parametre olduğu için user content **technically**
override edemez, ama LLM zayıf yorum yaparsa risk hala var. Anthropic'in `prompt_caching`
guide'ında "tool_use ile structured output" daha sağlam — JSON schema constraint ile LLM
serbest metin üretemez.

### Jailbreak Prevention

Çıktı denetim katmanı (`_ensure_disclaimer` zaten var, **eksik olanlar**):

1. **Yasaklı kelime taraması:** "kesinlikle alın", "garanti getiri", "X coin yükselecek"
   regex listesi → çıktı içeriyorsa retry (farklı seed) + ikinci fail'de generic boilerplate.
2. **Imperatif kip detection:** "...alın", "...satın", "...yatırım yapın" suffix kontrolü
   (TR'de fiil sonları → spaCy Turkish model overkill; regex `\b(alın|satın|yatırım yapın)\b`).
3. **Sayısal vaat detection:** `%\d+ kazanç`, `\d+ TL getiri garanti` → retry.

Bu üç katman + post-processing `_ensure_disclaimer` = 4 savunma katmanı. SPK denetiminde
"4 katmanlı çıktı kontrolü" yazılı dokümante edilmeli (`docs/05-ai-ve-finans.md`).

---

**Sonuç:** AI hattı FAZ H ile olgunlaşmış (timeout + cache + audit + KVKK rıza + kredi
düşümü atomik). Kritik eksiklikler: **(1)** provider portability (tek Anthropic SPOF),
**(2)** cache hit metrik dashboard yok, **(3)** prompt injection sanitization, **(4)**
multi-jurisdiction disclaimer. Bunlar Faz 4'te paralel ele alınabilir.
