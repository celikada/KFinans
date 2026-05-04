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

export const CHAIN_PLACEHOLDERS: Record<string, string> = {
  sonic: "0x...",
  avalanche_c: "0x...",
  avalanche_p: "P-avax1...",
  ethereum: "0x...",
  bitcoin: "bc1q... / 1... / 3... / xpub... / zpub...",
  solana: "Solana base58 adresi (~44 karakter)",
  cardano: "addr1... veya stake1...",
  algorand: "58 karakterlik büyük harf adres",
  polkadot: "1... ile başlayan SS58 adresi",
  litecoin: "ltc1... veya xpub (Ltub.../Ltpv...)",
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
  solana: {
    format: "Base58 ed25519 public key (~44 karakter)",
    howTo:
      "Ledger Live → Solana hesabı → 'Receive' butonu → açılan ekrandaki adresi kopyalayın. " +
      "Phantom/Solflare cüzdanı için: hesap adresine tıklayın → 'Copy address'.",
  },
  cardano: {
    format: "addr1... (Shelley payment) veya stake1... (stake address — daha iyi)",
    howTo:
      "Ledger Live → Cardano hesabı → 'Receive' butonu → addr1... ile başlayan adres. " +
      "Stake adresi (stake1...) varsa onu tercih edin — tüm türetilmiş adreslerin toplam bakiyesi + " +
      "ödülleri tek seferde gözükür.",
  },
  algorand: {
    format: "58 karakterlik base32 büyük harf adres",
    howTo:
      "Ledger Live → Algorand hesabı → 'Receive' butonu → uzun büyük harf adresi kopyalayın. " +
      "Pera Wallet için: Cüzdan listesi → adres ikonuna tıklayın.",
  },
  polkadot: {
    format: "1 ile başlayan SS58 adresi (~47 karakter)",
    howTo:
      "Ledger Live → Polkadot hesabı → 'Receive' butonu → 1... ile başlayan SS58 adresi. " +
      "Talisman / Polkadot.js cüzdanı için: hesap adı altındaki adresi kopyalayın.",
  },
  litecoin: {
    format: "ltc1... (Native SegWit) veya HD için xpub (Ltub.../Ltpv...)",
    howTo:
      "TEK ADRES için: Ledger Live → Litecoin hesabı → 'Receive' → ltc1... adresi.\n" +
      "HD WALLET (önerilir) için: Ledger Live → Litecoin hesabı → ⚙ ayarlar → 'Edit account' → " +
      "'Show xpub' (Ltub... ile başlar — Litecoin xpub formatı).",
  },
};
