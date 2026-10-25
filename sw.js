const CACHE_NAME = 'b2-parking-v10';
const ASSETS = [
  './',               // 首頁
  './index.html',
  './instant.html',
  './parking.geojson',      // B2 圖資
  './parking-b1.geojson',   // B1 圖資
  './B2-20260503.svg',      // B2 SVG 底圖
  './B1-20260501-geo.svg',  // B1 SVG 底圖（已對齊 B2）
  './EV.svg',               // 電梯 CI 標示
  './stair.svg',            // 樓梯 CI 標示
  './manifest.json',
  './icon.png',
  // 必須強制快取外部的 Leaflet 資源
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'
];

// 安裝 Service Worker 並快取所有資源
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('正在快取離線資源...');
      return cache.addAll(ASSETS);
    })
  );
  self.skipWaiting();
});

// 啟動時清理舊快取
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))
      );
    })
  );
});

// 攔截網路請求，優先回傳快取內容（忽略 ?t= 等查詢字串，讓 instant.html 離線也能開啟）
self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request, { ignoreSearch: new URL(event.request.url).origin === location.origin }).then((response) => {
      return response || fetch(event.request);
    })
  );

});
