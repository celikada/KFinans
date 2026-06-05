// KFinans Frontend — API DTO/Type/Constant catalog.
//
// `lib/api.ts` 1511 satırlık tek dosyaydı; type'lar buraya taşındı.
// Public yüzey aynı: consumer'lar hâlâ `import { ExpenseDTO } from "@/lib/api"`
// yazabilir (api.ts re-export ediyor). Sonraki aşama (ileri): endpoint method'ları
// domain modüllerine (auth.ts, expense.ts, ...) bölünecek.

// Decimal alanlar: backend Numeric → JSON'da string ya da number; form boşsa null.
export type DecimalInput = number | string | null;

// ─── Çoklu para birimi (v0.3.0) ─────────────────────────────────
// income/expense/planned/recurring/budget/credit_card kapsamı için ortak
// para birimi seti. cash + goal eski 4'lü setleri bunun alt kümesi.
export type CurrencyType = "TRY" | "USD" | "EUR" | "GBP" | "CHF" | "JPY";

export const CURRENCIES: CurrencyType[] = ["TRY", "USD", "EUR", "GBP", "CHF", "JPY"];

export const CURRENCY_SYMBOLS: Record<CurrencyType, string> = {
  TRY: "₺",
  USD: "$",
  EUR: "€",
  GBP: "£",
  CHF: "₣",
  JPY: "¥",
};

// ─── Auth + Kullanıcı ────────────────────────────────────────────

export interface UserMeDTO {
  email: string;
  risk_profile: "conservative" | "balanced" | "aggressive";
  created_at: string;
  email_verified: boolean;
  credit_balance: number;
  mfa_enabled?: boolean;
  is_admin?: boolean;
  release_notes_opt_in?: boolean;
  default_currency?: CurrencyType;
}

// ─── Sürüm bildirimleri (release notes) ──────────────────────────

export interface ReleaseOptInStatusDTO {
  release_notes_opt_in: boolean;
}

export interface ReleaseSendResultDTO {
  version: string;
  recipients: number;
  sent: number;
  failed: number;
}

// MFA (TOTP) — Audit #5
export interface MfaSetupResponse {
  secret_base32: string;
  otpauth_url: string;
  qr_png_base64: string; // "data:image/png;base64,..." veya saf base64
}

export interface MfaEnableResponse {
  recovery_codes: string[];
}

export interface MfaStatusResponse {
  mfa_enabled: boolean;
}

// Login response — MFA aktifse pre_mfa_token doner; aktif degilse normal tokenlar.
export interface LoginResponseDTO {
  access_token?: string;
  refresh_token?: string;
  token_type?: string;
  // MFA challenge
  mfa_required?: boolean;
  pre_mfa_token?: string;
}

export interface MfaVerifyResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export const RISK_PROFILE_LABELS: Record<"conservative" | "balanced" | "aggressive", string> = {
  conservative: "Muhafazakâr",
  balanced: "Dengeli",
  aggressive: "Agresif",
};

export interface RegisterResponseDTO {
  id: string;
  email: string;
  risk_profile: string;
  email_verified: boolean;
  verification_email_sent: boolean;
}

// ─── Snapshot + Portfolio ────────────────────────────────────────

export interface SnapshotHealthIssue {
  source: string;
  code: string;
  msg: string;
  level?: "warn" | "info"; // varsayılan 'warn' — eski kayıtlarda olmayabilir
  chain?: string | null;
  address?: string | null;
  provider?: string | null;
  label?: string | null;
  exchange?: string | null;
  symbol?: string | null;
}

export interface SnapshotHistoryDTO {
  id: string;
  snapshot_date: string;
  total_value_tl: string;
  usd_try_rate?: string | null;
  health_issues?: SnapshotHealthIssue[] | null;
  asset_positions: Array<{
    id: string;
    asset_type: string;
    provider: string;
    symbol: string;
    name: string;
    total_value_tl: string;
    weight_pct: string;
  }>;
}

