
const http = require('http');

const options = {
    hostname: 'localhost',
    port: 3000,
    path: '/api/videos',
    method: 'GET'
};

const req = http.request(options, (res) => {
    console.log(`STATUS: ${res.statusCode}`);
    res.resume(); // consume response data to free up memory
});

req.on('error', (e) => {
    console.error(`problem with request: ${e.message}`);
    process.exit(1);
});

req.end();
