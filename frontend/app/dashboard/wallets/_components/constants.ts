export type Chain = "sonic" | "avalanche_c" | "avalanche_p" | "ethereum" | "bitcoin";

export const CHAIN_LABELS: Record<string, string> = {
  sonic: "Sonic (S)",
  avalanche_c: "Avalanche C-Chain",
  avalanche_p: "Avalanche P-Chain",
  ethereum: "Ethereum",
  bitcoin: "Bitcoin",
};

export const CHAIN_SYMBOLS: Record<string, string> = {
  sonic: "S",
  avalanche_c: "AVAX",
  avalanche_p: "AVAX",
  ethereum: "ETH",
  bitcoin: "BTC",
};
