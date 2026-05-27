FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --include=dev
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy config as a template — only $API_URL will be substituted at startup,
# all other nginx $variables ($http_host, $remote_addr etc.) are preserved.
COPY nginx.conf /etc/nginx/nginx.conf.template

EXPOSE 80

# Explicitly substitute ONLY $API_URL, leaving all nginx $variables intact.
# Then exec nginx so it is PID 1 and receives signals correctly.
CMD ["/bin/sh", "-c", \
     "envsubst '${API_URL}' < /etc/nginx/nginx.conf.template > /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"]
