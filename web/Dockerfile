# orc-notify-web — production image
#
# Multi-stage build:
#   Stage 1: node:22-alpine builds the Vite SPA (tsc -b && vite build) → /app/dist
#   Stage 2: nginx:alpine serves /app/dist + reverse-proxies /auth, /api, /v1
#            to the backend Captain app `orc-notify` over the swarm overlay network.
#
# Build (on VPS, build context = ./web):
#   docker build -t 127.0.0.1:5000/orc-notify/web:<tag> -f web/Dockerfile web
#
# Captain deploy (manual via Captain v2 API):
#   POST /api/v2/user/apps/appData/orc-notify-web
#   captainDefinitionContent = {schemaVersion: 2, imageName: <tag>, containerHttpPort: 80}

# ── Stage 1: build ────────────────────────────────────────────────────────
FROM node:22-alpine AS builder
WORKDIR /app

# pnpm 11+ enforces minimumReleaseAge=1440min which breaks fresh-dep installs
# (electron-to-chromium + others). Pin pnpm@10.15.0 to match reelant-web precedent.
RUN npm install -g pnpm@10.15.0 --silent \
 && pnpm config set minimum-release-age 0 -g \
 && pnpm --version

# Copy manifests first for cache reuse across rebuilds.
COPY package.json pnpm-lock.yaml ./
RUN CI=true pnpm install --frozen-lockfile

# Copy source + build (type-check + vite bundle → /app/dist).
COPY . .
RUN pnpm exec tsc -b && pnpm exec vite build

# ── Stage 2: nginx ────────────────────────────────────────────────────────
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY ./nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
# nginx:alpine default CMD is "nginx -g 'daemon off;'" — keep it.