import { LegalLayout, LegalSection } from "../_components/LegalLayout";

export const metadata = { title: "Çerez Politikası — KFinans" };

export default function CookiesPage() {
  return (
    <LegalLayout title="Çerez Politikası" lastUpdated="2026-05-02">
      <p className="text-sm">
        Bu politika, KFinans web uygulamasının kullandığı çerezler (cookies) ve benzeri
        depolama mekanizmaları hakkında bilgi verir.
      </p>

      <LegalSection title="Çerez Nedir?">
        <p>
          Çerezler, ziyaret ettiğiniz bir web sitesinin tarayıcınıza yerleştirdiği küçük metin
          dosyalarıdır. Oturumunuzu sürdürmek, tercihlerinizi hatırlamak veya analitik veri
          toplamak için kullanılırlar.
        </p>
      </LegalSection>

      <LegalSection title="Kullandığımız Çerezler ve Depolama">
        <table className="w-full text-xs border-collapse">
          <thead>
            <tr className="border-b">
              <th className="text-left py-2">Tür</th>
              <th className="text-left py-2">Amaç</th>
              <th className="text-left py-2">Yasal Zemin</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            <tr>
              <td className="py-2"><code>access_token</code> (cookie + localStorage)</td>
              <td className="py-2">Oturum sürdürme — JWT erişim jetonu</td>
              <td className="py-2">Zorunlu (sözleşme ifası)</td>
            </tr>
          </tbody>
        </table>
        <p className="text-xs text-gray-500">
          Şu anda KFinans <strong>analytics, reklam veya üçüncü taraf izleme çerezleri</strong>
          {" "}kullanmamaktadır. İleride analitik eklenirse bu politika güncellenir ve onayınız istenir.
        </p>
      </LegalSection>

      <LegalSection title="Çerezlerin Yönetimi">
        <p>
          Tarayıcı ayarlarınızdan çerezleri silebilir veya engelleyebilirsiniz. Ancak oturum
          çerezini engellerseniz uygulamaya giriş yapamazsınız (zorunlu çerez).
        </p>
        <ul className="list-disc pl-5">
          <li>Chrome: Ayarlar → Gizlilik ve güvenlik → Çerezler</li>
          <li>Firefox: Ayarlar → Gizlilik ve Güvenlik → Çerezler ve Site Verileri</li>
          <li>Safari: Tercihler → Gizlilik → Çerezler</li>
        </ul>
      </LegalSection>

      <LegalSection title="Üçüncü Taraf Çerezleri">
        <p>
          Şu anda hiçbir üçüncü taraf çerezi yerleştirilmez. Hizmetin doğrudan ihtiyacı olan
          ödeme entegrasyonu (iyzico) eklendiğinde, ödeme akışı sırasında ilgili sağlayıcının
          kendi çerezleri devreye girebilir.
        </p>
      </LegalSection>

      <LegalSection title="Politika Değişiklikleri">
        <p>
          Bu politikayı zaman zaman güncelleyebiliriz. Güncel sürüm her zaman bu sayfada
          yayınlanır. Önemli değişikliklerde uygulama içinde bilgilendirme yapılır.
        </p>
      </LegalSection>
    </LegalLayout>
  );
}
