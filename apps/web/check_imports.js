
try {
    require.resolve('radix-ui');
    console.log('radix-ui resolved');
} catch (e) {
    console.error('radix-ui failed:', e.message);
}

try {
    require.resolve('sonner');
    console.log('sonner resolved');
} catch (e) {
    console.error('sonner failed:', e.message);
}

try {
    require.resolve('zustand');
    console.log('zustand resolved');
} catch (e) {
    console.error('zustand failed:', e.message);
}

try {
    require.resolve('@tanstack/react-query');
    console.log('@tanstack/react-query resolved');
} catch (e) {
    console.error('@tanstack/react-query failed:', e.message);
}
