FROM node:22-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install --omit=dev
COPY . .
ENV NODE_ENV=production
ENV PORT=7000
ENV XSPORTSX_INTERNAL_PORT=7099
ENV XSPORTSX_CONFIG_SECRET=xsportsx-v520-stable-config-key
EXPOSE 7000
CMD ["node", "render-proxy.js"]
