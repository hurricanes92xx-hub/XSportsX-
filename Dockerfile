FROM node:20-bookworm-slim

WORKDIR /app

ENV NODE_ENV=production
ARG XSPORTSX_BUILD=7.5.2
ENV XSPORTSX_BUILD=$XSPORTSX_BUILD

COPY package*.json ./
RUN npm install --omit=dev

COPY . .

EXPOSE 10000

# Pairing proxy owns the public port and forwards the existing Nuvio layer
# to an internal port while exposing short-lived TV QR pairing endpoints.
ENTRYPOINT ["node", "pairing-proxy.js"]
