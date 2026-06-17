// KFinans Frontend — API barrel.
//
// 1511 satırlık monolitik dosya 3 aşamada bölündü:
//   1. types.ts        — 45+ DTO/interface/const (MR #5, a463c6d)
//   2. _client.ts      — HTTP helpers (request, setAuth, getAccessToken, ...) (MR #6, 72a1fd3)
//   3. api/<domain>.ts — 19 domain modülü (bu MR)
//
// Public yüzey aynen korunur: consumer'lar `import { api, ExpenseDTO, setAuth } from "@/lib/api"`
// yazabilir. api objesi 19 domain'in spread'i (Object.assign mantığı).

// Public auth helpers + tüm DTO/type/const'ları re-export
export { clearAuth, setAuth } from "./api/_client";
export * from "./api/types";

// Domain modülleri (alfabetik)
import { authApi } from "./api/auth";
import { besApi } from "./api/bes";
import { budgetApi } from "./api/budget";
import { cashApi } from "./api/cash";
import { cashFlowApi } from "./api/cashFlow";
import { commodityApi } from "./api/commodity";
import { creditCardsApi } from "./api/creditCards";
import { expensesApi } from "./api/expenses";
import { goalApi } from "./api/goal";
import { incomesApi } from "./api/incomes";
import { integrationsApi } from "./api/integrations";
import { manualCryptoApi } from "./api/manualCrypto";
import { personalDebtsApi } from "./api/personalDebts";
import { plannedExpensesApi } from "./api/plannedExpenses";
import { portfolioApi } from "./api/portfolio";
import { pushApi } from "./api/push";
import { recurringApi } from "./api/recurring";
import { releaseApi } from "./api/release";
import { reportsApi } from "./api/reports";
import { stocksApi } from "./api/stocks";
import { subscriptionsApi } from "./api/subscriptions";
import { tefasApi } from "./api/tefas";
import { userApi } from "./api/user";
import { walletsApi } from "./api/wallets";

export const api = {
  ...authApi,
  ...besApi,
  ...budgetApi,
  ...cashApi,
  ...cashFlowApi,
  ...commodityApi,
  ...creditCardsApi,
  ...expensesApi,
  ...goalApi,
  ...incomesApi,
  ...integrationsApi,
  ...manualCryptoApi,
  ...personalDebtsApi,
  ...plannedExpensesApi,
  ...portfolioApi,
  ...pushApi,
  ...recurringApi,
  ...releaseApi,
  ...reportsApi,
  ...stocksApi,
  ...subscriptionsApi,
  ...tefasApi,
  ...userApi,
  ...walletsApi,
};
