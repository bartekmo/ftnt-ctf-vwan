# Build context must be the repo root so challenges/ is available.
# docker build -f frontend/Dockerfile .
# (or set context: . in docker-compose / GitHub Actions)

FROM node:20-alpine AS builder
WORKDIR /app

# Install dependencies first (better layer caching)
COPY frontend/package*.json ./
RUN npm ci --include=dev

# Copy frontend source and the challenges directory
COPY frontend/ .
COPY challenges/ ../challenges/

# Copy challenge images into public/ so nginx serves them as static files
RUN find ../challenges -type d -name img | while read d; do \
      slug=$(echo "$d" | sed 's|../challenges/||; s|/img||'); \
      mkdir -p "public/challenges/$slug/img"; \
      cp "$d"/* "public/challenges/$slug/img/"; \
    done || true

RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/nginx.conf.template
EXPOSE 80

CMD ["/bin/sh", "-c", \
     "envsubst '$API_URL $API_HOST' < /etc/nginx/nginx.conf.template > /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"]