export interface IntegrationDTO {
  id: string;
  provider: string;
  is_active: boolean;
  last_synced_at: string | null;
}

export interface CryptoPositionDTO {
  provider: string;
  symbol: string;
  liquid_quantity: string;
  staked_quantity: string;
  unit_price_usd: string;
  unit_price_tl: string;
  total_value_tl: string;
}

// ─── Stocks ─────────────────────────────────────────────────────

export interface StockHoldingDTO {
  ticker: string;
  quantity: number;
  name: string;
  avg_cost_tl?: number | null;
  distributor?: string | null;
}

export interface StockPositionDTO {
  ticker: string;
  name: string;
  quantity: string;
  currency: string;
  unit_price_original: string;
  unit_price_tl: string;
  total_value_tl: string;
  avg_cost_tl: string | null;
  cost_basis_tl: string | null;
  gain_loss_tl: string | null;
  gain_loss_pct: number | null;
  distributor: string | null;
}

// ─── Wallets ────────────────────────────────────────────────────

export interface WalletDTO {
  id: string;
  chain: string;
  address: string;
  label: string | null;
  is_active: boolean;
}

export interface WalletPositionDTO {
  wallet_id: string;
  chain: string;
  address: string;
  label: string | null;
  symbol: string;
  liquid_quantity: string;
  staked_quantity: string;
  pending_rewards: string;
  unit_price_usd: string;
  unit_price_tl: string;
  total_value_tl: string;
}

// ─── TEFAS + BES ────────────────────────────────────────────────

export interface TefasHoldingDTO {
  code: string;
  quantity: number;
  name: string;
  avg_cost_tl?: number | null;
  distributor?: string | null;
}

export interface BesHoldingDTO {
  plan_name: string;
  contract_number?: string | null;
  paid_principal: number | string;
  paid_returns: number | string;
  govt_contribution: number | string;
  govt_returns: number | string;
}

export interface TefasPosition {
  code: string;
  name: string;
  quantity: string;
  unit_price_tl: string;
  total_value_tl: string;
  avg_cost_tl: string | null;
  cost_basis_tl: string | null;
  gain_loss_tl: string | null;
  gain_loss_pct: number | null;
  distributor: string | null;
}

// ─── Expense ────────────────────────────────────────────────────

export type ExpenseCategory =
  | "food"
  | "groceries"
  | "transport"
  | "bills"
  | "health"
  | "entertainment"
  | "clothing"
  | "home"
  | "tax"
  | "other";

export const EXPENSE_CATEGORIES: ExpenseCategory[] = [
  "food",
  "groceries",
  "transport",
  "bills",
  "health",
  "entertainment",
  "clothing",
  "home",
  "tax",
  "other",
];

export const EXPENSE_CATEGORY_LABELS: Record<ExpenseCategory, string> = {
  food: "Yiyecek",
  groceries: "Market",
  transport: "Ulaşım",
  bills: "Faturalar",
  health: "Sağlık",
  entertainment: "Eğlence",
  clothing: "Giyim",
  home: "Ev",
  tax: "Vergi",
  other: "Diğer",
};

export interface ExpenseInput {
  amount: number;
  category: ExpenseCategory;
  date: string; // YYYY-MM-DD
  description?: string | null;
  credit_card_id?: number | null;
  is_paid?: boolean;
  currency?: CurrencyType; // v0.3.0 — yoksa backend default (TRY)
}

export interface ExpenseDTO {
  id: number;
  amount: string;
  category: ExpenseCategory;
  date: string;
  description: string | null;
  credit_card_id?: number | null;
  is_paid?: boolean;
  currency?: CurrencyType; // v0.3.0
  amount_tl?: string; // v0.3.0 — işlem-anı kuruyla sabitlenmiş TL karşılığı
}

export interface CategoryBreakdownDTO {
  category: ExpenseCategory;
  total: string;
  count: number;
}

export interface ExpenseSummaryDTO {
  year: number;
  month: number;
  total: string;
  count: number;
  by_category: CategoryBreakdownDTO[];
}

