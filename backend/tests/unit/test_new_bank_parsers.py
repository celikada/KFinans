"""Yapı Kredi + QNB + Garanti BBVA + İş Bankası ekstre parser'ları.

Fixture metinleri gerçek ekstrelerin pdfplumber'ın üreteceği metne yakın
temsilidir. Tarih/sayı biçimi ve taksit deseni bankaya göre değişir:
- Yapı Kredi: TR sayı, Türkçe ay-adı tarih, "X TL'lik işlemin k / n taksidi".
- QNB: EN sayı, sayısal kesim tarihi + Türkçe ay-adı son ödeme, satır-sonu "k/n".
- Garanti: TR sayı, Türkçe ay-adı tarih, iki-noktasız etiketler.
- İş Bankası: TR sayı, sayısal tarih, "Hesap Özeti Borcu", "k/ntaksidi(toplam)".
"""

from datetime import date
from decimal import Decimal

from app.services.statement_import import detect_parser
from app.services.statement_import._utils import parse_turkish_date, search_labeled_date
from app.services.statement_import.garanti import GarantiParser
from app.services.statement_import.isbank import IsbankParser
from app.services.statement_import.qnb import QnbParser
from app.services.statement_import.vakifbank import VakifBankParser
from app.services.statement_import.yapikredi import YapiKrediParser

# ─── Ortak Türkçe tarih util ──────────────────────────────────────────────────


def test_parse_turkish_date():
    assert parse_turkish_date("5 Haziran 2026") == date(2026, 6, 5)
    assert parse_turkish_date("01 Ocak 2026") == date(2026, 1, 1)
    assert parse_turkish_date("20 Mayıs 2026, Çarşamba") == date(2026, 5, 20)
    assert parse_turkish_date("15 Aralık 2025") == date(2025, 12, 15)


def test_search_labeled_date_skips_next_period():
    text = "Hesap Kesim Tarihi : 09/05/2026\nBir Sonraki Hesap Kesim Tarihi : 09/06/2026"
    assert search_labeled_date(text, "Hesap Kesim Tarihi", turkish=False) == date(2026, 5, 9)


# ─── Yapı Kredi ────────────────────────────────────────────────────────────────

YAPIKREDI_TEXT = """YAPI KREDİ WORLD PLATINUM HESAP ÖZETİ
Sn. EBRU DİNÇER
Son Ödeme Tarihi: 15 Haziran 2026
HESAP BİLGİLERİ
Hesap Kesim Tarihi : 5 Haziran 2026
Son Ödeme Tarihi : 15 Haziran 2026
Dönem Borcu : 2.000,00 TL
Önceki Dönem Hesap Özeti Borcu : 2.000,00 TL
Bir Sonraki Ay Hesap Kesim Tarihi : 5 Temmuz 2026
Bir Sonraki Ay Son Ödeme Tarihi : 16 Temmuz 2026
Müşteri Limiti : 38.700,00 TL
Kart Limiti : 30.000,00 TL
Nakit Çekim Limiti : 7.500,00 TL
Kart Numarası : 5258 64** **** 6593
31 Aralık 2025 OTOMOTIV LASTIKLERITEVZI ISTANBUL TR 2.000,00
12.000,00 TL'lik işlemin 6 / 6 taksidi
www.yapikredi.com.tr www.worldcard.com.tr
"""


def test_detect_yapikredi_wins_over_vakifbank_worldcard():
    # Metinde hem "yapikredi" hem "worldcard" geçer; Yapı Kredi öncelikli.
    p = detect_parser(YAPIKREDI_TEXT)
    assert isinstance(p, YapiKrediParser)
    assert not isinstance(p, VakifBankParser)


def test_yapikredi_fields():
    p = YapiKrediParser().parse(YAPIKREDI_TEXT)
    assert p.bank_name == "Yapı Kredi"
    assert p.last_4 == "6593"
    assert p.credit_limit == Decimal("30000.00")  # "Müşteri Limiti" değil
    assert p.statement_date == date(2026, 6, 5)
    assert p.due_date == date(2026, 6, 15)  # "Bir Sonraki Ay" tuzağına düşmez
    assert p.statement_amount == Decimal("2000.00")  # "Önceki Dönem ... Borcu" değil
    assert p.installments == []  # 6/6 son dilim → gelecek taksit yok


def test_yapikredi_active_installment():
    text = YAPIKREDI_TEXT.replace("6 / 6 taksidi", "3 / 6 taksidi")
    p = YapiKrediParser().parse(text)
    assert len(p.installments) == 1
    inst = p.installments[0]
    assert inst.installments_paid == 3
    assert inst.installments_total == 6
    assert inst.total_amount == Decimal("12000.00")
    assert inst.monthly_amount == Decimal("2000.00")
    assert "OTOMOTIV" in inst.description


def test_yapikredi_missing_field_raises():
    import pytest

    with pytest.raises(ValueError):
        YapiKrediParser().parse("yapikredi ama alan yok")


# ─── QNB ───────────────────────────────────────────────────────────────────────

