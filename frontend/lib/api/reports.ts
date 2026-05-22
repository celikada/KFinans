import { BASE, getAccessToken } from "./_client";

export const reportsApi = {
  // Rapor indirme yardımcısı (hem Excel hem PDF için)
  downloadReport: async (path: string, filename: string) => {
    const token = getAccessToken();
    const res = await fetch(`${BASE}${path}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error("Rapor indirilemedi");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  },
};
