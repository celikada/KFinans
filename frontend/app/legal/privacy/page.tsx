import { LegalLayout, LegalSection } from "../_components/LegalLayout";

export const metadata = { title: "Gizlilik Politikası — KFinans" };

export default function PrivacyPage() {
  return (
    <LegalLayout title="Gizlilik Politikası" lastUpdated="2026-05-02">
      <p className="text-sm">
        Bu politika, KFinans uygulamasının (&quot;Hizmet&quot;) topladığı, kullandığı ve koruduğu
        kişisel veriler hakkında genel bilgi sağlar. Detaylı yasal çerçeve için
        {" "}<a href="/legal/kvkk" className="text-blue-600">KVKK Aydınlatma Metni</a>&apos;ne bakınız.
      </p>

      <LegalSection title="Topladığımız Veriler">
        <p>Hizmeti kullanırken aşağıdaki verileri toplarız:</p>
        <ul className="list-disc pl-5">
          <li>Hesap bilgileri: e-posta, şifre (geri döndürülemez şekilde hash&apos;lenir)</li>
          <li>Portföy verileri: kayıtlı borsa entegrasyonları, blockchain cüzdan adresleri,
            yatırım fonu/hisse/BES holdingleri</li>
          <li>Otomatik veriler: IP, tarayıcı/uygulama bilgisi, erişim zamanları</li>
        </ul>
      </LegalSection>

      <LegalSection title="Verilerinizi Nasıl Kullanırız">
        <ul className="list-disc pl-5">
          <li>Hesabınızı oluşturmak ve sürdürmek</li>
          <li>Borsa, blockchain ve yatırım fonu API&apos;leri üzerinden bakiyenizi okuyup tek
            ekranda göstermek</li>
          <li>Haftalık portföy snapshot&apos;ı oluşturmak ve geçmiş değişiminizi izlemek</li>
          <li>Talebiniz üzerine AI tabanlı bilgilendirici tavsiye üretmek</li>
          <li>Hizmet güvenliğini sağlamak ve istismarı önlemek</li>
        </ul>
      </LegalSection>

      <LegalSection title="Verilerinizi Kimlerle Paylaşırız">
        <p>
          KFinans kişisel verilerinizi <strong>satmaz</strong> ve pazarlama amacıyla üçüncü
          taraflarla paylaşmaz. Sadece hizmetin gerektirdiği teknik sağlayıcılarla aktarım
          yapılır:
        </p>
        <ul className="list-disc pl-5">
          <li>E-posta gönderimi: Resend (yalnızca e-posta adresi)</li>
          <li>AI tavsiye üretimi: Anthropic (anonim portföy özeti)</li>
          <li>Barındırma: bulut altyapı sağlayıcıları</li>
          <li>Yasal makamlar: yasal bir zorunluluk halinde</li>
        </ul>
      </LegalSection>

      <LegalSection title="Borsa API Anahtarlarınızın Güvenliği">
        <p>
          Borsa entegrasyonu eklediğinizde, API anahtarlarınız Fernet simetrik şifreleme ile
          şifrelenip veri tabanında saklanır. Anahtarlar yalnızca bakiye okumak için kullanılır;
          KFinans bu anahtarlarla işlem yapma, para çekme veya transfer etme yetkisi
          <strong> talep etmez ve kullanmaz</strong>.
        </p>
        <p className="text-xs text-gray-500">
          Tavsiye: borsa hesabınızda API anahtarına yalnızca <em>read-only</em> izin verin,
          IP whitelist ekleyin.
        </p>
      </LegalSection>

      <LegalSection title="Veri Saklama">
        <p>
          Verileriniz hesabınız aktif olduğu sürece tutulur. Hesabınızı sildiğinizde 30 günlük
          cayma süresi başlar; bu süre sonunda kişisel verileriniz anonimleştirilir veya silinir.
          Yasal zorunluluk olan kayıtlar (ödeme, fatura) ilgili kanunda belirlenen süre kadar
          tutulur.
        </p>
      </LegalSection>

      <LegalSection title="Veri İhlali Halinde">
        <p>
          Olası bir veri ihlali tespit edilirse, KVKK m.12/5 uyarınca en geç 72 saat içinde
          Kişisel Verileri Koruma Kurulu&apos;na bildirim yapılır ve etkilenen kullanıcılara
          gecikmeksizin bilgi verilir.
        </p>
      </LegalSection>

      <LegalSection title="Otomatik Karar Verme ve AI">
        <p>
          KFinans&apos;ın AI tabanlı tavsiye motoru çıktılarını <strong>bağlayıcı yatırım
          tavsiyesi olarak değil</strong>, bilgilendirme amaçlı sunar. Hiçbir karar tek başına
          otomatik sistem tarafından sizin aleyhinize sonuç doğuracak şekilde alınmaz; nihai
          yatırım kararı her zaman size aittir. KVKK m.11/g kapsamında otomatik analiz
          sonucuna itiraz hakkınız vardır.
        </p>
      </LegalSection>

      <LegalSection title="Çocukların Verisi">
        <p>
          KFinans 18 yaşın altındaki kişilere yönelik bir hizmet değildir. 18 yaş altı bir
          kullanıcının verisinin işlendiğini fark edersek hesap derhal kapatılır ve veriler silinir.
        </p>
      </LegalSection>

      <LegalSection title="Politika Değişiklikleri">
        <p>
          Bu politika güncellenebilir. Önemli değişikliklerde size e-posta ile veya uygulama
          içinde bildirim gönderilir. En son güncelleme tarihi sayfanın üstünde belirtilmiştir.
        </p>
      </LegalSection>

      <LegalSection title="İletişim">
        <p>
          Sorularınız için <a href="mailto:privacy@kfinans.app" className="text-blue-600">privacy@kfinans.app</a>
          {" "}adresine yazabilirsiniz.
        </p>
      </LegalSection>
    </LegalLayout>
  );
}