// ─── Income (regular + recurring) ───────────────────────────────

export type IncomeCategory =
  | "salary"
  | "freelance"
  | "rental"
  | "dividend"
  | "bonus"
  | "sale"
  | "other";

export const INCOME_CATEGORIES: IncomeCategory[] = [
  "salary",
  "freelance",
  "rental",
  "dividend",
  "bonus",
  "sale",
  "other",
];

export const INCOME_CATEGORY_LABELS: Record<IncomeCategory, string> = {
  salary: "Maaş",
  freelance: "Serbest Meslek",
  rental: "Kira Geliri",
  dividend: "Temettü / Faiz",
  bonus: "İkramiye / Prim",
  sale: "Varlık Satışı",
  other: "Diğer",
};

export interface IncomeInput {
  amount: number;
  category: IncomeCategory;
  date: string;
  description?: string | null;
  currency?: CurrencyType; // v0.3.0 — yoksa backend default (TRY)
}

export interface IncomeDTO {
  id: number;
  amount: string;
  category: IncomeCategory;
  date: string;
  description: string | null;
  recurring_income_id?: number | null;
  currency?: CurrencyType; // v0.3.0
  amount_tl?: string; // v0.3.0 — işlem-anı kuruyla sabitlenmiş TL karşılığı
}

export interface IncomeCategoryBreakdownDTO {
  category: IncomeCategory;
  total: string;
  count: number;
}

export interface IncomeSummaryDTO {
  year: number;
  month: number;
  total: string;
  count: number;
  by_category: IncomeCategoryBreakdownDTO[];
}

// Periyodik gelir (recurring_incomes)
export type RecurringIncomeCategory =
  | "salary"
  | "rental"
  | "dividend"
  | "bonus"
  | "freelance"
  | "other";
export type RecurringRecurrence =
  | "one_time"
  | "monthly"
  | "quarterly"
  | "biannual"
  | "yearly"
  | "custom";

export const RECURRING_INCOME_CATEGORY_LABELS: Record<RecurringIncomeCategory, string> = {
  salary: "Maaş",
  rental: "Kira Geliri",
  dividend: "Temettü / Faiz",
  bonus: "İkramiye / Prim",
  freelance: "Serbest Meslek",
  other: "Diğer",
};

export const RECURRING_RECURRENCE_LABELS: Record<RecurringRecurrence, string> = {
  one_time: "Tek seferlik",
  monthly: "Aylık",
  quarterly: "3 aylık",
  biannual: "6 aylık",
  yearly: "Yıllık",
  custom: "Özel aylar",
};

export interface RecurringIncomeInput {
  title: string;
  amount: number;
  category: RecurringIncomeCategory;
  recurrence: RecurringRecurrence;
  months?: number[] | null;
  day_of_month: number;
  start_date: string; // YYYY-MM-DD
  end_date?: string | null;
  notes?: string | null;
  currency?: CurrencyType; // v0.3.0 — tahmin; güncel kurla TL'ye çevrilir
}

export interface RecurringIncomeDTO {
  id: number;
  title: string;
  amount: string;
  category: RecurringIncomeCategory;
  recurrence: RecurringRecurrence;
  months: number[] | null;
  day_of_month: number;
  start_date: string;
  end_date: string | null;
  notes: string | null;
  currency?: CurrencyType; // v0.3.0
}

export interface IncomeDashboardDTO {
  year: number;
  month: number;
  this_month_actual: string;
  ytd_actual: string;
  this_month_recurring: string;
  ytd_recurring: string;
  remaining_year_recurring: string;
  year_total_estimate: string;
}

export interface RealizeResultDTO {
  realized: number;
  skipped: number;
  income_ids?: number[]; // gelir realize (income.py)
  ids?: number[]; // gider realize (planned_expenses.py)
}

// ─── Periyodik gerçekleşme (pending / skip) ─────────────────────
export type RecurringKind = "income" | "expense";

