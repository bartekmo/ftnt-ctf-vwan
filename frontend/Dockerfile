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

# Substitute only $API_URL at startup — all other nginx $variables are untouched.
# API_URL is injected as a runtime environment variable by the container platform:
#   ACA:           API_URL=http://ctf-api  (internal DNS, same environment)
#   Docker Compose: API_URL=http://api:8000 (Docker network)
CMD ["/bin/sh", "-c", \
     "envsubst '$API_URL' < /etc/nginx/nginx.conf.template > /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"]
