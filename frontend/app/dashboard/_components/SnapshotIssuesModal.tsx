"use client";
/**
 * FE-003 (FAZ H): Snapshot saglik uyari modal'i.
 * A11Y-001 (FAZ H): useFocusTrap + aria-labelledby/aria-describedby.
 *
 * Snapshot al butonuna tiklandiginda preview endpoint'i issues dondururse
 * kullaniciya uyari listesi gosterilip "yine de kaydet / iptal" secenegi
 * sunulur. page.tsx'ten extract edildi.
 */
import * as React from "react";

import type { SnapshotHealthIssue } from "@/lib/api";
import { useFocusTrap } from "@/app/_hooks/useFocusTrap";


export interface PendingIssues {
  issues: SnapshotHealthIssue[];
  total: number;
}


function fmtTL(val: number) {
  return val.toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}


export function SnapshotIssuesModal({
  pending, onCancel, onConfirm, saving,
}: {
  readonly pending: PendingIssues;
  readonly onCancel: () => void;
  readonly onConfirm: () => void;
  readonly saving: boolean;
}) {
  const warns = pending.issues.filter((i) => (i.level ?? "warn") === "warn");
  const infos = pending.issues.filter((i) => i.level === "info");
  const containerRef = useFocusTrap<HTMLDivElement>(true, onCancel);

  return (
    <div
      role="presentation"
      onClick={(e) => { if (e.target === e.currentTarget) onCancel(); }}
      onKeyDown={(e) => { if (e.key === "Escape") onCancel(); }}
      className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50"
    >
      <div
        ref={containerRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="snapshot-issues-title"
        aria-describedby="snapshot-issues-desc"
        className="bg-white rounded-2xl border border-gray-100 shadow-xl p-6 max-w-lg w-full text-left cursor-default"
      >
        <h3 id="snapshot-issues-title" className="text-base font-semibold text-gray-900 mb-1">
          Snapshot uyarıları
          {warns.length > 0 && <span className="text-amber-600"> · {warns.length} sorun</span>}
          {infos.length > 0 && <span className="text-blue-600"> · {infos.length} bilgi</span>}
        </h3>
        <p id="snapshot-issues-desc" className="text-xs text-gray-600 mb-4">
          Toplam: <span className="font-semibold text-gray-700">{fmtTL(pending.total)} ₺</span>.
          {warns.length > 0 && " Sorunlu kayıtlar var; yine de kaydetmek ister misiniz? "}
          {warns.length === 0 && infos.length > 0 && " Bilgi notları var (manuel/bağlı fiyatlar). "}
          Sorunlar/notlar geçmişte de görünür kalır.
        </p>
        <ul className="space-y-2 max-h-72 overflow-y-auto mb-4">
          {pending.issues.map((iss) => {
            const isInfo = iss.level === "info";
            const key = [
              iss.source, iss.exchange, iss.symbol, iss.chain,
              iss.provider, iss.label, iss.msg,
            ].filter(Boolean).join("|");
            return (
              <li
                key={key}
                className={`rounded-lg px-3 py-2 text-xs border ${
                  isInfo
                    ? "bg-blue-50 border-blue-100"
                    : "bg-amber-50 border-amber-100"
                }`}
              >
                <p className={`font-semibold ${isInfo ? "text-blue-800" : "text-amber-800"}`}>
                  <span aria-hidden="true">{isInfo ? "ⓘ" : "⚠"} </span>
                  <span className="sr-only">{isInfo ? "Bilgi:" : "Uyarı:"} </span>
                  {iss.source}
                  {iss.exchange && ` · ${iss.exchange}`}
                  {iss.symbol && ` · ${iss.symbol}`}
                  {iss.chain && ` · ${iss.chain}`}
                  {iss.provider && ` · ${iss.provider}`}
                  {iss.label && ` · ${iss.label}`}
                </p>
                <p className="text-gray-700 mt-0.5">{iss.msg}</p>
              </li>
            );
          })}
        </ul>
        <div className="flex gap-2 justify-end">
          <button
            type="button"
            onClick={onCancel}
            className="px-4 py-2 border border-gray-200 text-gray-600 text-sm font-medium rounded-lg hover:bg-gray-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
          >
            İptal
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={saving}
            className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-300"
          >
            {saving ? "Kaydediliyor..." : "Yine de kaydet"}
          </button>
        </div>
      </div>
    </div>
  );
}
