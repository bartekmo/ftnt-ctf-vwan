FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --include=dev
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx config as a template — API_HOST is substituted at container start
COPY nginx.conf /etc/nginx/templates/default.conf.template

EXPOSE 80

# nginx:alpine's official image processes /etc/nginx/templates/*.template
# via envsubst automatically before starting nginx — no custom entrypoint needed.
CMD ["nginx", "-g", "daemon off;"]
