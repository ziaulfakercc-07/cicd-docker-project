const http = require('http');

const port = process.env.PORT || 3000;

const server = http.createServer((req, res) => {
  res.end("Hello world maam i have done the cicd pipe line project look this right now.");
});

server.listen(port, () => {
  console.log("Hello from CI/CD v1");
});
