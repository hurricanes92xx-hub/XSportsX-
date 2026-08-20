FROM node:22-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install --omit=dev
COPY . .
ENV NODE_ENV=production
ENV PORT=7000
EXPOSE 7000
CMD ["node", "render-proxy.js"]
