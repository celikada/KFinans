import { describe, expect, it, beforeEach, afterEach, vi } from "vitest";
import { BASE } from "../lib/api/_client";
import { besApi } from "../lib/api/bes";
import { budgetApi } from "../lib/api/budget";
import { cashApi } from "../lib/api/cash";
import { cashFlowApi } from "../lib/api/cashFlow";
import { commodityApi } from "../lib/api/commodity";
import { creditCardsApi } from "../lib/api/creditCards";
import { expensesApi } from "../lib/api/expenses";
import { goalApi } from "../lib/api/goal";
import { incomesApi } from "../lib/api/incomes";
import { integrationsApi } from "../lib/api/integrations";
import { manualCryptoApi } from "../lib/api/manualCrypto";
import { plannedExpensesApi } from "../lib/api/plannedExpenses";
import { portfolioApi } from "../lib/api/portfolio";
import { reportsApi } from "../lib/api/reports";
import { stocksApi } from "../lib/api/stocks";
import { tefasApi } from "../lib/api/tefas";
import { userApi } from "../lib/api/user";
import { walletsApi } from "../lib/api/wallets";

// Tüm wrapper'lar fetch'i mock'lar. Her fetch çağrısının doğru URL + method +
// body ile yapıldığını assert ederiz. fetch her zaman 200 + {} döner.

let fetchMock: ReturnType<typeof vi.fn>;

function lastCall() {
  const calls = fetchMock.mock.calls;
  const [url, init] = calls[calls.length - 1];
  return { url: url as string, init: (init ?? {}) as RequestInit };
}

function expectFetch(suffix: string, method = "GET") {
  const { url, init } = lastCall();
  expect(url).toBe(`${BASE}${suffix}`);
  // GET request'lerde method undefined olabilir.
  expect(init.method ?? "GET").toBe(method);
}

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
  fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
  vi.stubGlobal("fetch", fetchMock);
  // downloadBlob için URL + anchor stub
  vi.stubGlobal("URL", {
    ...URL,
    createObjectURL: vi.fn().mockReturnValue("blob:x"),
    revokeObjectURL: vi.fn(),
  });
});

afterEach(() => vi.restoreAllMocks());

// Excel indirme için blob yanıtı + anchor mock kuran helper.
function stubDownload() {
  fetchMock.mockResolvedValue(new Response(new Blob(["x"]), { status: 200 }));
  vi.spyOn(document, "createElement").mockReturnValue({
    href: "",
    download: "",
    rel: "",
    style: {},
    click: vi.fn(),
    remove: vi.fn(),
  } as unknown as HTMLAnchorElement);
  // saveBlob artik <a>'yi DOM'a ekliyor — stub anchor gercek Node degil, appendChild no-op.
  vi.spyOn(document.body, "appendChild").mockImplementation((n) => n as unknown as Node);
}

describe("besApi", () => {
  it("getBesHoldings", async () => {
    await besApi.getBesHoldings();
    expectFetch("/portfolio/bes/holdings");
  });
  it("saveBesHoldings PUT body", async () => {
    await besApi.saveBesHoldings([{ id: 1 } as never]);
    expectFetch("/portfolio/bes/holdings", "PUT");
    expect(lastCall().init.body).toBe('[{"id":1}]');
  });
  it("exportBesHoldings", async () => {
    stubDownload();
    await besApi.exportBesHoldings();
    expectFetch("/portfolio/bes/export");
  });
  it("importBesHoldings", async () => {
    await besApi.importBesHoldings(new File(["x"], "b.xlsx"));
    expectFetch("/portfolio/bes/import", "POST");
  });
});

describe("budgetApi", () => {
  it("listBudgets", async () => {
    await budgetApi.listBudgets();
    expectFetch("/budgets");
  });
  it("upsertBudget", async () => {
    await budgetApi.upsertBudget("market", 500);
    expectFetch("/budgets/market", "PUT");
    expect(lastCall().init.body).toBe('{"amount":500}');
  });
  it("deleteBudget", async () => {
    await budgetApi.deleteBudget("market");
    expectFetch("/budgets/market", "DELETE");
  });
  it("getBudgetComparison", async () => {
    await budgetApi.getBudgetComparison(2026, 5);
    expectFetch("/budgets/comparison?year=2026&month=5");
  });
});

