import React, { useMemo } from 'react';
import SwaggerUI from 'swagger-ui-react';
import 'swagger-ui-react/swagger-ui.css';

/**
 * OpenAPI / Swagger UI.
 *
 * Development: loads spec from same-origin `/api/openapi.json` (see src/setupProxy.js)
 * so the browser does not cross-origin fetch the spec (avoids CORS on openapi.json).
 *
 * Production: set REACT_APP_API_URL to your API origin (e.g. https://api.example.com).
 *
 * Proxy target (dev, Node only): REACT_APP_DEV_PROXY_API or DEV_PROXY_API; default
 * http://127.0.0.1:8000 (see setupProxy.js — not REACT_APP_API_URL).
 */
const ApiDocsPage = () => {
  const isDev = process.env.NODE_ENV === 'development';

  const specUrl = useMemo(() => {
    if (isDev) {
      return '/api/openapi.json';
    }
    const base = (process.env.REACT_APP_API_URL || '').replace(/\/$/, '');
    if (base) {
      return `${base}/api/openapi.json`;
    }
    if (typeof window !== 'undefined') {
      return `${window.location.origin}/api/openapi.json`;
    }
    return '/api/openapi.json';
  }, [isDev]);

  /** For links to /docs and /redoc (not under /api, not proxied by default). */
  const externalApiBase = useMemo(() => {
    const env = (process.env.REACT_APP_API_URL || '').replace(/\/$/, '');
    if (env) return env;
    if (typeof window !== 'undefined' && isDev) {
      return process.env.REACT_APP_DEV_PROXY_API?.replace(/\/$/, '') || `http://${window.location.hostname}:8000`;
    }
    if (typeof window !== 'undefined') {
      return window.location.origin;
    }
    return 'http://localhost:8000';
  }, [isDev]);

  const requestInterceptor = (req) => {
    try {
      if (req && typeof req === 'object' && 'credentials' in req) {
        req.credentials = 'omit';
      }
      if (
        isDev &&
        typeof window !== 'undefined' &&
        req &&
        typeof req.url === 'string'
      ) {
        const bases = [
          process.env.REACT_APP_DEV_PROXY_API?.replace(/\/$/, ''),
          process.env.REACT_APP_API_URL?.replace(/\/$/, ''),
          'http://127.0.0.1:8000',
          'http://localhost:8000',
        ].filter(Boolean);
        for (const b of bases) {
          if (req.url.startsWith(b)) {
            req.url = `${window.location.origin}${req.url.slice(b.length)}`;
            break;
          }
        }
      }
    } catch {
      /* ignore */
    }
    return req;
  };

  return (
    <div className="container api-docs-page">
      <div className="api-docs-header">
        <h2>REST API — Swagger</h2>
        <p>
          OpenAPI spec:{' '}
          <a href={specUrl} target="_blank" rel="noopener noreferrer">
            {specUrl}
          </a>
          {' · '}
          <a href={`${externalApiBase}/redoc`} target="_blank" rel="noopener noreferrer">
            ReDoc
          </a>
          {' · '}
          <a href={`${externalApiBase}/docs`} target="_blank" rel="noopener noreferrer">
            Backend /docs
          </a>
        </p>
        <p className="api-docs-hint">
          {isDev ? (
            <>
              Dev mode loads the spec via the CRA proxy at <code>/api</code>. The proxy defaults to{' '}
              <code>http://127.0.0.1:8000</code> (API on this machine). It does{' '}
              <strong>not</strong> use <code>REACT_APP_API_URL</code> as the proxy target (LAN URLs often
              time out from Node on Windows). If the API runs on another host, set{' '}
              <code>REACT_APP_DEV_PROXY_API</code> in <code>.env.development.local</code> to a URL your dev
              machine can reach. Keep <code>REACT_APP_API_URL</code> for the browser (e.g. other devices on
              the LAN).
            </>
          ) : (
            <>
              Set <code>REACT_APP_API_URL</code> at build time if the API is not served from the same
              origin.
            </>
          )}
        </p>
      </div>
      <div className="swagger-ui-wrap">
        <SwaggerUI
          url={specUrl}
          docExpansion="list"
          defaultModelsExpandDepth={1}
          tryItOutEnabled
          persistAuthorization
          deepLinking={false}
          requestInterceptor={requestInterceptor}
        />
      </div>
    </div>
  );
};

export default ApiDocsPage;
