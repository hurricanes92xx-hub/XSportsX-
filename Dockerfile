FROM node:20-bookworm-slim

WORKDIR /app

ENV NODE_ENV=production
ARG XSPORTSX_BUILD=7.5.1
ENV XSPORTSX_BUILD=$XSPORTSX_BUILD

COPY package*.json ./
RUN npm install --omit=dev

COPY . .

EXPOSE 10000

# Render is using the Dockerfile. Keep the public Nuvio compatibility
# layer as the container entrypoint and make every release produce a
# distinct Docker build layer so an old cached image cannot be reused.
ENTRYPOINT ["node", "bootstrap.js"]
