FROM node:20-bookworm-slim

WORKDIR /app

ENV NODE_ENV=production

COPY package*.json ./
RUN npm install --omit=dev

COPY . .

EXPOSE 10000

# Force the Render container through the public compatibility proxy.
# This is required for Nuvio's /v527/<token>/manifest.json requests.
ENTRYPOINT ["node", "render-proxy.js"]
