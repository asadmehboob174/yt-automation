
try {
    const radix = require('radix-ui');
    console.log('radix-ui exports:', Object.keys(radix));
} catch (e) {
    console.error('Failed to require radix-ui:', e.message);
}
