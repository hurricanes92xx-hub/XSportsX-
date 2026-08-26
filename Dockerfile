FROM node:20-bookworm-slim

WORKDIR /app

ENV NODE_ENV=production
ARG XSPORTSX_BUILD=7.5.2
ENV XSPORTSX_BUILD=$XSPORTSX_BUILD

COPY package*.json ./
RUN npm install --omit=dev

COPY . .

# Expand the runtime sports resolver without adding the source registry or
# event metadata to the Android APK. The patch is deterministic and runs once
# during the container image build.
RUN python3 scripts/patch_public_sports_backend.py

EXPOSE 10000

# Pairing proxy owns the public port and forwards the existing Nuvio layer
# to an internal port while exposing short-lived TV QR pairing endpoints.
ENTRYPOINT ["node", "pairing-proxy.js"]
