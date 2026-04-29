import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { resolve } from "path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    css: false,
    coverage: {
      provider: "v8",
      reporter: ["text", "html", "lcov"],
      include: ["lib/**", "app/**"],
      exclude: [
        "**/node_modules/**",
        "**/.next/**",
        "**/__tests__/**",
        "**/*.spec.ts",
        "**/*.test.ts",
        "**/*.test.tsx",
        "**/playwright/**",
      ],
      thresholds: {
        lines: 30,
        functions: 30,
        branches: 30,
        statements: 30,
      },
    },
    exclude: ["node_modules", "dist", ".next", "playwright/**"],
  },
  resolve: {
    alias: {
      "@": resolve(__dirname, "./"),
    },
  },
});
