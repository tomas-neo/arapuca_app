// sw.js
self.addEventListener('fetch', function(event) {
    // Apenas deixa a requisição passar (necessário para o Chrome aceitar o PWA)
    event.respondWith(fetch(event.request));
});
