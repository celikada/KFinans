import { LegalLayout, LegalSection } from "../_components/LegalLayout";

export const metadata = { title: "KVKK Aydınlatma Metni — KFinans" };

export default function KvkkPage() {
  return (
    <LegalLayout title="KVKK Aydınlatma Metni" lastUpdated="2026-05-02">
      <p className="text-sm">
        6698 sayılı Kişisel Verilerin Korunması Kanunu (&quot;KVKK&quot;) uyarınca, KFinans
        kullanıcılarına ait kişisel verilerin işlenmesine ilişkin aşağıdaki bilgilendirme yapılır.
      </p>

      <LegalSection title="1. Veri Sorumlusu">
        <p>
          <strong>Mayotek</strong> (&quot;KFinans&quot; uygulamasının operatörü), KVKK kapsamında
          veri sorumlusu sıfatıyla hareket eder.
        </p>
        <ul className="list-disc pl-5">
          <li>Ticari ad: [TİCARİ ÜNVAN]</li>
          <li>İletişim e-postası: <a href="mailto:kvkk@kfinans.app" className="text-blue-600">kvkk@kfinans.app</a></li>
          <li>KEP adresi: [KEP_ADRESI]</li>
          <li>Adres: [TEBLİGAT_ADRESİ]</li>
        </ul>
      </LegalSection>

      <LegalSection title="2. İşlenen Kişisel Veriler">
        <p>Hesap oluşturma ve hizmet sunumu için aşağıdaki veriler işlenir:</p>
        <ul className="list-disc pl-5">
          <li><strong>Kimlik:</strong> e-posta adresi, şifre (bcrypt hash), risk profili</li>
          <li><strong>Finansal:</strong> şifrelenmiş borsa API anahtarları (Fernet), kayıtlı
            blockchain cüzdan adresleri, TEFAS/hisse/BES holdingleri, haftalık portföy snapshot&apos;ları</li>
          <li><strong>İşlem:</strong> giriş kayıtları, IP adresi, kullanıcı ajanı (User-Agent),
            uygulama içi etkinlik logları</li>
          <li><strong>Türev veri:</strong> AI tavsiye motoru tarafından üretilen içerikler</li>
        </ul>
        <p>Özel nitelikli kişisel veri (sağlık, biyometrik vb.) işlenmez.</p>
      </LegalSection>

      <LegalSection title="3. İşleme Amaçları ve Yasal Zemin">
        <ul className="list-disc pl-5">
          <li>Hesap oluşturma, kimlik doğrulama, e-posta doğrulama — <strong>sözleşme ifası</strong> (KVKK m.5/2-c)</li>
          <li>Portföy verisi toplama, snapshot oluşturma ve görüntüleme — <strong>sözleşme ifası</strong> (m.5/2-c)</li>
          <li>Borsa API anahtarları üzerinden bakiye okuma — <strong>sözleşme ifası</strong> (m.5/2-c); kullanıcı entegrasyonu kendi tercihi ile ekler</li>
          <li>AI tabanlı bilgilendirici içerik üretimi — <strong>sözleşme ifası</strong> (m.5/2-c); bağlayıcı yatırım danışmanlığı niteliği taşımaz</li>
          <li>Yurt dışı sağlayıcılara veri aktarımı (Anthropic, Resend — ABD) — <strong>açık rıza</strong> (KVKK m.9), kayıt sırasında ayrı kutuda alınır</li>
          <li>Güvenlik denetimi, sahtecilik önleme, log saklama — <strong>meşru menfaat</strong> (m.5/2-f, 5651 sayılı Kanun)</li>
          <li>Hizmet kalitesini iyileştirme, anonim analitik — <strong>meşru menfaat</strong></li>
        </ul>
      </LegalSection>

      <LegalSection title="4. Aktarım">
        <p>Veriler aşağıdaki üçüncü taraflara, hizmetin gerektirdiği ölçüde aktarılır:</p>
        <ul className="list-disc pl-5">
          <li><strong>Anthropic (ABD):</strong> AI tavsiye üretimi için anonim portföy özeti
            (Claude API). Gerçek e-posta veya kimlik aktarılmaz.</li>
          <li><strong>Resend (ABD):</strong> e-posta doğrulama bağlantısının teslimatı için
            e-posta adresi.</li>
          <li><strong>Bulut altyapı sağlayıcıları (AB/Türkiye):</strong> barındırma için.</li>
          <li><strong>iyzico (Türkiye):</strong> kredi paketi satın alma akışı eklendiğinde
            ödeme işleme için.</li>
        </ul>
        <p className="text-xs text-gray-500">
          Yurt dışına aktarımlar KVKK m.9 kapsamında, Kurul tarafından belirlenen güvenli
          ülkelere veya yeterli koruma taahhüdü içeren standart sözleşme maddeleri ile yapılır.
        </p>
      </LegalSection>

      <LegalSection title="5. Saklama Süreleri">
        <ul className="list-disc pl-5">
          <li>Hesap verisi (e-posta, holdingler, snapshot&apos;lar): hesap silinene + 30 gün cayma süresi</li>
          <li>Şifrelenmiş borsa API anahtarları: hesap silindiğinde derhal SİLİNİR</li>
          <li>Erişim logları, IP, User-Agent: 1-2 yıl (5651 sayılı Kanun yasal arşiv)</li>
          <li>Ödeme/fatura kayıtları: 10 yıl (TTK m.82, VUK m.253)</li>
        </ul>
      </LegalSection>

      <LegalSection title="6. Haklarınız (KVKK m.11)">
        <p>Veri sahibi olarak şu haklara sahipsiniz:</p>
        <ul className="list-disc pl-5">
          <li>Kişisel verilerinizin işlenip işlenmediğini öğrenme</li>
          <li>İşlenmişse buna ilişkin bilgi talep etme</li>
          <li>İşleme amacını ve kullanım uygunluğunu öğrenme</li>
          <li>Yurt içi / yurt dışı aktarım yapılan üçüncü tarafları bilme</li>
          <li>Eksik / yanlış işlenmiş verilerin düzeltilmesini isteme</li>
          <li>KVKK m.7 koşullarında silinmesini veya yok edilmesini isteme</li>
          <li>Otomatik analiz sonucunun aleyhinize bir sonuç doğurmasına itiraz etme</li>
          <li>Hukuka aykırı işleme nedeniyle zarara uğramışsanız tazminat isteme</li>
        </ul>
        <p>
          Başvurularınızı <strong>Veri Sorumlusuna Başvuru Usul ve Esasları Hakkında Tebliğ</strong>{" "}
          uyarınca aşağıdaki kanallardan birini kullanarak iletebilirsiniz:
        </p>
        <ul className="list-disc pl-5">
          <li>
            E-posta (kayıtlı adresinizden):{" "}
            <a href="mailto:kvkk@kfinans.app" className="text-blue-600">kvkk@kfinans.app</a>
          </li>
          <li>
            KEP (Kayıtlı Elektronik Posta) adresinden veri sorumlusu KEP'imize: [KEP_ADRESI]
          </li>
          <li>
            Güvenli elektronik imza ile imzalanmış belge ile e-posta yoluyla
          </li>
          <li>
            Yazılı (ıslak imzalı) başvuru — yukarıdaki tebligat adresine elden veya noter aracılığıyla
          </li>
        </ul>
        <p>
          KVKK m.13 uyarınca başvurunuza en geç 30 gün içinde ücretsiz yanıt verilir
          (işlemin ek maliyet doğurması halinde Kurul tarifesi uygulanır).
        </p>
      </LegalSection>

      <LegalSection title="7. Veri Güvenliği">
        <p>Aşağıdaki teknik ve idari tedbirler alınır:</p>
        <ul className="list-disc pl-5">
          <li>Şifre hash&apos;leme (bcrypt), borsa anahtarları için Fernet simetrik şifreleme</li>
          <li>HTTPS / TLS zorunluluğu, JWT tabanlı kimlik doğrulama, oturum iptal mekanizması (token blacklist)</li>
          <li>Rate limiting (login, register, refresh endpoint&apos;leri için)</li>
          <li>Veri tabanı erişim kontrolü, en az yetki ilkesi</li>
          <li>Düzenli yedekleme ve felaket kurtarma planı</li>
        </ul>
      </LegalSection>

      <LegalSection title="8. Veri İhlali Bildirimi">
        <p>
          KVKK m.12/5 uyarınca olası bir veri ihlali tespit edildiğinde, en kısa sürede ve en
          geç <strong>72 saat</strong> içinde Kişisel Verileri Koruma Kurulu&apos;na bildirim
          yapılır. Etkilenen veri sahiplerine de gecikmeksizin (ihlalin niteliği ve riski
          gözetilerek) bilgi verilir.
        </p>
      </LegalSection>

      <LegalSection title="9. VERBİS Kaydı">
        <p>
          Mayotek, KVKK Kurulu&apos;nun belirlediği eşikleri (yıllık çalışan sayısı 50+, mali
          bilanço 25M ₺+, özel nitelikli veri ana faaliyet) aşmadığı için Veri Sorumluları
          Sicili (VERBİS) kayıt yükümlülüğü <strong>bulunmamaktadır</strong>. Eşikler aşıldığında
          veya gönüllü olarak kayıt yapıldığında bu metin güncellenecektir.
        </p>
      </LegalSection>
    </LegalLayout>
  );
}