describe("cashApi", () => {
  it("listCash", async () => {
    await cashApi.listCash();
    expectFetch("/cash");
  });
  it("createCash", async () => {
    await cashApi.createCash({ amount: 100 } as never);
    expectFetch("/cash", "POST");
  });
  it("updateCash", async () => {
    await cashApi.updateCash(7, { amount: 200 } as never);
    expectFetch("/cash/7", "PUT");
  });
  it("deleteCash", async () => {
    await cashApi.deleteCash(7);
    expectFetch("/cash/7", "DELETE");
  });
});

describe("cashFlowApi", () => {
  it("getCashFlow", async () => {
    await cashFlowApi.getCashFlow(2026);
    expectFetch("/cash-flow?year=2026");
  });
});

describe("commodityApi", () => {
  it("getCommodities", async () => {
    await commodityApi.getCommodities();
    expectFetch("/portfolio/commodities");
  });
  it("createCommodity", async () => {
    await commodityApi.createCommodity({ metal: "XAU" } as never);
    expectFetch("/portfolio/commodities", "POST");
  });
  it("updateCommodity", async () => {
    await commodityApi.updateCommodity(3, { quantity: 5 });
    expectFetch("/portfolio/commodities/3", "PUT");
  });
  it("deleteCommodity", async () => {
    await commodityApi.deleteCommodity(3);
    expectFetch("/portfolio/commodities/3", "DELETE");
  });
  it("exportCommodities", async () => {
    stubDownload();
    await commodityApi.exportCommodities();
    expectFetch("/portfolio/commodities/export");
  });
  it("importCommodities", async () => {
    await commodityApi.importCommodities(new File(["x"], "c.xlsx"));
    expectFetch("/portfolio/commodities/import", "POST");
  });
});

describe("creditCardsApi", () => {
  it("listCreditCards", async () => {
    await creditCardsApi.listCreditCards();
    expectFetch("/credit-cards");
  });
  it("createCreditCard", async () => {
    await creditCardsApi.createCreditCard({ name: "X" } as never);
    expectFetch("/credit-cards", "POST");
  });
  it("updateCreditCard", async () => {
    await creditCardsApi.updateCreditCard(1, { name: "Y" });
    expectFetch("/credit-cards/1", "PUT");
  });
  it("deleteCreditCard", async () => {
    await creditCardsApi.deleteCreditCard(1);
    expectFetch("/credit-cards/1", "DELETE");
  });
  it("getCreditCardDetail", async () => {
    await creditCardsApi.getCreditCardDetail(1);
    expectFetch("/credit-cards/1");
  });
  it("createStatement", async () => {
    await creditCardsApi.createStatement(1, { statement_amount: 10 } as never);
    expectFetch("/credit-cards/1/statements", "POST");
  });
  it("updateStatement", async () => {
    await creditCardsApi.updateStatement(1, 2, { statement_amount: 20 });
    expectFetch("/credit-cards/1/statements/2", "PUT");
  });
  it("deleteStatement", async () => {
    await creditCardsApi.deleteStatement(1, 2);
    expectFetch("/credit-cards/1/statements/2", "DELETE");
  });
  it("createInstallment", async () => {
    await creditCardsApi.createInstallment(1, { total_amount: 100 } as never);
    expectFetch("/credit-cards/1/installments", "POST");
  });
  it("updateInstallment", async () => {
    await creditCardsApi.updateInstallment(1, 3, { monthly_amount: 200 });
    expectFetch("/credit-cards/1/installments/3", "PUT");
  });
  it("deleteInstallment", async () => {
    await creditCardsApi.deleteInstallment(1, 3);
    expectFetch("/credit-cards/1/installments/3", "DELETE");
  });
});

