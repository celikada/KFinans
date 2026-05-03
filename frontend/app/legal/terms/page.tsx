import { LegalLayout, LegalSection } from "../_components/LegalLayout";

export const metadata = { title: "Kullanım Şartları — KFinans" };

export default function TermsPage() {
  return (
    <LegalLayout title="Kullanım Şartları" lastUpdated="2026-05-02">
      <p className="text-sm">
        KFinans uygulamasını (&quot;Hizmet&quot;) kullanarak aşağıdaki şartları kabul etmiş
        olursunuz. Lütfen dikkatlice okuyunuz.
      </p>

      <LegalSection title="1. Hizmetin Tanımı">
        <p>
          KFinans, kullanıcının çeşitli platformlarda (kripto borsaları, blockchain cüzdanlar,
          yatırım fonu, BES) sahip olduğu varlıkların değerini tek ekranda görüntülemesine ve
          değişimini izlemesine olanak tanıyan bir kişisel finans aracıdır.
        </p>
      </LegalSection>

      <LegalSection title="2. Yatırım Danışmanlığı Değildir">
        <p>
          KFinans <strong>yatırım danışmanlığı hizmeti sunmaz</strong>. Uygulama içerisindeki
          AI tabanlı içerik bilgilendirme amaçlı olup 6362 sayılı Sermaye Piyasası Kanunu
          kapsamında bağlayıcı yatırım tavsiyesi niteliği taşımaz.
        </p>
        <p>
          Yatırım kararlarınızdan ve sonuçlarından münhasıran siz sorumlusunuz. Önemli kararlar
          için lisanslı bir yatırım danışmanına başvurmanız önerilir.
        </p>
      </LegalSection>

      <LegalSection title="3. Hesap Oluşturma">
        <ul className="list-disc pl-5">
          <li>18 yaşını doldurmuş olmalısınız.</li>
          <li>Doğru ve güncel bilgi vermelisiniz.</li>
          <li>Hesap güvenliğinizden (şifre, API anahtarları) siz sorumlusunuz.</li>
          <li>Hesabınızda yetkisiz erişim fark ederseniz derhal bildirin.</li>
        </ul>
      </LegalSection>

      <LegalSection title="4. Borsa API Anahtarları">
        <p>
          Borsa entegrasyonu eklerken yalnızca <strong>okuma izinli</strong> (trading veya
          withdrawal yetkisi olmayan) API anahtarları kullanmanız önerilir. KFinans, withdrawal
          yetkili anahtarların kötüye kullanımı sonucunda doğan zararlardan sorumlu tutulamaz.
        </p>
      </LegalSection>

      <LegalSection title="5. Yasaklı Kullanımlar">
        <ul className="list-disc pl-5">
          <li>Hizmeti yasalara aykırı amaçlarla kullanmak</li>
          <li>Başkasına ait API anahtarı veya cüzdan adresi yetkisiz şekilde eklemek</li>
          <li>Hizmetin altyapısına saldırı denemesi yapmak (DoS, brute-force, scraping otomasyonu)</li>
          <li>Hesabı ticari amaçla başkasına devretmek</li>
          <li>Servisin tersine mühendisliğini yapmak</li>
        </ul>
      </LegalSection>

      <LegalSection title="6. Hizmet Kullanılabilirliği">
        <p>
          KFinans &quot;olduğu gibi&quot; sunulur. Üçüncü taraf API&apos;lerin (borsa, blockchain RPC,
          TEFAS, Yahoo Finance) erişilemez olması durumunda ilgili veriler geçici olarak gösterilemez.
          Planlı bakım ve yükseltmeler için Hizmet kısa süreli kesintiye uğrayabilir.
        </p>
      </LegalSection>

      <LegalSection title="7. Sorumluluğun Sınırlandırılması">
        <p>
          Yasaların izin verdiği azami ölçüde, KFinans aşağıdakilerden sorumlu tutulamaz:
        </p>
        <ul className="list-disc pl-5">
          <li>Kullanıcının yatırım kararlarından doğan zarar</li>
          <li>Üçüncü taraf API&apos;lerinden gelen hatalı veri</li>
          <li>Kullanıcı hesabının kullanıcının kusurlu davranışı sonucu ele geçirilmesi</li>
          <li>Beklenmeyen hizmet kesintileri (mücbir sebepler, üst yetkili sağlayıcı arızaları)</li>
        </ul>
        <p className="text-xs text-gray-500">
          <strong>Tüketici hakları saklıdır:</strong> 6502 sayılı Tüketicinin Korunması
          Hakkında Kanun ve ilgili mevzuat kapsamında tüketicilere tanınan ve sözleşme ile
          sınırlandırılamayacak haklar bu maddedeki sınırlamalardan etkilenmez.
        </p>
      </LegalSection>

      <LegalSection title="8. Hesabın Sonlandırılması">
        <p>
          Hesabınızı dilediğiniz zaman ayarlardan silebilirsiniz. KFinans, kullanım şartlarını
          ihlal eden hesapları önceden uyarı yaparak askıya alma veya kapatma hakkını saklı tutar.
        </p>
      </LegalSection>

      <LegalSection title="9. Değişiklikler">
        <p>
          Bu şartlar zaman zaman güncellenebilir. Önemli değişikliklerde e-posta ile veya
          uygulama içinde bildirim gönderilir. Değişiklik sonrası Hizmeti kullanmaya devam
          etmeniz, yeni şartları kabul ettiğiniz anlamına gelir.
        </p>
      </LegalSection>

      <LegalSection title="10. Uygulanacak Hukuk ve Yetkili Mahkeme">
        <p>
          Bu sözleşme Türkiye Cumhuriyeti yasalarına tabidir. Anlaşmazlıklarda
          [İSTANBUL/MERKEZ] Mahkemeleri ve İcra Daireleri yetkilidir.
        </p>
      </LegalSection>
    </LegalLayout>
  );
}
