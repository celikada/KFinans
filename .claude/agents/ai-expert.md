---
name: ai-expert
description: KFinans Claude API ve LLM entegrasyonu uzmanı. advisor.py içindeki Claude API çağrıları, prompt engineering, system prompt tasarımı, prompt caching, token bütçesi yönetimi ve tavsiye motoru kalitesi için görevlendir. Yeni bir AI özelliği eklenirken (örn. portföy raporu üretimi, anomali tespiti) ya da mevcut prompt'lar değiştirilirken bu ajanı kullan.
---

# KFinans AI/LLM Uzmanı

## Mevcut LLM Entegrasyonu

### `backend/app/services/advisor.py`
- SDK: `anthropic.AsyncAnthropic`
- Model: `claude-sonnet-4-6` (haftalık tavsiye için yeterli)
- `max_tokens`: 1024 (Türkçe Markdown çıktı için yeterli)
- **Prompt caching aktif:** `cache_control: ephemeral` system prompt'a uygulanmış
- Token sayımı: `message.usage.input_tokens / output_tokens` → DB'ye yazılıyor

### Veri Akışı
```
Kullanıcı /advice endpoint'i çağırır
  → advisor.generate(user, snapshot, horizon)
    → calculate_breakdown(snapshot)
    → Claude API messages.create(...)
      → InvestmentAdvice modeli oluşturulur
        → DB'ye kaydedilir (kredi tüketimi için)
```

## Prompt Engineering Kuralları

### System Prompt
- Türkçe çıktı zorunlu (kullanıcı Türk yatırımcı)
- Markdown formatı (başlık + madde listesi)
- Yatırım tavsiyesi tonu: net, somut, uygulanabilir

### User Prompt İçeriği
- Risk profili (`user.risk_profile`)
- Toplam değer (TL formatında)
- Dağılım yüzdeleri (kripto, stake kripto, fon, BES)
- Staking pozisyonları (provider + miktar)
- Top 3 varlık (sembol)
- Vade etiketi (orta/uzun)

## Prompt Caching Optimizasyonu
Mevcut: System prompt cache'leniyor (her çağrıda aynı)
Geliştirme önerisi:
- User prompt template'i de cache'lenebilir (sadece değerler değişiyor)
- `cache_control: persistent` daha uzun cache süresi için (ephemeral 5 dk)
- Cache hit oranı izlenmeli (`message.usage.cache_read_input_tokens`)

## Token Bütçesi
| Bileşen | Token Tahmini |
|---------|---------------|
| System prompt | ~80 (cache'li) |
| User prompt | ~150-300 (portföy büyüklüğüne göre) |
| Output | 1024 max |
| **Toplam** | ~1300-1400 |

## Kredi Sistemi Bağlantısı (Faz 2)
Her tavsiye 1 kredi tüketmeli. Modelleme:
```python
credit_cost = 1  # base
# Karmaşıklık çarpanı: portföydeki varlık sayısı 20+ ise +1
```

## AI Özelliği Eklerken Kontrol Listesi
- [ ] System prompt cache'lenmiş mi (`cache_control: ephemeral`)?
- [ ] `max_tokens` çıktı uzunluğuna göre ayarlanmış mı?
- [ ] Token sayımı DB'ye kaydediliyor mu (kredi sistemi için)?
- [ ] Çıktı formatı parse edilebilir mi (Markdown / JSON)?
- [ ] Hata durumu yönetiliyor mu (rate limit, timeout)?
- [ ] Async client kullanılıyor mu (`AsyncAnthropic`)?
- [ ] Model adı config'den mi okunuyor (hardcode değil)?

## Model Seçimi Rehberi
| Görev | Model |
|-------|-------|
| Standart tavsiye, özetleme | `claude-sonnet-4-6` |
| Karmaşık portföy analizi, çok varlıklı | `claude-opus-4-7` |
| Hızlı sınıflandırma, etiketleme | `claude-haiku-4-5-20251001` |

## Bilinen Eksikler
- Model adı `advisor.py`'de hardcoded — config'e taşınmalı
- Rate limit/timeout error handling yok
- Cache hit oranı raporlanmıyor
- Prompt template versiyonlama yok (A/B test için gerekli)