describe("expensesApi", () => {
  it("listExpenses boş param → query yok", async () => {
    await expensesApi.listExpenses();
    expectFetch("/expenses");
  });
  it("listExpenses tüm paramlar → query string", async () => {
    await expensesApi.listExpenses({ year: 2026, month: 5, category: "market" });
    expectFetch("/expenses?year=2026&month=5&category=market");
  });
  it("createExpense", async () => {
    await expensesApi.createExpense({ amount: 10 } as never);
    expectFetch("/expenses", "POST");
  });
  it("updateExpense", async () => {
    await expensesApi.updateExpense(4, { amount: 20 });
    expectFetch("/expenses/4", "PUT");
  });
  it("deleteExpense", async () => {
    await expensesApi.deleteExpense(4);
    expectFetch("/expenses/4", "DELETE");
  });
  it("getExpenseSummary", async () => {
    await expensesApi.getExpenseSummary(2026, 5);
    expectFetch("/expenses/summary?year=2026&month=5");
  });
  it("exportExpenses boş → query yok", async () => {
    stubDownload();
    await expensesApi.exportExpenses();
    expectFetch("/expenses/export");
  });
  it("exportExpenses paramlı", async () => {
    stubDownload();
    await expensesApi.exportExpenses(2026, 5);
    expectFetch("/expenses/export?year=2026&month=5");
  });
  it("importExpenses", async () => {
    await expensesApi.importExpenses(new File(["x"], "e.xlsx"));
    expectFetch("/expenses/import", "POST");
  });
});

describe("goalApi", () => {
  it("getGoal", async () => {
    await goalApi.getGoal();
    expectFetch("/user/goal");
  });
  it("setGoal", async () => {
    await goalApi.setGoal(1000, "TRY");
    expectFetch("/user/goal", "PUT");
    expect(lastCall().init.body).toBe('{"amount":1000,"currency":"TRY"}');
  });
});

describe("incomesApi", () => {
  it("listIncomes boş", async () => {
    await incomesApi.listIncomes();
    expectFetch("/income");
  });
  it("listIncomes paramlı", async () => {
    await incomesApi.listIncomes({ year: 2026, month: 5, category: "maas" });
    expectFetch("/income?year=2026&month=5&category=maas");
  });
  it("createIncome", async () => {
    await incomesApi.createIncome({ amount: 10 } as never);
    expectFetch("/income", "POST");
  });
  it("updateIncome", async () => {
    await incomesApi.updateIncome(2, { amount: 20 });
    expectFetch("/income/2", "PUT");
  });
  it("deleteIncome", async () => {
    await incomesApi.deleteIncome(2);
    expectFetch("/income/2", "DELETE");
  });
  it("getIncomeSummary", async () => {
    await incomesApi.getIncomeSummary(2026, 5);
    expectFetch("/income/summary?year=2026&month=5");
  });
  it("getIncomeDashboard", async () => {
    await incomesApi.getIncomeDashboard(2026, 5);
    expectFetch("/income/dashboard?year=2026&month=5");
  });
  it("listRecurringIncomes", async () => {
    await incomesApi.listRecurringIncomes();
    expectFetch("/income/recurring");
  });
  it("createRecurringIncome", async () => {
    await incomesApi.createRecurringIncome({ amount: 10 } as never);
    expectFetch("/income/recurring", "POST");
  });
  it("updateRecurringIncome", async () => {
    await incomesApi.updateRecurringIncome(5, { amount: 20 });
    expectFetch("/income/recurring/5", "PUT");
  });
  it("deleteRecurringIncome", async () => {
    await incomesApi.deleteRecurringIncome(5);
    expectFetch("/income/recurring/5", "DELETE");
  });
  it("realizeRecurringPeriod", async () => {
    await incomesApi.realizeRecurringPeriod(5, 2026, 5);
    expectFetch("/income/recurring/5/realize", "POST");
    expect(lastCall().init.body).toBe('{"year":2026,"month":5}');
  });
  it("realizeRecurringPast", async () => {
    await incomesApi.realizeRecurringPast(5);
    expectFetch("/income/recurring/5/realize-past", "POST");
  });
  it("realizeAllRecurringPast", async () => {
    await incomesApi.realizeAllRecurringPast();
    expectFetch("/income/recurring/realize-all-past", "POST");
  });
  it("exportIncomes boş", async () => {
    stubDownload();
    await incomesApi.exportIncomes();
    expectFetch("/income/export");
  });
  it("exportIncomes paramlı", async () => {
    stubDownload();
    await incomesApi.exportIncomes(2026, 5);
    expectFetch("/income/export?year=2026&month=5");
  });
  it("importIncomes", async () => {
    await incomesApi.importIncomes(new File(["x"], "i.xlsx"));
    expectFetch("/income/import", "POST");
  });
});