QNB_TEXT = """QNB Fix
Kredi Kartı Numarası : 5311 57** **** 8936
Hesap Kesim Tarihi : 09/05/2026
Dönem Borcu : 85,275.04 TL
Asgari Ödeme Tutarı : 34,111.00 TL
Kredi Kartı Limiti : 315,000.00 TL
Toplam Kredi Kartı Limiti : 357,650.00 TL
Son Ödeme Tarihi: 20 Mayıs 2026, Çarşamba
26/04/2026 SPORLINE OUTLET 1,043.69 1/3 7,457
10/02/2026 TRENDYOL.COM 431.90 3/3
16/03/2026 TRENDYOL.COM 439.95 2/3
15/04/2026 20260302TRENDYOL.COM -1,429.95 3/3
04/04/2026 SAYGI GIYIM SANAYI V 767.95 2/2
www.qnbcard.com.tr
"""


def test_detect_qnb():
    assert isinstance(detect_parser(QNB_TEXT), QnbParser)


def test_qnb_fields():
    p = QnbParser().parse(QNB_TEXT)
    assert p.bank_name == "QNB"
    assert p.last_4 == "8936"
    assert p.credit_limit == Decimal("315000.00")  # "Toplam" değil
    assert p.statement_date == date(2026, 5, 9)
    assert p.due_date == date(2026, 5, 20)  # Türkçe ay-adı son ödeme
    assert p.statement_amount == Decimal("85275.04")  # EN format


def test_qnb_installments_skip_negative_and_last():
    p = QnbParser().parse(QNB_TEXT)
    # 1/3 ve 2/3 kalır; 3/3 + 2/2 (son dilim) + -1,429.95 (iade) atlanır.
    assert len(p.installments) == 2
    paids = sorted(i.installments_paid for i in p.installments)
    assert paids == [1, 2]
    sporline = next(i for i in p.installments if "SPORLINE" in i.description)
    assert sporline.monthly_amount == Decimal("1043.69")
    assert sporline.installments_total == 3
    assert sporline.total_amount == Decimal("3131.07")


# ─── Garanti BBVA (Bonus) ──────────────────────────────────────────────────────

GARANTI_TEXT = """Bonus Bilgileriniz
Müşteri Numarası 9676451
Müşteri Limiti 20.000,00 TL
Kart Numarası 9792 05** **** 4010
Kart Limiti 20.000,00 TL
Nakit Avans Limiti 5.000,00 TL
Hesap Kesim Tarihi 01 Haziran 2026
Son Ödeme Tarihi 11 Haziran 2026
Dönem Borcunuz 17.176,69 TL
Min. Ödeme Tutarı 3.436,00 TL
20 Mayıs 2026 3129 İZMİR DİKİLİ CARREFO 0,06 187,65
T. Garanti Bankası A.Ş. www.garantibbva.com.tr
Bir sonraki hesap kesiminiz 03 Temmuz 2026 ve son ödemeniz 13 Temmuz 2026
"""


def test_detect_garanti():
    assert isinstance(detect_parser(GARANTI_TEXT), GarantiParser)


def test_garanti_fields():
    p = GarantiParser().parse(GARANTI_TEXT)
    assert p.bank_name == "Garanti BBVA"
    assert p.last_4 == "4010"
    assert p.credit_limit == Decimal("20000.00")  # Kart Limiti (Müşteri/Avans değil)
    assert p.statement_date == date(2026, 6, 1)  # iki-noktasız etiket
    assert p.due_date == date(2026, 6, 11)  # "son ödemeniz 13 Temmuz" tuzağına düşmez
    assert p.statement_amount == Decimal("17176.69")
    assert p.installments == []  # örnekte taksit yok
    assert any("taksit" in w.lower() for w in p.warnings)


# ─── İş Bankası (Maximum) ──────────────────────────────────────────────────────

ISBANK_TEXT = """MAXIMUM VISA Klasik Hesap Özetiniz
Hesap Kesim Tarihi: 05.06.2026
Son Ödeme Tarihi: 15.06.2026
Hesap Özeti Borcu: 14.589,28 TL
Bir Sonraki Hesap Kesim Tarihi: 05.07.2026
Bir Sonraki Son Ödeme Tarihi: 16.07.2026
Kart Numarası: 4543********8014
Müşteri Limiti: 195.090,00 TL
Toplam Kart Limiti: 195.090,00 TL
Toplam Kullanılabilir Kart Limiti: 180.500,72 TL
07/05/2026 WWW.TRENDYOL.COMISTANBULTR 1.537,86 3/3taksidi(4.613,60)
07/05/2026 İADE/WWW.TRENDYOL.COM -178,50 3/3taksidi(535,52)
isbank.com.tr maximum.com.tr
"""


def test_detect_isbank():
    assert isinstance(detect_parser(ISBANK_TEXT), IsbankParser)


