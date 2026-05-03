"use client";
import { useState } from "react";
import {
  api,
  BIGA_GOLD_CODES, BIGA_SILVER_CODES, BIGA_GRAM_WEIGHTS,
  COIN_LABELS, COIN_TYPES,
  type CommodityUnitType, type CommodityMetal, type CoinType,
} from "@/lib/api";

interface Props {
  onAdded: () => void;
}

export function CommodityForm({ onAdded }: Props) {
  const [unitType, setUnitType] = useState<CommodityUnitType>("coin");
  const [metal, setMetal] = useState<CommodityMetal>("gold");
  const [bigaCode, setBigaCode] = useState("A01");
  const [coinType, setCoinType] = useState<CoinType>("tam");
  const [quantity, setQuantity] = useState("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const bigaCodes = metal === "gold" ? BIGA_GOLD_CODES : BIGA_SILVER_CODES;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const qty = parseFloat(quantity);
    if (!qty || qty <= 0) { setError("Geçerli bir miktar girin"); return; }
    setSaving(true);
    setError("");
    try {
      await api.createCommodity({
        unit_type: unitType,
        metal: unitType === "gram" ? metal : undefined,
        biga_code: unitType === "biga" ? bigaCode : undefined,
        coin_type: unitType === "coin" ? coinType : undefined,
        quantity: qty,
        notes: notes.trim() || null,
      });
      setQuantity("");
      setNotes("");
      onAdded();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kaydedilemedi");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-4">
      <h2 className="text-sm font-semibold text-gray-700">Varlık Ekle</h2>

      {/* Tür seçimi */}
      <div className="flex gap-2">
        {(["coin","gram","biga"] as CommodityUnitType[]).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setUnitType(t)}
            className={`flex-1 py-2 rounded-xl text-sm font-medium border transition-colors ${
              unitType === t
                ? "bg-amber-500 text-white border-amber-500"
                : "border-gray-200 text-gray-600 hover:border-amber-300"
            }`}
          >
            {t === "coin" ? "Sikke" : t === "gram" ? "Gram" : "BiGA"}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap gap-3">
        {/* Gram: metal seçimi */}
        {unitType === "gram" && (
          <select
            value={metal}
            onChange={(e) => setMetal(e.target.value as CommodityMetal)}
            className="flex-1 min-w-[140px] border border-gray-200 rounded-xl px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-amber-400"
          >
            <option value="gold">Altın (gram)</option>
            <option value="silver">Gümüş (gram)</option>
          </select>
        )}

        {/* BiGA: metal + kod seçimi */}
        {unitType === "biga" && (
          <>
            <select
              value={metal}
              onChange={(e) => {
                setMetal(e.target.value as CommodityMetal);
                setBigaCode(e.target.value === "gold" ? "A01" : "G01");
              }}
              className="border border-gray-200 rounded-xl px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-amber-400"
            >
              <option value="gold">Altın</option>
              <option value="silver">Gümüş</option>
            </select>
            <select
              value={bigaCode}
              onChange={(e) => setBigaCode(e.target.value)}
              className="flex-1 min-w-[120px] border border-gray-200 rounded-xl px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-amber-400"
            >
              {bigaCodes.map((c) => (
                <option key={c} value={c}>{c} — {BIGA_GRAM_WEIGHTS[c]}g</option>
              ))}
            </select>
          </>
        )}

        {/* Coin: sikke seçimi */}
        {unitType === "coin" && (
          <select
            value={coinType}
            onChange={(e) => setCoinType(e.target.value as CoinType)}
            className="flex-1 min-w-[200px] border border-gray-200 rounded-xl px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-amber-400"
          >
            {COIN_TYPES.map((c) => (
              <option key={c} value={c}>{COIN_LABELS[c]}</option>
            ))}
          </select>
        )}

        {/* Miktar */}
        <div className="flex items-center border border-gray-200 rounded-xl px-3 py-2 min-w-[120px]">
          <input
            type="number"
            min="0.0001"
            step="0.0001"
            placeholder={unitType === "gram" ? "Gram" : "Adet"}
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            className="flex-1 text-sm text-gray-900 focus:outline-none placeholder:text-gray-400 w-24"
          />
          <span className="text-gray-400 text-sm ml-1">{unitType === "gram" ? "g" : "adet"}</span>
        </div>

        <button
          type="submit"
          disabled={saving}
          className="bg-amber-500 hover:bg-amber-600 disabled:opacity-50 text-white text-sm font-medium px-5 py-2 rounded-xl transition-colors"
        >
          {saving ? "Ekleniyor..." : "Ekle"}
        </button>
      </div>

      <input
        type="text"
        placeholder="Not (opsiyonel — örn. Ziraat Bankası)"
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-amber-400 placeholder:text-gray-400"
      />

      {error && (
        <p className="text-xs text-red-600 bg-red-50 px-3 py-2 rounded-lg">{error}</p>
      )}
    </form>
  );
}