describe("integrationsApi", () => {
  it("getIntegrations", async () => {
    await integrationsApi.getIntegrations();
    expectFetch("/integrations");
  });
  it("addIntegration", async () => {
    await integrationsApi.addIntegration("binance", "k", "s", "t");
    expectFetch("/integrations", "POST");
    expect(lastCall().init.body).toBe(
      '{"provider":"binance","api_key":"k","api_secret":"s","extra_token":"t"}',
    );
  });
  it("removeIntegration", async () => {
    await integrationsApi.removeIntegration("binance");
    expectFetch("/integrations/binance", "DELETE");
  });
});

describe("manualCryptoApi", () => {
  it("listManualCrypto", async () => {
    await manualCryptoApi.listManualCrypto();
    expectFetch("/manual-crypto");
  });
  it("createManualCrypto", async () => {
    await manualCryptoApi.createManualCrypto({ symbol: "BTC" } as never);
    expectFetch("/manual-crypto", "POST");
  });
  it("updateManualCrypto", async () => {
    await manualCryptoApi.updateManualCrypto(9, { quantity: 1 } as never);
    expectFetch("/manual-crypto/9", "PUT");
  });
  it("deleteManualCrypto", async () => {
    await manualCryptoApi.deleteManualCrypto(9);
    expectFetch("/manual-crypto/9", "DELETE");
  });
  it("exportManualCrypto", async () => {
    stubDownload();
    await manualCryptoApi.exportManualCrypto();
    expectFetch("/manual-crypto/export");
  });
  it("importManualCrypto", async () => {
    await manualCryptoApi.importManualCrypto(new File(["x"], "m.xlsx"));
    expectFetch("/manual-crypto/import", "POST");
  });
  it("searchAssetCatalog boş param", async () => {
    await manualCryptoApi.searchAssetCatalog();
    expectFetch("/asset-catalog");
  });
  it("searchAssetCatalog tüm paramlar", async () => {
    await manualCryptoApi.searchAssetCatalog({ q: "eth", source: "binance", limit: 5 });
    expectFetch("/asset-catalog?q=eth&source=binance&limit=5");
  });
});

describe("plannedExpensesApi", () => {
  it("listPlannedExpenses", async () => {
    await plannedExpensesApi.listPlannedExpenses();
    expectFetch("/planned-expenses");
  });
  it("createPlannedExpense", async () => {
    await plannedExpensesApi.createPlannedExpense({ amount: 10 } as never);
    expectFetch("/planned-expenses", "POST");
  });
  it("updatePlannedExpense", async () => {
    await plannedExpensesApi.updatePlannedExpense(6, { amount: 20 });
    expectFetch("/planned-expenses/6", "PUT");
  });
  it("deletePlannedExpense", async () => {
    await plannedExpensesApi.deletePlannedExpense(6);
    expectFetch("/planned-expenses/6", "DELETE");
  });
  it("getForecast", async () => {
    await plannedExpensesApi.getForecast(2026);
    expectFetch("/planned-expenses/forecast?year=2026");
  });
});

describe("portfolioApi", () => {
  it("getCryptoPositions", async () => {
    await portfolioApi.getCryptoPositions();
    expectFetch("/portfolio/crypto");
  });
  it("previewSnapshot", async () => {
    await portfolioApi.previewSnapshot();
    expectFetch("/portfolio/snapshot/preview", "POST");
  });
  it("createSnapshot force=false", async () => {
    await portfolioApi.createSnapshot();
    expectFetch("/portfolio/snapshot", "POST");
  });
  it("createSnapshot force=true", async () => {
    await portfolioApi.createSnapshot(true);
    expectFetch("/portfolio/snapshot?force=true", "POST");
  });
  it("getPortfolioHistory default limit", async () => {
    await portfolioApi.getPortfolioHistory();
    expectFetch("/portfolio/history?limit=100");
  });
  it("getPortfolioHistory limit + year", async () => {
    await portfolioApi.getPortfolioHistory({ limit: 50, year: 2026 });
    expectFetch("/portfolio/history?limit=50&year=2026");
  });
  it("getPortfolioHistoryYears", async () => {
    await portfolioApi.getPortfolioHistoryYears();
    expectFetch("/portfolio/history/years");
  });
  it("deleteSnapshot", async () => {
    await portfolioApi.deleteSnapshot("2026-05-31");
    expectFetch("/portfolio/snapshot/2026-05-31", "DELETE");
  });
  it("getUsdRate", async () => {
    await portfolioApi.getUsdRate();
    expectFetch("/portfolio/usd-rate");
  });
});

