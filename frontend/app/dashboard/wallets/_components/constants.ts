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

/**
 * Her zincir için adres formatı + nereden bulunacağı bilgisi.
 * WalletForm'daki (i) tooltip'inde gösterilir.
 */
export const CHAIN_ADDRESS_HINTS: Record<string, { format: string; howTo: string }> = {
  sonic: {
    format: "0x ile başlayan 42 karakterlik EVM adresi",
    howTo:
      "MetaMask veya Rabby cüzdanınızı Sonic ağına bağlayın → hesap adınızın altındaki 0x... adresini kopyalayın. " +
      "Ledger Live'da henüz Sonic resmi destek yok — MetaMask + Ledger entegrasyonu kullanın.",
  },
  avalanche_c: {
    format: "0x ile başlayan 42 karakterlik EVM adresi",
    howTo:
      "Ledger Live → Avalanche C-Chain hesabı → 'Receive' butonu → açılan ekrandaki 0x... adresi. " +
      "MetaMask kullanıyorsanız → Avalanche ağı seçili → hesap adresi.",
  },
  avalanche_p: {
    format: "P-avax1... ile başlayan Bech32 adresi",
    howTo:
      "Avalanche resmi cüzdanı (Core) veya Ledger'la bağlanmış Avalanche Wallet → P-Chain hesabı → adres P-avax1... ile başlar. " +
      "Bu adres staking için kullanılır (validatör delegasyonu).",
  },
  ethereum: {
    format: "0x ile başlayan 42 karakterlik EVM adresi",
    howTo:
      "Ledger Live → Ethereum 1 hesabı → 'Receive' butonu → 0x... adresi. " +
      "MetaMask için: hesap adı altındaki adresi tıklayıp kopyalayın. " +
      "Önemli: ERC-20 token bakiyeleri (USDT, stETH, vb.) bu adres üzerinden taranır.",
  },
  bitcoin: {
    format: "Tek adres (bc1q.../1.../3...) veya HD cüzdan için xpub/zpub",
    howTo:
      "TEK ADRES için: Cüzdan uygulamanızda 'Receive' → bc1q... gösterilir (sadece o adresin bakiyesi).\n" +
      "HD WALLET (önerilir) için: Ledger Live → Bitcoin hesabı → ⚙ ayarlar → 'Edit account' → 'Show xpub' " +
      "(veya Receive ekranında 'Show advanced details' → xpub görünür). " +
      "Native SegWit hesaplarda xpub aslında BIP-84 path'inde olur — KFinans bunu otomatik tespit eder.",
  },
};
