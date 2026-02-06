const CACHE_NAME = 'weiwuying-parking-v3';
const ASSETS = [
  './',               // 首頁
  './index.html',     
  './weiwuying_parking.geojson',
  './B2-20250921.svg', // 你的 SVG 底圖
  './manifest.json',
  './icon.png',
  // 必須強制快取外部的 Leaflet 資源
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
  'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png' // 如果想留底圖（但離線時這行可能抓不全，建議靠 SVG）
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

// 攔截網路請求，優先回傳快取內容
self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request).then((response) => {
      return response || fetch(event.request);
    })
  );

});
