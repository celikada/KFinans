"use client";
import { useRef, useState } from "react";

interface Props {
  /** Dosya seçildiğinde çağrılır. Tanımlıysa "MKK Excel'i Yükle" butonu gösterilir. */
  readonly onUpload?: (file: File) => Promise<void>;
}

/**
 * Hisse senedi ve TEFAS sayfaları için MKK e-Yatırımcı ipucu.
 * Opsiyonel olarak doğrudan MKK xls dosyası yükleme butonu içerir.
 */
export function MkkHint({ onUpload }: Props) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [err, setErr] = useState("");

  async function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !onUpload) return;
    setUploading(true);
    setErr("");
    try {
      await onUpload(file);
    } catch (error_) {
      setErr(error_ instanceof Error ? error_.message : "Yükleme başarısız");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  return (
    <div className="mt-3 flex items-start gap-2 text-xs text-gray-600 bg-blue-50 border border-blue-100 rounded-lg px-3 py-2.5">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" className="w-4 h-4 text-blue-500 flex-shrink-0 mt-0.5">
        <circle cx="12" cy="12" r="10" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 16v-4M12 8h.01" />
      </svg>
      <div className="flex-1">
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
        {onUpload && (
          <div className="mt-2 flex items-center gap-3">
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              disabled={uploading}
              className="inline-flex items-center gap-1.5 text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-3.5 h-3.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0 4.5 4.5M12 3v13.5" />
              </svg>
              {uploading ? "Yükleniyor..." : "MKK Excel'i Yükle"}
            </button>
            <span className="text-xs text-gray-400">(.xls / .xlsx)</span>
            <input
              ref={fileRef}
              type="file"
              accept=".xls,.xlsx"
              className="hidden"
              onChange={handleFile}
              disabled={uploading}
            />
          </div>
        )}
        {err && (
          <p className="mt-2 text-xs text-red-600 bg-red-50 border border-red-100 rounded px-2 py-1">{err}</p>
        )}
      </div>
    </div>
  );
}
