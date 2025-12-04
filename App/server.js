const http = require('http');

const port = process.env.PORT || 3000;

const server = http.createServer((req, res) => {
  res.end("HAHA I have done it");
});

server.listen(port, () => {
  console.log("Hello from CI/CD v1");
});
