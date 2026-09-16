# syntax=docker/dockerfile:1.7
FROM node:24.8.0-alpine AS base
ENV PNPM_HOME=/pnpm
ENV PATH=$PNPM_HOME:$PATH
RUN corepack enable
WORKDIR /workspace

FROM base AS dependencies
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps ./apps
COPY packages ./packages
RUN pnpm install --frozen-lockfile

FROM dependencies AS build
COPY . .
ARG APP_NAME
RUN test -n "$APP_NAME" && pnpm --filter "$APP_NAME" build

FROM node:24.8.0-alpine AS runtime
ENV NODE_ENV=production
USER node
WORKDIR /app
ARG APP_PATH
COPY --from=build --chown=node:node /workspace/${APP_PATH}/dist ./dist
CMD ["node", "dist/index.js"]