export interface PendingItemDTO {
  kind: RecurringKind;
  ref_id: number;
  title: string;
  category: string;
  amount: string;
  period_year: number;
  period_month: number;
  occurrence_date: string; // YYYY-MM-DD
}

export interface PendingResponseDTO {
  items: PendingItemDTO[];
}

// ─── Planlı gider dönem durumu (realize/skip geri alma) ─────────
export type PeriodStatusKind = "pending" | "realized" | "skipped";

export interface PeriodStatusDTO {
  year: number;
  month: number;
  target_date: string; // YYYY-MM-DD
  status: PeriodStatusKind;
  expense_id?: number | null;
  skip_id?: number | null;
}

export interface PeriodsResultDTO {
  periods: PeriodStatusDTO[];
}

export interface UnrealizeResultDTO {
  removed: number;
}

// ─── Periyodik gelir dönem durumu (realize/skip geri alma) ──────
export interface RecurringPeriodStatusDTO {
  year: number;
  month: number;
  target_date: string; // YYYY-MM-DD
  status: PeriodStatusKind;
  income_id?: number | null;
  skip_id?: number | null;
}

export interface RecurringPeriodsResultDTO {
  periods: RecurringPeriodStatusDTO[];
}

export interface RecurringUnrealizeResultDTO {
  removed: number;
}

// ─── Cash Flow (yıllık projeksiyon) ─────────────────────────────

export interface CashFlowMonthDTO {
  month: number;
  income_actual: string;
  income_forecast: string;
  expense_actual: string;
  expense_forecast: string;
  income_total: string;
  expense_total: string;
  net: string;
  is_past: boolean;
}

export interface CashFlowYearDTO {
  year: number;
  months: CashFlowMonthDTO[];
  total_income: string;
  total_expense: string;
  total_net: string;
}

export interface CashFlowItemDTO {
  kind: "actual" | "forecast";
  category: "income" | "expense" | "statement" | "installment" | "recurring_income" | "planned";
  label: string;
  sub_label: string | null;
  date: string | null;
  amount: string;
  currency: string;
  amount_tl: string;
}

export interface CashFlowMonthDetailDTO {
  year: number;
  month: number;
  is_past: boolean;
  is_current: boolean;
  income_items: CashFlowItemDTO[];
  expense_items: CashFlowItemDTO[];
  income_total: string;
  expense_total: string;
  net: string;
}

// ─── Credit Cards ───────────────────────────────────────────────

// Kredi kartları (Faz 3 — manuel giriş)
export interface CreditCardInput {
  name: string;
  bank_name?: string | null;
  last_4?: string | null;
  credit_limit?: DecimalInput;
  statement_day: number;
  payment_due_day: number;
  current_period_debt?: number | string;
  notes?: string | null;
  currency?: CurrencyType; // v0.3.0 — kart para birimi (ekstre/taksit miras alır)
}

export interface CreditCardDTO {
  id: number;
  name: string;
  bank_name: string | null;
  last_4: string | null;
  credit_limit: string | null;
  statement_day: number;
  payment_due_day: number;
  current_period_debt: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
  currency?: CurrencyType; // v0.3.0
  // Hesaplanmış (server-side)
  unpaid_statement_total: string;
  unpaid_statement_count: number;
  future_installment_total: string;
  period_debt: string;
  total_debt: string;
}

export interface CreditCardSummaryDTO {
  cards: CreditCardDTO[];
  total_period_debt: string;
  total_debt: string;
  total_current_period_debt: string; // legacy
}

// Ekstre
export interface StatementInput {
  period_year: number;
  period_month: number;
  statement_amount: number | string;
  statement_date: string; // YYYY-MM-DD
  due_date: string;
  paid_at?: string | null; // ISO datetime
  notes?: string | null;
  currency?: CurrencyType; // v0.3.0 — kart para biriminden miras/override
}

export interface StatementDTO {
  id: number;
  card_id: number;
  period_year: number;
  period_month: number;
  statement_amount: string;
  statement_date: string;
  due_date: string;
  paid_at: string | null;
  notes: string | null;
  created_at: string;
  currency?: CurrencyType; // v0.3.0
}

