FROM node:20-slim AS build
WORKDIR /app

# Left unset on purpose. The bundle calls the API with relative URLs and nginx
# proxies /api to the backend container, so nothing host-specific gets inlined at
# build time and the same image works on localhost, a VM, or behind a domain.
# Override only when the API is genuinely on another origin.
ARG VITE_API_BASE_URL=""
ARG VITE_WS_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_WS_BASE_URL=$VITE_WS_BASE_URL

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
