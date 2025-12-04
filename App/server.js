const http = require('http'); 
const port = process.env.PORT || 3000; 
const server = http.createServer((req, res) => { 
res.end("CI/CD Pipeline with Docker and GitHub Actions - Version 1"); 
}); 
server.listen(port, () => { 
console.log(`Server running on port ${port}`); 
});