// Girişte kredi kartı hatırlatmaları (ekstre yükleme + ödeme)
export interface PendingStatementCardDTO {
  card_id: number;
  name: string;
  bank_name: string | null;
  last_4: string | null;
  period_year: number;
  period_month: number;
  cutoff_date: string; // YYYY-MM-DD
}

export interface DuePaymentItemDTO {
  card_id: number;
  card_name: string;
  bank_name: string | null;
  statement_id: number;
  period_year: number;
  period_month: number;
  due_date: string; // YYYY-MM-DD
  statement_amount: string;
  days_until_due: number; // <0 gecikmiş, 0 bugün, >0 yaklaşıyor
}

export interface CreditCardRemindersDTO {
  pending_statements: PendingStatementCardDTO[];
  due_payments: DuePaymentItemDTO[];
}

// Taksit
// total_amount + installments_remaining backend'de otomatik hesaplanır
// (monthly × count = total; first_due_date'ten bugüne kalan = remaining).
export interface InstallmentInput {
  description: string;
  monthly_amount: number | string;
  installments_total: number;
  first_due_date: string;
  notes?: string | null;
  currency?: CurrencyType; // v0.3.0 — kart para biriminden miras/override
}

export interface InstallmentDTO {
  id: number;
  card_id: number;
  description: string;
  total_amount: string;
  monthly_amount: string;
  installments_total: number;
  installments_remaining: number;
  first_due_date: string;
  notes: string | null;
  created_at: string;
  currency?: CurrencyType; // v0.3.0
}

export interface CreditCardDetailDTO {
  card: CreditCardDTO;
  statements: StatementDTO[];
  installments: InstallmentDTO[];
}

// Ekstre (PDF) import — preview çıktısı + commit girdisi
export interface ParsedInstallmentDTO {
  description: string;
  total_amount: string;
  monthly_amount: string;
  installments_total: number;
  installments_paid: number;
  first_due_date: string;
}

export interface ParsedStatementDTO {
  bank_name: string;
  last_4: string | null;
  credit_limit: string | null;
  statement_day: number;
  payment_due_day: number;
  period_year: number;
  period_month: number;
  statement_amount: string;
  statement_date: string;
  due_date: string;
  installments: ParsedInstallmentDTO[];
  matched_card_id: number | null;
  warnings: string[];
}

export interface StatementImportCommitInput {
  target_card_id: number | null;
  name: string;
  bank_name?: string | null;
  last_4?: string | null;
  credit_limit?: number | string | null;
  statement_day: number;
  payment_due_day: number;
  statement: StatementInput;
  installments: InstallmentInput[];
  currency?: CurrencyType; // v0.3.0 — içe aktarılan kartın para birimi
}

// ─── Goal ───────────────────────────────────────────────────────

export type GoalCurrency = "TRY" | "USD" | "EUR" | "GBP";

export const GOAL_CURRENCY_SYMBOLS: Record<GoalCurrency, string> = {
  TRY: "₺",
  USD: "$",
  EUR: "€",
  GBP: "£",
};

export interface GoalDTO {
  goal_amount: string | null;
  goal_currency: GoalCurrency;
  rate_to_tl: string | null;
  monthly_tl: string | null;
  freedom_target_tl: string | null;
  portfolio_value: string | null;
  passive_income_tl: string | null;
  passive_income_foreign: string | null;
  progress_pct: number | null;
  months_covered: number | null;
}

// ─── Planned Expenses + Forecast ────────────────────────────────

export type PlannedCategory =
  | "loan"
  | "tax"
  | "insurance"
  | "subscription"
  | "rent"
  | "utility"
  | "other";
export type PlannedRecurrence =
  | "one_time"
  | "monthly"
  | "quarterly"
  | "biannual"
  | "yearly"
  | "custom";

export const PLANNED_CATEGORY_LABELS: Record<PlannedCategory, string> = {
  loan: "Kredi / Borç",
  tax: "Vergi",
  insurance: "Sigorta",
  subscription: "Abonelik",
  rent: "Kira",
  utility: "Fatura",
  other: "Diğer",
};

