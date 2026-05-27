FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --include=dev
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf.template
EXPOSE 80

# Substitute $API_URL and $API_HOST only — all other nginx $variables are preserved.
# ACA sets:
#   API_URL=https://ctf-api.internal.<env-domain>  (full internal FQDN with scheme)
#   API_HOST=ctf-api.internal.<env-domain>          (just the hostname for Host header)
# Docker Compose sets:
#   API_URL=http://api:8000
#   API_HOST=api
CMD ["/bin/sh", "-c", \
     "envsubst '$API_URL $API_HOST' < /etc/nginx/nginx.conf.template > /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"]
