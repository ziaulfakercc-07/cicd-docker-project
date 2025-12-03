const express = require('express');
const app = express();
const port = 80;
const version = process.env.VERSION || 'v1';

app.get('/', (req, res) => {
  res.send(`<h1>Hello from ${version}</h1><p>Full CI/CD Pipeline Working!</p>`);
});

app.listen(port, () => console.log(`App running: ${version}`));