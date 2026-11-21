# Multi-stage build for SwiftletCare Frontend
# Stage 1: Build
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies first for layer caching
COPY package.json package-lock.json ./
RUN npm ci

# Copy application source
COPY . ./

# Build production bundle (default to same-origin /api via Nginx unless overridden)
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
# INT03-R2: Optional Firebase Web Push public client config (safe to leave empty when disabled)
ARG VITE_FIREBASE_API_KEY=""
ARG VITE_FIREBASE_AUTH_DOMAIN=""
ARG VITE_FIREBASE_PROJECT_ID=""
ARG VITE_FIREBASE_MESSAGING_SENDER_ID=""
ARG VITE_FIREBASE_APP_ID=""
ARG VITE_FIREBASE_VAPID_KEY=""
ENV VITE_FIREBASE_API_KEY=${VITE_FIREBASE_API_KEY}
ENV VITE_FIREBASE_AUTH_DOMAIN=${VITE_FIREBASE_AUTH_DOMAIN}
ENV VITE_FIREBASE_PROJECT_ID=${VITE_FIREBASE_PROJECT_ID}
ENV VITE_FIREBASE_MESSAGING_SENDER_ID=${VITE_FIREBASE_MESSAGING_SENDER_ID}
ENV VITE_FIREBASE_APP_ID=${VITE_FIREBASE_APP_ID}
ENV VITE_FIREBASE_VAPID_KEY=${VITE_FIREBASE_VAPID_KEY}
RUN npm run build

# Stage 2: Production Nginx Server
FROM nginx:alpine

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy compiled assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

# Health check probe
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://127.0.0.1/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
