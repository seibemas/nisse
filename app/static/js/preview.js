/**
 * preview.js — renders a live product card preview in the editor.
 *
 * Usage:
 *   import { renderPreview } from './preview.js';
 *   renderPreview(containerEl, productData);
 *
 * productData shape: { name, price, category, short, tint, photo }
 */

const TINT_COLORS = {
  teal:    '#1F8A72',
  indigo:  '#2C1A6B',
  lime:    '#9BC53D',
  magenta: '#A82E97',
};

/**
 * Render a preview card into `container`.
 * Replaces existing content each call.
 */
export function renderPreview(container, product = {}) {
  const { name, price, category, short, tint = 'teal', photo } = product;
  const tintColor = TINT_COLORS[tint] || TINT_COLORS.teal;

  // Build the card HTML
  // blob: and absolute URLs are used as-is; relative paths get a leading /
  const imgSrc = photo
    ? (/^(blob:|https?:|\/)/i.test(photo) ? photo : '/' + photo)
    : null;
  const imgContent = imgSrc
    ? `<img src="${imgSrc}" alt="${escHtml(name || 'Product')}" loading="lazy">`
    : `<div class="preview-card-placeholder" style="background:${tintColor}">
         <span>photo coming soon</span>
       </div>`;

  const priceCategory = [price, category].filter(Boolean).join(' · ');

  container.innerHTML = `
    <div class="preview-card">
      <div class="preview-card-tint-bar" style="background:${tintColor}"></div>
      <div class="preview-card-img-wrap">
        ${imgContent}
      </div>
      <div class="preview-card-body">
        <div class="preview-card-name">${escHtml(name || 'Product name')}</div>
        <div class="preview-card-meta">${escHtml(priceCategory || '—')}</div>
        <div class="preview-card-short">${escHtml(short || 'Short description will appear here.')}</div>
      </div>
    </div>
  `;
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
