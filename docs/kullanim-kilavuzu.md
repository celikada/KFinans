# KFinans Kullanım Kılavuzu

> Kişisel yatırım portföyünüzü ve kişisel finansınızı tek ekranda toplayan uygulamanın
> son-kullanıcı rehberi. Uygulama adresi: **https://kfinans.app**

İçindekiler:

1. [KFinans Nedir?](#1-kfinans-nedir)
2. [Başlarken](#2-başlarken)
3. [Ana Ekran (Pano)](#3-ana-ekran-pano)
4. [Yatırım Modülleri](#4-yatırım-modülleri)
5. [Finans Modülleri](#5-finans-modülleri)
6. [Bütçe](#6-bütçe)
7. [Para Birimi & Görüntüleme](#7-para-birimi--görüntüleme)
8. [İçe / Dışa Aktarma ve Raporlar](#8-içe--dışa-aktarma-ve-raporlar)
9. [Geçmiş ve Anlık Görüntü (Snapshot)](#9-geçmiş-ve-anlık-görüntü-snapshot)
10. [AI Yatırım Tavsiyesi](#10-ai-yatırım-tavsiyesi)
11. [Bildirimler](#11-bildirimler)
12. [Mobil Uygulama (PWA)](#12-mobil-uygulama-pwa)
13. [Güvenlik ve Gizlilik](#13-güvenlik-ve-gizlilik)
14. [İpuçları ve Sık Sorulan Sorular](#14-i̇puçları-ve-sık-sorulan-sorular)

---

## 1. KFinans Nedir?

KFinans; kripto borsalarınızı, blockchain cüzdanlarınızı, TEFAS yatırım fonlarınızı,
hisse senetlerinizi, kıymetli madenlerinizi (altın/gümüş), BES birikimlerinizi ve
kişisel gelir/gider/bütçe takibinizi **tek bir panoda** toplayan kişisel finans
uygulamasıdır. Tüm değerler anlık kurlarla TL'ye normalize edilir; haftalık değişimler
izlenir, dilerseniz yapay zekâ destekli yatırım tavsiyesi alabilirsiniz.

**Öne çıkanlar:**
- 10 blockchain zinciri + Binance/iCrypex borsa entegrasyonu + manuel kayıt
- TEFAS, hisse, altın/gümüş, BES
- Gelir/gider, planlı ödeme, kredi kartı, abonelik, bütçe ve nakit akışı projeksiyonu
- 6 para birimi (TRY/USD/EUR/GBP/CHF/JPY), seçilebilen görüntüleme para birimi
- PDF/Excel rapor, haftalık snapshot, mobil uygulama (PWA), Türkçe/İngilizce

---

## 2. Başlarken

### 2.1 Kayıt ve Giriş
1. **https://kfinans.app** adresine gidin → **Kayıt Ol**.
2. E-posta + güçlü bir şifre girin (şifre gücü canlı ölçülür; bilinen sızmış şifreler
   reddedilir). Yaş onayı ve sözleşme kabulü zorunludur.
3. E-postanıza gelen **doğrulama bağlantısına** tıklayın.
4. **Giriş Yap** ile e-posta + şifrenizle oturum açın.

### 2.2 İki Adımlı Doğrulama (MFA — önerilir)
Hesabınızı korumak için **Ayarlar → Güvenlik**'ten iki adımlı doğrulamayı açın:
1. **Kur** → ekrandaki QR kodu Google Authenticator / Authy / 1Password ile okutun.
2. Uygulamadaki 6 haneli kodu girip **Etkinleştir** deyin.
3. Size verilen **10 kurtarma kodunu** güvenli bir yere kaydedin (telefonunuzu
   kaybederseniz bunlarla giriş yaparsınız — her kod tek kullanımlıktır).
4. Bundan sonra her girişte şifre + 6 haneli kod istenir.

### 2.3 Dil ve İlk Ayarlar
- Sağ üstteki **dil anahtarı** ile Türkçe/İngilizce geçiş yapabilirsiniz.
- **Ayarlar**'dan **varsayılan para biriminizi** seçin (hem giriş hem görüntüleme
  para biriminiz olur — bkz. [Bölüm 7](#7-para-birimi--görüntüleme)).

---

## 3. Ana Ekran (Pano)

Pano, portföyünüzün ve finansınızın özetidir. İki ana grup vardır:

- **Yatırım kartları:** Cüzdanlar, Kripto, Manuel Kripto, TEFAS, Hisse, Emtia, BES.
- **Finans kartları:** Kredi Kartları, Gelirler, Giderler, Bütçe, Hedef, Nakit, Abonelikler.

En üstte **Toplam Portföy** değeri, altında her kartın toplamı + en büyük 3 kalemi görünür.
Bir karta tıklayınca o modülün detay sayfası açılır.

### 3.1 Canlı Veri, Yenileme ve "Son Güncelleme"
Yatırım verileri (cüzdan/kripto/TEFAS/hisse/emtia) dış kaynaklardan geldiği için
arka planda hesaplanıp önbelleğe alınır. Üstteki çubukta **"Son güncelleme: X dk önce"**
yazar.
- **Yenile** butonu: tüm portföyü yeniden hesaplatır.
- **Tek-kart yenileme (🔄):** Her yatırım kartının **sağ üst köşesindeki yenileme
  ikonu**, yalnız o kartı yeniden çeker — tüm sayfayı yenilemeden tek bir kaynağı
  tazelemek için idealdir (ör. TEFAS geçici hata verdiyse yalnız TEFAS kartını yenileyin).
  İkona bastığınızda ikon döner; güncel değer gelince kart kendiliğinden tazelenir.

### 3.2 Uyarılar (⚠)
Bir veri kaynağı geçici erişilemezse kart boş kalmaz; o kartın **sağ üstünde, yenile
ikonunun yanında ⚠ işareti** belirir. Üzerine gelince (veya tıklayınca) uyarının
ayrıntısını okursunuz — ör. *"XAGX: fiyatı alınamadı"*, *"TEFAS fiyatı şu an alınamıyor"*,
*"altın anlık fiyatı alınamadı"*. Diğer kartlar bu durumdan etkilenmez.

> Çoğu uyarı **geçici**dir (dış servisin o anki hız sınırı / erişim boşluğu). Genellikle
> kartı **🔄 ile yenilediğinizde** değer güncellenir ve ⚠ kaybolur.

---

## 4. Yatırım Modülleri

### 4.1 Kripto Borsalar (Binance / iCrypex)
**Ayarlar → Entegrasyonlar** (veya Kripto sayfası) üzerinden borsa **API anahtarınızı**
ekleyin. Anahtarlar şifrelenerek saklanır; yalnızca **okuma** yetkisi yeterlidir
(işlem yetkisi vermeyin). Bakiyeleriniz otomatik çekilir ve anlık fiyatla değerlenir.

### 4.2 Manuel Kripto (API'siz borsalar)
BinanceTR, BTCTurk, Paribu, Bybit, KuCoin gibi API erişimi olmayan borsalardaki
varlıklarınızı **Manuel Kripto** sayfasından elle girin. Her kayıt için fiyat kaynağı:
- **Otomatik:** Binance/CoinGecko'dan anlık fiyat (varsayılan).
- **Manuel:** Birim fiyatı kendiniz girersiniz.
- **Bağlı:** Mevcut bir varlığa bağlarsınız (ör. gram altın, ETH).

Excel ile toplu içe/dışa aktarım desteklenir.

### 4.3 Blockchain Cüzdanları
**Cüzdanlar** sayfasından genel adresinizi (veya Bitcoin için xpub) ekleyin —
desteklenen 10 zincir: Bitcoin, Ethereum, Sonic, Avalanche C/P, Solana, Cardano,
Algorand, Polkadot, Litecoin. Likit bakiye, **stake** edilen miktar ve **bekleyen
ödüller** ayrı ayrı gösterilip toplam değere dahil edilir. Adresleriniz şifreli saklanır
ve ekranda maskelenir (yalnız ilk/son karakterler görünür).

> Yalnızca **genel (public) adres / xpub** girin; özel anahtarınızı (private key)
> **asla** hiçbir yere girmeyin.

### 4.4 TEFAS Yatırım Fonları
**TEFAS** sayfasından fonlarınızı **fon kodu + adet** olarak girin. İsterseniz
**ortalama maliyet** girerek kâr/zarar görebilirsiniz. Aynı fonu farklı aracı
kurumlardan tutuyorsanız **aracı kurum (dağıtıcı)** alanıyla ayrı satır izleyebilirsiniz.
- **MKK e-Yatırımcı Excel** dosyanızı yükleyerek fonlarınızı toplu ekleyebilirsiniz.
- Bir fon TEFAS'ta o an fiyatlanamıyorsa (geçici değerleme boşluğu) o fon listede
  **"⚠ fiyat yok"** rozetiyle kalır; **diğer fonlarınız normal görünür** (tek fon
  yüzünden kart boşalmaz).

### 4.5 Hisse Senetleri
Hisse kodu + adet girin (BIST kodları otomatik tanınır). Fiyatlar Yahoo Finance'tan
gelir; anlık fiyat alınamazsa son kapanış kullanılır ve "stale" uyarısı gösterilir.
MKK Excel ile toplu import desteklenir.

### 4.6 Emtia (Altın / Gümüş)
Sahip olduğunuz gram altın/gümüşü girin; TCMB ve piyasa kurlarıyla TL değeri hesaplanır.

### 4.7 BES (Bireysel Emeklilik)
**BES** sayfasında her sözleşme için 4 tutar girilir: **yatırılan ana para**, **getirisi**,
**devlet katkısı** ve **devlet katkısı getirisi**. Excel ile içe/dışa aktarım vardır.

> **İpucu — Toplama girişi:** Tutar alanlarına birden çok değeri **toplayarak**
> girebilirsiniz. Örneğin `100+150+200+100` yazarsanız kayıtta otomatik **550** olarak
> toplanır; yazarken altında canlı `= 550 ₺` ipucu görünür. Aylık ödemelerinizi elde
> toplamadan girmek için kullanışlıdır.

---

## 5. Finans Modülleri

### 5.1 Gelirler
**Gelirler** sayfasında iki tür kayıt vardır:
- **Gerçekleşen gelirler:** Tek seferlik kayıtlar (kendi para biriminde; işlem-anı
  kuruyla TL'ye sabitlenir).
- **Periyodik gelirler:** Maaş, kira, temettü gibi düzenli beklentiler (aylık/3 aylık/
  yıllık vb.). Bunlar **tahmin**dir; "Bu ayı gerçekleştir" ile gerçek gelire dönüştürülür.

### 5.2 Giderler
Harcamalarınızı kategori + tutar + tarihle girin. Kredi kartından yapılıp **ödenmiş**
işaretlenen harcamalar, kart borcuyla **çift sayılmamak** için toplamdan otomatik hariç
tutulur (listede `💳 kart` / `✓ ödendi` rozetleriyle belirtilir).
Giderler sayfasında ayrıca **Periyodik** ve **Abonelikler** sekmeleri bulunur.

### 5.3 Planlı / Periyodik Ödemeler
Kira, aidat, sigorta gibi düzenli giderleri **planlı ödeme** olarak tanımlayın
(aylık/3 aylık/6 aylık/yıllık). Tarihi gelen dönemleri "**Gerçekleşti**" ya da
"**Gerçekleşmeyecek**" olarak işaretleyebilir, yanlış işaretlediğinizi **Dönemler**
ekranından geri alabilirsiniz. Girişte, tarihi geçmiş ama işaretlenmemiş dönemler için
bir **hatırlatma penceresi** açılır.

### 5.4 Nakit
Elinizdeki / banka hesabınızdaki nakdi takip edin.

### 5.5 Nakit Akışı
**Nakit Akışı** sayfası 12 aylık bir **projeksiyon** sunar: gerçekleşen + beklenen
gelir/gider, kredi kartı ekstreleri ve taksitler dahil. Yıl seçici + grafik (gelir-gider
çubukları + net çizgi) + aylık tablo bulunur. Bir aya tıklayınca o ayın **kalem dökümünü**
görürsünüz. Raporu **PDF ve Excel** olarak indirebilirsiniz.

### 5.6 Kredi Kartları
Her kartı (banka, son 4 hane, limit, kesim/son ödeme günü) tanımlayın. Sonra:
- **Ekstre ekleyin** veya **ekstre PDF'inizi yükleyin** — 8 banka desteklenir
  (Ziraat, Enpara, Yapı Kredi, VakıfBank, QNB, Garanti, İş Bankası, Akbank/Axess).
  Sistem kart/ekstre/taksitleri otomatik doldurur; siz onaylamadan kaydedilmez.
- **Taksitler** gelecek aylara yansıtılır (çift sayım önlenir).
- **Kısmi ödeme:** Ekstreyi tam veya kısmi ödendi işaretleyebilirsiniz; kalan tutar
  sonraki döneme taşınır.
- **Hatırlatma:** Girişte, son ödeme tarihi yaklaşan/geçen ekstreler ve ekstresi eksik
  kartlar için uyarı penceresi açılır; oradan "Ödendi" işaretleyebilir veya Google
  Takvim'e ekleyebilirsiniz.

> Tanınmayan/biçimi değişmiş bir ekstre asla "tahmini" doldurulmaz — sistem uyarır,
> elle girersiniz.

### 5.7 Abonelikler (Fatura/Utility Takibi)
Elektrik, doğalgaz, internet, telefon faturalarınızı **abone numarasıyla** takip edin
(Giderler → Abonelikler sekmesi). Her abonelik 3 durumludur:
1. **Bütçe** — fatura çıkmadan aylık tahmini değer.
2. **Fatura geldi** — gerçek tutar + son ödeme tarihi girilir.
3. **Ödendi** — gerçek gider kaydı oluşur (ödeme şeklini seçersiniz: nakit/kredi kartı).

**Fatura PDF'i yükleyerek** (ESGAZ, Vodafone, TTNET ve görüntü-PDF'ler için OCR ile
Osmangazi/Zorlu Elektrik) tutar/tarihleri otomatik doldurabilirsiniz. Son ödeme yaklaşan
faturalar için hatırlatma gelir.

### 5.8 Hedef
Bir finansal hedef (ör. belirli bir toplam servet) tanımlayın; ilerlemenizi yüzde olarak
ve pasif gelir katkısıyla birlikte izleyin.

---

## 6. Bütçe

**Bütçe** sayfası, gerçek harcama verinizin üstüne oturan hibrit bir planlama aracıdır
ve 4 sekmeden oluşur:

- **Aylık (Kovalar):** Harcama kategorileriniz üç "kovaya" ayrılır — **Temel İhtiyaçlar /
  Keyif / Gelecek (Birikim)** — her kovanın hedef oranı (varsayılan %50/%30/%20) ve
  bütçe-gerçekleşen karşılaştırması gösterilir. Aylık-olmayan giderler (kasko, sigorta,
  MTV gibi yıllık) **aylık eşdeğer "⚖️ ağırlıklı"** olarak dağıtılır. Altta o ay için
  **Analiz / Aksiyon Planı** notu yazabilirsiniz.
- **Yıllık Izgara:** 12 ay × kategori tablosunda her hücreye planlanan tutarı girersiniz;
  altında o ayki gerçekleşen görünür. Satır/sütun/yıl toplamları otomatik.
- **Projeksiyon:** 12 aylık gelir/gider/net + kümülatif yıl-sonu bakiye grafiği.
- **Borç / Alacak:** Kredi kartı dışı kişisel borç ve alacaklarınızı (kişi/kurum, tutar,
  vade) takip edin; kapatıldığında "Kapat" ile işaretleyin. Özet: toplam borç/alacak/net.

⚙️ **Kova Ayarları** ile hedef oranları ve kategori→kova eşlemesini değiştirebilirsiniz.
**Kategori limitleri** (klasik basit bütçe) bölümü, pano ve Giderler'deki "X kategori
aşıldı" uyarılarını besler.

---

## 7. Para Birimi & Görüntüleme

- **6 para birimi:** Her gelir/gider/planlı/bütçe/kredi-kartı kaydını TRY, USD, EUR,
  GBP, CHF veya JPY olarak girebilirsiniz.
- **Görüntüleme para birimi:** Ayarlar'daki tercihiniz hem giriş varsayılanı hem de
  **raporlama birimi**dir. **Toplamlar** seçtiğiniz birime çevrilir; **tek tek satır
  kalemleri kendi para biriminde** kalır (ör. maaşınız TRY, kiranız USD ise her biri
  kendi biriminde, toplam seçili birimde görünür). Para birimini değiştirmek için sayfa
  yenilemeye gerek yoktur.
- **"USD karşılığı göster"** seçeneğini açarsanız toplamların altında yaklaşık USD
  karşılığı gösterilir.

---

## 8. İçe / Dışa Aktarma ve Raporlar

**İçe aktarma:**
- **MKK e-Yatırımcı Excel** → TEFAS fonları + hisse senetleri.
- **Kredi kartı ekstresi (PDF)** → kart/ekstre/taksit (8 banka).
- **Fatura (PDF)** → abonelik faturaları (OCR dahil).
- **Excel** → BES, manuel kripto.

**Raporlar:** Nakit akışı ve snapshot raporları her zaman **hem PDF hem Excel** olarak
indirilebilir (Türkçe karakter desteğiyle). Borsa API anahtarlarınızı şifre doğrulamasıyla
dışa aktarabilirsiniz.

---

## 9. Geçmiş ve Anlık Görüntü (Snapshot)

Sistem her hafta (Pazar gecesi) portföyünüzün bir **anlık görüntüsünü** kaydeder; ayrıca
istediğiniz an manuel snapshot alabilirsiniz. **Geçmiş** sayfasında:
- Haftalık portföy değerinizin değişimini izlersiniz.
- Her snapshot için **📊 Excel** ve **📄 PDF** rapor indirebilirsiniz.
- TL/USD görünüm arasında geçiş yapabilirsiniz.
- Yanlış kaydedilmiş bir snapshot'ı silebilirsiniz.

---

## 10. AI Yatırım Tavsiyesi

Dilerseniz portföy dağılımınıza ve değişimlerinize göre **orta/uzun vadeli yatırım
tavsiyesi** alabilirsiniz (Claude AI ile üretilir).
- İlk kullanımda **veri işleme onayı** (KVKK) vermeniz gerekir.
- Her tavsiye 1 **kredi** harcar; krediniz yoksa önce kredi edinmeniz gerekir.
- Tüm tavsiyeler **yatırım danışmanlığı değildir** uyarısıyla sunulur — kararlar size aittir.

---

## 11. Bildirimler

**Ödeme hatırlatmaları** iki kanaldan gelir (Ayarlar'dan açılır):
- **Web Push:** Tarayıcı/telefon bildirimi (mağazasız). Android Chrome tam destekler;
  iOS'ta yalnızca uygulamayı "Ana ekrana ekle" ile kurduysanız çalışır.
- **E-posta hatırlatma:** Tarayıcıdan bağımsız garanti kanal (opt-in + doğrulanmış
  e-posta gerekir).

Son ödeme tarihi 5 günden yakın kredi kartı ekstreleri ve abonelik faturaları için
hatırlatma gönderilir.

---

## 12. Mobil Uygulama (PWA)

KFinans kurulabilir bir **PWA**'dır (ayrı uygulama mağazası gerekmez):
- **Android (Chrome):** Menü → "Uygulamayı yükle" / "Ana ekrana ekle".
- **iOS (Safari):** Paylaş → "Ana Ekrana Ekle". Push bildirimleri için bu kurulum şarttır.

Kurulduğunda tam ekran, uygulama gibi açılır. Bakiye/portföy verileri güvenlik gereği
çevrimdışı **önbelleğe alınmaz** (her zaman güncel veri gösterilir).

---

## 13. Güvenlik ve Gizlilik

- **İki adımlı doğrulama (MFA)** ve **güçlü şifre politikası** (sızmış şifre engeli).
- **Hesap kilitleme:** Çok sayıda hatalı giriş denemesi hesabı geçici kilitler.
- **API anahtarları ve cüzdan adresleri şifreli** saklanır; adresler ekranda maskelenir.
- **Oturum güvenliği:** Çıkış yaptığınızda oturumunuz güvenle sonlandırılır; oturum
  jetonları belirli sürede yenilenir.
- **KVKK / hesap silme:** **Ayarlar**'dan hesabınızı silebilirsiniz; verileriniz 30 gün
  sonra kalıcı olarak silinir. Verilerinizi dışa aktarma ve onam yönetimi desteklenir.

> Güvenlik açığı bildirimi için depo kökündeki `SECURITY.md` dosyasına bakın.

---

## 14. İpuçları ve Sık Sorulan Sorular

**TEFAS kartım boş / "fiyat yok" diyor?**
Bir fon TEFAS'ta o an fiyatlanamıyorsa (genelde gün içi değerleme yayınlanmadan önce,
özellikle altın fonlarında) o fon "⚠ fiyat yok" rozetiyle görünür; değerlemesi
yayınlanınca otomatik düzelir. Diğer fonlarınız etkilenmez. Dilerseniz TEFAS kartının
**🔄 yenileme ikonuyla** tek başına tazeleyin.

**Kartta ⚠ işareti var, ne demek?**
O kartın son güncellemesinde bir sorun (ör. bir varlığın fiyatı alınamadı) oluştu.
İkonun üzerine gelin/tıklayın → ayrıntıyı okuyun. Genelde geçicidir; kartı **🔄 ile
yenileyince** düzelir.

**Manuel kripto / bir varlık değeri 0,00 ₺ görünüyor?**
Genellikle fiyat kaynağının (ör. CoinGecko ücretsiz API) o anki **hız sınırı** nedeniyle
son güncellemede fiyat boş dönmüştür ve eski (0) değer önbellekte kalmıştır. İlgili kartı
**🔄 ile yenileyin** — fiyat erişilebilirse değer güncellenir. (Bağlı fiyat kaynağı
gerçekten geçersizse, kaydı düzenleyip doğru kaynağı seçin.)

**Tek bir kartı nasıl yenilerim?**
Yatırım kartının sağ üstündeki **🔄** ikonuna basın — yalnız o kart yeniden çekilir.
İkon dönerken bekleyin; güncel değer gelince kart tazelenir.

**BES'te birden çok ödemeyi nasıl tek seferde girerim?**
Tutar alanına `100+150+200` gibi yazın; kayıtta otomatik toplanır (550).

**Para birimini değiştirince satırlar neden farklı birimde?**
Toplamlar görüntüleme para biriminde, tek tek kalemler kendi giriş birimindedir
(tasarım gereği — her kalemin gerçek para birimi korunur).

**Verilerim ne sıklıkla güncellenir?**
Yatırım verileri arka planda önbelleğe alınır; üstteki çubukta "Son güncelleme" görünür.
Güncel değer için **Yenile** (tümü) veya kart üstündeki **🔄** (tek kart) kullanın.

**Kredi kartı harcamam neden gider toplamına eklenmedi?**
Kredi kartından yapılıp "ödendi" işaretlenen harcamalar, kart borcuyla çift sayılmasın
diye ham gider toplamından hariç tutulur (kart ekstresinde sayılır).

---

*Bu kılavuz uygulamanın güncel sürümüne göre hazırlanmıştır. Sürüm bilgisini Ayarlar
sayfasının altında görebilirsiniz.*
