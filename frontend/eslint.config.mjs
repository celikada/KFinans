import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
  // KFinans-spesifik kural override'lari (2026-05-21 lint refactor):
  // - react-hooks/set-state-in-effect: React 19 yeni kurali, mevcut 23 yerde
  //   pattern var (token kontrol, snapshot fetch, vb.). Refactor cascading
  //   render riskini azaltir ama davranis fonksiyonel olarak dogru. warn'a
  //   indir; gelecekteki Effect Event API'siyle (React Compiler) toplu
  //   refactor edilecek.
  // - react-hooks/exhaustive-deps: gercek dependency hatasi az; cogu kasitli
  //   "sadece mount'ta calistir" pattern. warn'a indir.
  // - react/no-unescaped-entities: TR metinlerde tirnak/apostrof yaygin
  //   (Şartlar'da, "Kayıt"). HTML entity zorunlulugu UX'i bozar; off.
  {
    rules: {
      "react-hooks/set-state-in-effect": "warn",
      "react-hooks/exhaustive-deps": "warn",
      "react/no-unescaped-entities": "off",
    },
  },
]);

export default eslintConfig;
