# The single-container image for Modal: the API image + nginx + the built React files.
#
# Why one container? Modal runs one container per function and can't run docker compose, so
# the API and the web server (nginx) have to live together. Qdrant and Postgres are hosted
# elsewhere (Qdrant Cloud, Neon) and reached over the internet; see deploy/README.md.
#
# It reuses the two images docker compose already builds, so nothing is compiled twice:
#   docker compose build
#   docker build -f docker/modal.Dockerfile -t ragbot-modal:local .
#
# API_IMAGE / FRONTEND_IMAGE can point at the Docker Hub copies instead (deploy/README.md).
ARG API_IMAGE=ragbot-api:local
ARG FRONTEND_IMAGE=ragbot-frontend:local

FROM ${FRONTEND_IMAGE} AS ui

FROM ${API_IMAGE}
# The API image ends as the unprivileged appuser; installing nginx needs root.
# (Modal always runs containers as root anyway: it ignores USER.)
USER root

# nginx from Debian's own package repository (same base OS as the API image).
# The default site is removed: it would listen on port 80 and serve nginx's welcome page.
RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx \
    && rm -rf /var/lib/apt/lists/* /etc/nginx/sites-enabled/default

# The built React app from the frontend image: plain static files, no Node.
COPY --from=ui /usr/share/nginx/html /usr/share/nginx/html
COPY deploy/nginx-modal.conf /etc/nginx/conf.d/ragbot.conf
COPY deploy/start_web.py /opt/ragbot/start_web.py

EXPOSE 8080
CMD ["python", "/opt/ragbot/start_web.py"]
