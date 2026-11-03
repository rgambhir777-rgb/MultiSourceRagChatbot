# The web UI image: a multi-stage build.
#
#   stage 1 "build": Node installs the exact dependencies and turns the React code into
#                    plain static files (frontend/dist). Node is only needed for this step.
#   stage 2:         nginx serves those files and forwards /api to the API container.
#
# Only stage 2 ends up in the final image: no Node, no node_modules, no source code.
# That makes the image small (~50 MB instead of ~500 MB) and gives attackers less to work with.
#
# Build (from the project root):  docker compose build frontend
FROM node:24.22.0-alpine AS build
WORKDIR /src
# The lockfile first: `npm ci` is re-run only when dependencies change.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM nginx:1.30.6-alpine
# Our site config replaces nginx's default one.
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/dist /usr/share/nginx/html
# nginx's master process starts as root only to open port 80; the worker processes that
# handle requests run as the unprivileged `nginx` user (set in the base image).
EXPOSE 80
