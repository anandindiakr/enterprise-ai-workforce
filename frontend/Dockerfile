# ── Stage 1: builder ──────────────────────────────────────────────────────────
# Robust against a stale / wrong-platform node_modules existing on the host
# (e.g. a Windows or partial install left in the build context). We copy the
# source first, then WIPE node_modules and do a clean linux install right before
# building, so `next build` always uses a freshly-installed linux `next` binary.
FROM node:20-alpine AS builder
WORKDIR /app

COPY . .
RUN rm -rf node_modules .next && npm ci --legacy-peer-deps

ARG NEXT_PUBLIC_API_URL=http://localhost:8080
ARG NEXT_PUBLIC_WS_URL=ws://localhost:8080
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_WS_URL=$NEXT_PUBLIC_WS_URL
ENV NEXT_TELEMETRY_DISABLED=1

# Invoke Next.js DIRECTLY via node instead of `npm run build` / the `.bin/next`
# shim. On some VPS kernels/overlay filesystems npm fails to create the
# node_modules/.bin symlinks even though the real `next` package installed fine,
# producing "sh: next: not found" (exit 127). Calling the package's real entry
# file (node_modules/next/dist/bin/next) does not depend on that symlink, so the
# build works regardless of whether bin-linking succeeded.
RUN echo "── node_modules/.bin/next:" && (ls -l node_modules/.bin/next || echo "  (.bin/next MISSING — using direct node invocation)") \
 && echo "── node_modules/next/dist/bin/next:" && ls -l node_modules/next/dist/bin/next \
 && node node_modules/next/dist/bin/next build

# ── Stage 2: runner ───────────────────────────────────────────────────────────
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000
ENV PORT=3000

CMD ["node", "server.js"]