export const PLANNED_RECURRENCE_LABELS: Record<PlannedRecurrence, string> = {
  one_time: "Tek seferlik",
  monthly: "Aylık",
  quarterly: "3 aylık",
  biannual: "6 aylık",
  yearly: "Yıllık",
  custom: "Özel aylar",
};

export const PLANNED_CATEGORIES: PlannedCategory[] = [
  "loan",
  "tax",
  "insurance",
  "subscription",
  "rent",
  "utility",
  "other",
];

export const PLANNED_RECURRENCES: PlannedRecurrence[] = [
  "one_time",
  "monthly",
  "quarterly",
  "biannual",
  "yearly",
  "custom",
];

export const MONTH_NAMES = [
  "Ocak",
  "Şubat",
  "Mart",
  "Nisan",
  "Mayıs",
  "Haziran",
  "Temmuz",
  "Ağustos",
  "Eylül",
  "Ekim",
  "Kasım",
  "Aralık",
];

export interface PlannedExpenseInput {
  title: string;
  amount: number;
  is_estimated?: boolean;
  category: PlannedCategory;
  recurrence: PlannedRecurrence;
  months?: number[] | null;
  day_of_month?: number;
  start_date: string; // YYYY-MM-DD
  end_date?: string | null;
  remaining_count?: number | null;
  notes?: string | null;
  credit_card_id?: number | null;
  is_paid?: boolean;
  currency?: CurrencyType; // v0.3.0 — tahmin; güncel kurla TL'ye çevrilir
}

export interface PlannedExpenseDTO {
  id: number;
  title: string;
  amount: string;
  is_estimated: boolean;
  category: PlannedCategory;
  recurrence: PlannedRecurrence;
  months: number[] | null;
  day_of_month: number;
  start_date: string;
  end_date: string | null;
  remaining_count: number | null;
  notes: string | null;
  credit_card_id?: number | null;
  is_paid?: boolean;
  currency?: CurrencyType; // v0.3.0
}

export interface ForecastItemDTO {
  id: number;
  title: string;
  amount: string;
  category: PlannedCategory;
  is_estimated: boolean;
}

export interface ForecastMonthDTO {
  month: number;
  total: string;
  items: ForecastItemDTO[];
}

export interface ForecastResultDTO {
  year: number;
  months: ForecastMonthDTO[];
  year_total: string;
}

// ─── Commodity (Kıymetli madenler) ──────────────────────────────

export type CommodityUnitType = "gram" | "biga" | "coin";
export type CommodityMetal = "gold" | "silver";
export type CoinType = "ceyrek" | "yarim" | "tam" | "cumhuriyet" | "resat" | "ata";

export const BIGA_GOLD_CODES = ["A01", "A02", "A03", "A04", "A05", "A06", "A07", "A08"] as const;
export const BIGA_SILVER_CODES = ["G01", "G02", "G03", "G04", "G05", "G06", "G07"] as const;
export const BIGA_GRAM_WEIGHTS: Record<string, number> = {
  A01: 1,
  A02: 5,
  A03: 10,
  A04: 50,
  A05: 100,
  A06: 250,
  A07: 500,
  A08: 1000,
  G01: 1,
  G02: 5,
  G03: 10,
  G04: 50,
  G05: 100,
  G06: 500,
  G07: 1000,
};
export const COIN_LABELS: Record<CoinType, string> = {
  ceyrek: "Çeyrek Altın (~1.75g)",
  yarim: "Yarım Altın (~3.50g)",
  tam: "Tam Altın (~7.02g)",
  cumhuriyet: "Cumhuriyet Altını (~7.22g)",
  resat: "Reşat Altını (~7.22g)",
  ata: "Ata Altını (~7.22g)",
};
export const COIN_TYPES: CoinType[] = ["ceyrek", "yarim", "tam", "cumhuriyet", "resat", "ata"];

