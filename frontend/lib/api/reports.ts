import { downloadBlob } from "./_client";

export const reportsApi = {
  // Rapor indirme yardımcısı (hem Excel hem PDF için). consumer kodu
  // `api.downloadReport(path, filename)` ile çağırır.
  downloadReport: (path: string, filename: string) => downloadBlob(path, filename),
};
