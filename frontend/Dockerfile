# syntax=docker/dockerfile:1.7
# ============================================================
# Stage 1 - Dependencies
# ============================================================
FROM node:22-slim AS deps

WORKDIR /app

RUN corepack enable && corepack prepare pnpm@10 --activate

COPY package.json pnpm-lock.yaml ./

RUN --mount=type=cache,target=/root/.local/share/pnpm/store \
    pnpm install --frozen-lockfile

# ============================================================
# Stage 2 - Builder
# ============================================================
FROM node:22-slim AS builder

WORKDIR /app

RUN corepack enable && corepack prepare pnpm@10 --activate

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# The one browser-exposed (NEXT_PUBLIC_) variable in this app (see
# .env.local.example) — Next.js inlines NEXT_PUBLIC_* values into the client
# bundle at build time, so it has to be supplied here, not just at container
# runtime like every other env var this app uses.
ARG NEXT_PUBLIC_WIDGET_API_URL
ENV NEXT_PUBLIC_WIDGET_API_URL=${NEXT_PUBLIC_WIDGET_API_URL}

RUN pnpm build

# ============================================================
# Stage 3 - Runtime
# ============================================================
FROM node:22-slim

ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

WORKDIR /app

RUN groupadd -r app && useradd -r -m -g app app

# output: "standalone" (next.config.ts) traces only the files actually needed
# at runtime — the full node_modules tree never has to ship in this image.
COPY --chown=app:app --from=builder /app/public ./public
COPY --chown=app:app --from=builder /app/.next/standalone ./
COPY --chown=app:app --from=builder /app/.next/static ./.next/static

USER app

EXPOSE 3000

# /api/healthz (src/app/api/healthz/route.ts) — under /api/, so proxy.ts's auth
# gate never intercepts it; the one route this image needs reachable with no
# session cookie for the healthcheck (and an external load balancer) to use.
HEALTHCHECK \
    --interval=30s \
    --timeout=5s \
    --start-period=20s \
    --retries=3 \
CMD node -e "fetch('http://localhost:3000/api/healthz').then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"

CMD ["node", "server.js"]