describe("reportsApi", () => {
  it("downloadReport", async () => {
    stubDownload();
    await reportsApi.downloadReport("/portfolio/snapshot/2026-05-31/report.pdf", "rapor.pdf");
    expectFetch("/portfolio/snapshot/2026-05-31/report.pdf");
  });
});

describe("stocksApi", () => {
  it("getStockHoldings", async () => {
    await stocksApi.getStockHoldings();
    expectFetch("/portfolio/stocks/holdings");
  });
  it("saveStockHoldings", async () => {
    await stocksApi.saveStockHoldings([{ symbol: "AKBNK" } as never]);
    expectFetch("/portfolio/stocks/holdings", "PUT");
  });
  it("stockPreview", async () => {
    await stocksApi.stockPreview([{ symbol: "AKBNK" } as never]);
    expectFetch("/portfolio/stocks/preview", "POST");
  });
  it("exportStockHoldings", async () => {
    stubDownload();
    await stocksApi.exportStockHoldings();
    expectFetch("/portfolio/stocks/export");
  });
  it("importStockMkk", async () => {
    await stocksApi.importStockMkk(new File(["x"], "s.xls"));
    expectFetch("/portfolio/stocks/import-mkk", "POST");
  });
  it("importStockHoldings", async () => {
    await stocksApi.importStockHoldings(new File(["x"], "s.xlsx"));
    expectFetch("/portfolio/stocks/import", "POST");
  });
});

describe("tefasApi", () => {
  it("getTefasHoldings", async () => {
    await tefasApi.getTefasHoldings();
    expectFetch("/portfolio/tefas/holdings");
  });
  it("saveTefasHoldings", async () => {
    await tefasApi.saveTefasHoldings([{ code: "AFA" } as never]);
    expectFetch("/portfolio/tefas/holdings", "PUT");
  });
  it("tefasPreview", async () => {
    await tefasApi.tefasPreview([{ code: "AFA" } as never]);
    expectFetch("/portfolio/tefas/preview", "POST");
  });
  it("exportTefasHoldings", async () => {
    stubDownload();
    await tefasApi.exportTefasHoldings();
    expectFetch("/portfolio/tefas/export");
  });
  it("importTefasHoldings", async () => {
    await tefasApi.importTefasHoldings(new File(["x"], "t.xlsx"));
    expectFetch("/portfolio/tefas/import", "POST");
  });
  it("importTefasMkk", async () => {
    await tefasApi.importTefasMkk(new File(["x"], "t.xls"));
    expectFetch("/portfolio/tefas/import-mkk", "POST");
  });
});

describe("userApi", () => {
  it("getMe", async () => {
    await userApi.getMe();
    expectFetch("/user/me");
  });
  it("updateProfile", async () => {
    await userApi.updateProfile("aggressive");
    expectFetch("/user/profile", "PUT");
    expect(lastCall().init.body).toBe('{"risk_profile":"aggressive"}');
  });
  it("changePassword", async () => {
    await userApi.changePassword("old", "new");
    expectFetch("/user/password", "PUT");
    expect(lastCall().init.body).toBe('{"current_password":"old","new_password":"new"}');
  });
  it("deleteAccount", async () => {
    await userApi.deleteAccount();
    expectFetch("/user/me", "DELETE");
  });
});

describe("walletsApi", () => {
  it("getWallets", async () => {
    await walletsApi.getWallets();
    expectFetch("/wallets");
  });
  it("addWallet", async () => {
    await walletsApi.addWallet("ethereum", "0xabc", "Ana");
    expectFetch("/wallets", "POST");
    expect(lastCall().init.body).toBe('{"chain":"ethereum","address":"0xabc","label":"Ana"}');
  });
  it("removeWallet", async () => {
    await walletsApi.removeWallet("w-1");
    expectFetch("/wallets/w-1", "DELETE");
  });
  it("getWalletPositions", async () => {
    await walletsApi.getWalletPositions();
    expectFetch("/portfolio/wallets");
  });
  it("exportWallets", async () => {
    stubDownload();
    await walletsApi.exportWallets();
    expectFetch("/wallets/export");
  });
  it("importWallets", async () => {
    await walletsApi.importWallets(new File(["x"], "w.xlsx"));
    expectFetch("/wallets/import", "POST");
  });
});
