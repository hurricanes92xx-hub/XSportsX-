FROM node:20-bookworm-slim

WORKDIR /app

ENV NODE_ENV=production

COPY package*.json ./
RUN npm install --omit=dev

COPY . .

EXPOSE 10000

# Render is using the Dockerfile, so the container itself must own
# the public Nuvio compatibility layer. Do not bypass bootstrap.js.
ENTRYPOINT ["node", "bootstrap.js"]
