FROM node:18

WORKDIR /app

COPY ./App /app

RUN npm install --prefix /app

EXPOSE 3000

CMD ["node", "server.js"]
