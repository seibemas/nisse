/**
 * api.js — thin fetch wrapper for the Mysma Catalog API
 * All methods return the parsed JSON body (or throw on non-OK).
 */

async function request(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok) {
    let msg = `API error ${res.status}`;
    try {
      const body = await res.json();
      msg = body.detail || body.message || msg;
    } catch (_) {
      // response wasn't JSON — keep default message
    }
    throw new Error(msg);
  }
  return res.json();
}

export const api = {
  /** GET /api/products */
  getProducts() {
    return request('/api/products');
  },

  /** POST /api/products */
  createProduct(data) {
    return request('/api/products', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
  },

  /** GET /api/products/:slug */
  getProduct(slug) {
    return request(`/api/products/${slug}`);
  },

  /** PUT /api/products/:slug */
  updateProduct(slug, data) {
    return request(`/api/products/${slug}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
  },

  /** DELETE /api/products/:slug */
  deleteProduct(slug) {
    return request(`/api/products/${slug}`, { method: 'DELETE' });
  },

  /** POST /api/products/:slug/photo  (multipart) */
  uploadPhoto(slug, file) {
    const fd = new FormData();
    fd.append('file', file);
    return request(`/api/products/${slug}/photo`, {
      method: 'POST',
      body: fd,
    });
  },

  /** GET /api/status */
  getStatus() {
    return request('/api/status');
  },

  /** POST /api/publish */
  publish() {
    return request('/api/publish', { method: 'POST' });
  },

  /** POST /api/publish/stream — returns raw Response for SSE streaming */
  publishStream() {
    return fetch('/api/publish/stream', { method: 'POST' });
  },
};