export interface CommodityInput {
  unit_type: CommodityUnitType;
  metal?: CommodityMetal;
  biga_code?: string;
  coin_type?: CoinType;
  quantity: number;
  notes?: string | null;
}

export interface CommodityDTO {
  id: number;
  unit_type: CommodityUnitType;
  metal: CommodityMetal;
  biga_code: string | null;
  coin_type: CoinType | null;
  quantity: string;
  notes: string | null;
  created_at: string;
}

export interface CommodityPositionDTO extends CommodityDTO {
  gram_equivalent: string;
  total_value_tl: string;
  gold_price_tl: string;
  silver_price_tl: string;
}

export interface CommoditySummaryDTO {
  positions: CommodityPositionDTO[];
  total_gold_gram: string;
  total_silver_gram: string;
  total_value_tl: string;
  gold_price_tl: string;
  silver_price_tl: string;
  gold_price_available: boolean;
  silver_price_available: boolean;
}

// ─── Cash (multi-currency) ──────────────────────────────────────

export type CashCurrency = "TRY" | "USD" | "EUR" | "GBP";

export interface CashCreateInput {
  label: string;
  amount: number;
  currency: CashCurrency;
  notes?: string | null;
}

export interface CashDTO {
  id: number;
  label: string;
  amount: string;
  currency: string;
  notes: string | null;
  updated_at: string;
  amount_tl: string;
}

export interface CashSummaryDTO {
  holdings: CashDTO[];
  total_tl: string;
}

// ─── Manual Crypto (API'siz borsalar) ───────────────────────────

// Manuel kripto (API'siz borsalar — BinanceTR, iCrypex vs.)
export type ManualCryptoPriceSource = "auto" | "manual" | "linked";
export type LinkedSource = "binance" | "coingecko" | "tefas" | "commodity";

export interface AssetCatalogItem {
  source: LinkedSource;
  id: string;
  symbol: string | null;
  name: string;
}

export interface ManualCryptoCreateInput {
  exchange: string;
  label?: string | null;
  symbol: string;
  quantity: number | string;
  avg_cost_tl?: DecimalInput;
  price_source?: ManualCryptoPriceSource;
  manual_unit_price_tl?: DecimalInput;
  linked_source?: LinkedSource | null;
  linked_id?: string | null;
  notes?: string | null;
}

export interface ManualCryptoDTO {
  id: number;
  exchange: string;
  label: string | null;
  symbol: string;
  quantity: string;
  avg_cost_tl: string | null;
  price_source: ManualCryptoPriceSource;
  manual_unit_price_tl: string | null;
  linked_source: LinkedSource | null;
  linked_id: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface ManualCryptoPositionDTO {
  id: number;
  exchange: string;
  label: string | null;
  symbol: string;
  quantity: string;
  avg_cost_tl: string | null;
  price_source: ManualCryptoPriceSource;
  manual_unit_price_tl: string | null;
  linked_source: LinkedSource | null;
  linked_id: string | null;
  unit_price_usd: string;
  unit_price_tl: string;
  total_value_tl: string;
  cost_basis_tl: string | null;
  gain_loss_tl: string | null;
  gain_loss_pct: number | null;
  notes: string | null;
}

export interface ManualCryptoSummaryDTO {
  positions: ManualCryptoPositionDTO[];
  total_value_tl: string;
  unknown_symbols: string[];
}

// ─── Budget ─────────────────────────────────────────────────────

export interface BudgetInput {
  amount: number;
  currency?: CurrencyType; // v0.3.0 — tahmin; güncel kurla TL'ye çevrilir
}

export interface BudgetDTO {
  id: number;
  category: string;
  amount: string;
  updated_at: string;
  currency?: CurrencyType; // v0.3.0
}

export interface BudgetComparisonDTO {
  category: string;
  budget_amount: string | null;
  actual_amount: string;
  remaining: string | null;
  pct_used: number | null;
  over_budget: boolean;
  currency?: CurrencyType; // v0.3.0 — bütçe satırının para birimi
}
