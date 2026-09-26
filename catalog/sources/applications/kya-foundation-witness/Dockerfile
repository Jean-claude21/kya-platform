FROM nginx:alpine

RUN printf '%s' '<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Application témoin KYA</title><main><h1>Application témoin KYA</h1><p>Recette technique du lanceur du socle.</p></main></html>' > /usr/share/nginx/html/index.html \
    && printf '%s' '{"status":"ok"}' > /usr/share/nginx/html/health

EXPOSE 80
