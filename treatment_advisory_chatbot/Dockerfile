FROM node:20-slim

WORKDIR /app

# Improve npm reliability during Docker builds
ENV NPM_CONFIG_FETCH_RETRIES=5
ENV NPM_CONFIG_FETCH_RETRY_MINTIMEOUT=20000
ENV NPM_CONFIG_FETCH_RETRY_MAXTIMEOUT=120000
ENV NPM_CONFIG_FUND=false
ENV NPM_CONFIG_AUDIT=false

COPY package*.json ./

# Install production dependencies
RUN npm install --omit=dev --prefer-online

COPY . .

EXPOSE 8004

CMD ["npm", "start"]