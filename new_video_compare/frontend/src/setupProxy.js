/**
 * setupProxy.js — Dynamiczny proxy dla środowisk LIVE i DEV
 *
 * Zgodny z zasadami SOUL.md (sekcja "Architektura środowisk — Zasady portów"):
 *   LIVE frontend (:3000) → backend (:8001)
 *   DEV  frontend (:3001) → backend (:8002)
 *
 * NIE modyfikuj tej logiki bez zgody człowieka.
 */
const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function (app) {
  // Determine backend port based on which frontend port is running
  // process.env.PORT is set when starting: PORT=3001 npm start
  const frontendPort = process.env.PORT || '3000';
  const backendPort = frontendPort === '3001' ? 8002 : 8001;

  console.log(`[Proxy] Frontend port: ${frontendPort} → Backend port: ${backendPort}`);

  app.use(
    '/api',
    createProxyMiddleware({
      target: `http://localhost:${backendPort}`,
      changeOrigin: true,
      logLevel: 'warn',
    })
  );

  app.use(
    '/ws',
    createProxyMiddleware({
      target: `http://localhost:${backendPort}`,
      changeOrigin: true,
      ws: true,
      logLevel: 'warn',
    })
  );

  app.use(
    '/health',
    createProxyMiddleware({
      target: `http://localhost:${backendPort}`,
      changeOrigin: true,
      logLevel: 'warn',
    })
  );
};
