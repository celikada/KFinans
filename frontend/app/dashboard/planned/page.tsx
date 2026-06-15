import { redirect } from "next/navigation";

// Planlı harcamalar sayfası "Harcamalar > Periyodik" sekmesine taşındı (gelir
// sayfasıyla simetrik). Eski /dashboard/planned linkleri kırılmasın diye kalıcı
// olarak birleşik sayfanın periyodik sekmesine yönlendirilir.
export default function PlannedRedirectPage() {
  redirect("/dashboard/expenses?tab=periyodik");
}