def test_isbank_fields():
    p = IsbankParser().parse(ISBANK_TEXT)
    assert p.bank_name == "İş Bankası"
    assert p.last_4 == "8014"
    assert p.credit_limit == Decimal("195090.00")  # Toplam Kart Limiti (Kullanılabilir değil)
    assert p.statement_date == date(2026, 6, 5)
    assert p.due_date == date(2026, 6, 15)  # "Bir Sonraki" tuzağına düşmez
    assert p.statement_amount == Decimal("14589.28")  # "Hesap Özeti Borcu"
    assert p.installments == []  # 3/3 son dilim + iade → boş


def test_isbank_active_installment():
    text = ISBANK_TEXT.replace("1.537,86 3/3taksidi(4.613,60)", "1.537,86 1/3taksidi(4.613,60)")
    p = IsbankParser().parse(text)
    assert len(p.installments) == 1
    inst = p.installments[0]
    assert inst.installments_paid == 1
    assert inst.installments_total == 3
    assert inst.monthly_amount == Decimal("1537.86")
    assert inst.total_amount == Decimal("4613.60")


# ─── Çapraz: yeni parser'lar eski banka fixture'larını YANLIŞ tanımamalı ───────


def test_new_parsers_do_not_match_each_other():
    # Her fixture yalnız kendi parser'ına çözülmeli.
    assert isinstance(detect_parser(QNB_TEXT), QnbParser)
    assert isinstance(detect_parser(GARANTI_TEXT), GarantiParser)
    assert isinstance(detect_parser(ISBANK_TEXT), IsbankParser)
    assert isinstance(detect_parser(YAPIKREDI_TEXT), YapiKrediParser)


# ─── Glyph-düşmesi (Türkçe karakter kaybı) regresyonu ─────────────────────────
# Bazı banka PDF'lerinin metin katmanı Türkçe-özel harfleri tamamen düşürür
# ("Son Ödeme"→"Son deme", "Numarası"→"Numaras", "Mayıs"→"Mays"). Zorunlu
# alanlar (son ödeme tarihi + dönem borcu) yine de okunabilmeli.
_TR_SPECIAL = "çÇğĞıİöÖşŞüÜ"


def _strip_tr(s: str) -> str:
    return s.translate({ord(c): None for c in _TR_SPECIAL})


def _cid_tr(s: str) -> str:
    """pdfplumber davranışını taklit: her Türkçe-özel harf → "(cid:N)" token."""
    return "".join(f"(cid:{ord(c) % 250})" if c in _TR_SPECIAL else c for c in s)


def test_all_banks_pdfplumber_cid_tokens():
    """pdfplumber Türkçe harfi (cid:N) token'ına çevirdiğinde de zorunlu alanlar
    okunmalı — ay-adlı tarih (Mayıs→May(cid:N)s) dahil (asıl prod bug'ı)."""
    g = GarantiParser().parse(_cid_tr(GARANTI_TEXT))
    assert g.due_date == date(2026, 6, 11)
    assert g.statement_amount == Decimal("17176.69")
    assert g.last_4 == "4010"

    q = QnbParser().parse(_cid_tr(QNB_TEXT))
    assert q.due_date == date(2026, 5, 20)  # "20 May(cid:N)s 2026" → Mayıs
    assert q.statement_amount == Decimal("85275.04")
    assert q.last_4 == "8936"

    y = YapiKrediParser().parse(_cid_tr(YAPIKREDI_TEXT))
    assert y.due_date == date(2026, 6, 15)
    assert y.statement_amount == Decimal("2000.00")
    assert y.last_4 == "6593"

    i = IsbankParser().parse(_cid_tr(ISBANK_TEXT))
    assert i.due_date == date(2026, 6, 15)
    assert i.statement_amount == Decimal("14589.28")
    assert i.last_4 == "8014"


def test_yapikredi_stripped_glyphs():
    p = YapiKrediParser().parse(_strip_tr(YAPIKREDI_TEXT))
    assert p.due_date == date(2026, 6, 15)  # "Bir Sonraki Ay" tuzağına düşmez
    assert p.statement_amount == Decimal("2000.00")  # "Önceki Dönem" değil
    assert p.last_4 == "6593"


def test_qnb_stripped_glyphs():
    # "20 Mayıs 2026" → "20 Mays 2026" (ı düşmüş ay adı da çözülmeli).
    p = QnbParser().parse(_strip_tr(QNB_TEXT))
    assert p.due_date == date(2026, 5, 20)
    assert p.statement_amount == Decimal("85275.04")
    assert p.last_4 == "8936"
    assert p.credit_limit == Decimal("315000.00")  # "Toplam" tuzağına düşmez


def test_garanti_stripped_glyphs():
    p = GarantiParser().parse(_strip_tr(GARANTI_TEXT))
    assert p.due_date == date(2026, 6, 11)  # "son ödemeniz 13 Temmuz" tuzağına düşmez
    assert p.statement_amount == Decimal("17176.69")
    assert p.last_4 == "4010"


def test_isbank_stripped_glyphs():
    # "Hesap Özeti Borcu" → "Hesap zeti Borcu" (Ö düşmüş) yine okunmalı.
    p = IsbankParser().parse(_strip_tr(ISBANK_TEXT))
    assert p.due_date == date(2026, 6, 15)
    assert p.statement_amount == Decimal("14589.28")
    assert p.last_4 == "8014"
