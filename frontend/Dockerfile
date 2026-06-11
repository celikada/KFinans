FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# ── builder ───────────────────────────────────────────────────────────────────
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# DEVOPS-018 (FAZ H): NEXT_PUBLIC_* runtime'da etkili degil, build-time'da bake edilir.
# Prod tek host modeli (kfinans.app + path-based ingress): bos string -> goreceli /api/v1
# release.yml --build-arg NEXT_PUBLIC_API_URL="" ile gecirir (default zaten "").
ARG NEXT_PUBLIC_API_URL=""
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

RUN npm run build

# ── runner (production) ───────────────────────────────────────────────────────
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production

# Tek RUN katmanı (SonarQube docker:S7031): (1) OS paketlerini güncelle — Trivy
# HIGH/CRITICAL gate; node:20-alpine'in pinlediği Alpine'de biriken OpenSSL vb.
# CVE'leri yamalar (ör. CVE-2026-45447, libcrypto3/libssl3 3.5.6-r0 → 3.5.7-r0).
# (2) Non-root nextjs user. (3) Global npm/npx kaldır — runtime'da gereksiz
# (CMD "node server.js"); npm CLI bundle'ı (cross-spawn/glob/minimatch/tar
# transitive) HIGH/CRITICAL CVE taşır, saldırı yüzeyini küçültür. root iken,
# USER nextjs'ten ÖNCE.
RUN apk upgrade --no-cache && \
    addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs && \
    rm -rf /usr/local/lib/node_modules/npm /usr/local/bin/npm /usr/local/bin/npx

COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

USER nextjs
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD wget -qO- http://localhost:3000 || exit 1
CMD ["node", "server.js"]
