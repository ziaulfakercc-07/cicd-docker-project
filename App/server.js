const http = require('http');

const port = process.env.PORT || 3000;

const server = http.createServer((req, res) => {
  res.end("hello every one! How are you doing.");
});

server.listen(port, () => {
  console.log("Hello from CI/CD v1");
});
