"use client";

/**
 * Hisse senedi ve TEFAS sayfaları için MKK e-Yatırımcı ipucu.
 * Kullanıcıya "Tüm Kıymetler" Excel dosyasını nereden indireceğini söyler.
 */
export function MkkHint() {
  return (
    <div className="mt-3 flex items-start gap-2 text-xs text-gray-500 bg-blue-50 border border-blue-100 rounded-lg px-3 py-2">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" className="w-4 h-4 text-blue-500 flex-shrink-0 mt-0.5">
        <circle cx="12" cy="12" r="10" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 16v-4M12 8h.01" />
      </svg>
      <p>
        Excel dosyanızı{" "}
        <a
          href="https://eyatirimci.mkk.com.tr/account-portfolio-balance"
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-600 hover:text-blue-700 font-medium underline"
        >
          MKK e-Yatırımcı &gt; Hesap Portföy Bakiyesi
        </a>
        {" "}sayfasından (&quot;Tüm Kıymetler&quot;) indirip yükleyebilirsiniz. Tüm aracı kurum hesaplarınız tek dosyada toplu olarak gelir.
      </p>
    </div>
  );
}
