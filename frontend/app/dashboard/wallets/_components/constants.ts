export type Chain =
  | "sonic" | "avalanche_c" | "avalanche_p" | "ethereum" | "bitcoin"
  | "solana" | "cardano" | "algorand" | "polkadot" | "litecoin";

export const CHAIN_LABELS: Record<string, string> = {
  sonic: "Sonic (S)",
  avalanche_c: "Avalanche C-Chain",
  avalanche_p: "Avalanche P-Chain",
  ethereum: "Ethereum",
  bitcoin: "Bitcoin",
  solana: "Solana",
  cardano: "Cardano",
  algorand: "Algorand",
  polkadot: "Polkadot",
  litecoin: "Litecoin",
};

export const CHAIN_SYMBOLS: Record<string, string> = {
  sonic: "S",
  avalanche_c: "AVAX",
  avalanche_p: "AVAX",
  ethereum: "ETH",
  bitcoin: "BTC",
  solana: "SOL",
  cardano: "ADA",
  algorand: "ALGO",
  polkadot: "DOT",
  litecoin: "LTC",
};

// Address placeholders and per-chain "how to find your address" hints moved to
// the i18n dictionary (content.wallets.placeholders.* / content.wallets.hints.*)
// and are now read via t() in WalletForm for TR/EN support.
