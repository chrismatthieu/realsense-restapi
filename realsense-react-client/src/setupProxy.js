const { createProxyMiddleware } = require('http-proxy-middleware');

/**
 * Dev-only: proxy /api/* to the FastAPI host so the browser loads
 * /api/openapi.json from http://localhost:3000 (same origin → no CORS for the spec).
 *
 * Target is chosen only for this Node process (webpack dev server), not the browser.
 * Do not fall back to REACT_APP_API_URL: that often points at a LAN IP (e.g.
 * http://192.168.0.43:8000) for phone/other clients; on Windows, Node connecting
 * to the same machine via its LAN address frequently hits ETIMEDOUT.
 *
 * - API on this machine: omit override (default http://127.0.0.1:8000).
 * - API on another host only: set in .env.development.local, e.g.
 *     REACT_APP_DEV_PROXY_API=http://192.168.0.43:8000
 *   (Node must be able to TCP-connect to that host:port.)
 */
module.exports = function setupProxy(app) {
  const raw =
    process.env.REACT_APP_DEV_PROXY_API ||
    process.env.DEV_PROXY_API ||
    'http://127.0.0.1:8000';
  const target = raw.replace(/\/$/, '');

  app.use(
    '/api',
    createProxyMiddleware({
      target,
      changeOrigin: true,
      timeout: 120_000,
      proxyTimeout: 120_000,
    })
  );
};
