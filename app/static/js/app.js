/**
 * app.js — Nisse PWA
 * Hash-based routing, state management, event wiring.
 * Vanilla ES modules, no build step required.
 */

import { api } from './api.js';
import { renderPreview } from './preview.js';

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let currentProducts = [];
let filteredProducts = [];
let currentSlug = null;       // null = new product
let unpublishedCount = 0;
let pendingPhotoFile = null;  // photo selected before product is saved
let currentPhotoPath = null;  // photo path of the product currently in the editor
let autosaveTimer = null;
let isNewProduct = true;

// ---------------------------------------------------------------------------
// DOM refs (resolved after DOMContentLoaded)
// ---------------------------------------------------------------------------
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

let elViewList, elViewEdit;
let elProductList, elSearchInput;
let elFab, elPublishBar, elPublishCount, elPublishBtn;
let elEditorTitle, elBackBtn, elAutosaveIndicator;
let elPhotoPlaceholder, elPhotoImg, elPhotoBtn, elPhotoInput;
let elCardPreview;
let elForm;
let elSaveBtn, elDeleteBtn;
let elTintPicker;
let elConfirmOverlay, elConfirmOk, elConfirmCancel;
let elToast;
let elDetailsToggle, elDetailsBody;
let elPublishProgress, elPublishSteps;

// ---------------------------------------------------------------------------
// Toast
// ---------------------------------------------------------------------------
let toastTimer;
function showToast(msg, type = '') {
  elToast.textContent = msg;
  elToast.className = 'toast show' + (type ? ' ' + type : '');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    elToast.className = 'toast';
  }, 3200);
}

// ---------------------------------------------------------------------------
// View routing
// ---------------------------------------------------------------------------
function showView(name) {
  elViewList.classList.toggle('hidden', name !== 'list');
  elViewEdit.classList.toggle('hidden', name !== 'edit');
  // Scroll list to top on return
  if (name === 'list') {
    elProductList.scrollTop = 0;
  }
}

function navigate(hash) {
  window.location.hash = hash;
}

function handleHashChange() {
  const hash = window.location.hash.replace('#', '') || 'list';

  if (hash === 'list' || hash === '') {
    showView('list');
    loadList(); // refresh list & status each time we return
  } else if (hash === 'new') {
    openEditor(null);
  } else if (hash.startsWith('edit/')) {
    const slug = hash.slice(5);
    openEditor(slug);
  }
}

// ---------------------------------------------------------------------------
// List view
// ---------------------------------------------------------------------------
async function loadList() {
  try {
    const [products, status] = await Promise.all([
      api.getProducts(),
      api.getStatus(),
    ]);
    currentProducts = products;
    filteredProducts = products;
    unpublishedCount = status.unpublished_count;
    renderProductList(products);
    updatePublishBar();
  } catch (err) {
    showToast('Could not load products: ' + err.message, 'error');
    renderProductList([]); // clear shimmer
  }
}

function renderProductList(products) {
  if (products.length === 0) {
    elProductList.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">&#127800;</div>
        <div class="empty-state-text">No products yet — add your first one!</div>
      </div>
    `;
    return;
  }

  elProductList.innerHTML = products.map(p => cardHTML(p)).join('');

  // Attach tap handlers
  elProductList.querySelectorAll('.product-card').forEach(card => {
    card.addEventListener('click', () => {
      navigate('#edit/' + card.dataset.slug);
    });
  });

  // Attach swipe-to-sold handlers
  elProductList.querySelectorAll('.card-swipe-wrapper').forEach(wrapper => {
    const card = wrapper.querySelector('.product-card');
    let startX = 0, startY = 0, isDragging = false;

    wrapper.addEventListener('touchstart', e => {
      const t = e.touches[0];
      startX = t.clientX;
      startY = t.clientY;
      isDragging = false;
    }, { passive: true });

    wrapper.addEventListener('touchmove', e => {
      const t = e.touches[0];
      const dx = t.clientX - startX;
      const dy = t.clientY - startY;
      if (!isDragging && Math.abs(dx) > 8 && Math.abs(dx) > Math.abs(dy)) {
        isDragging = true;
        card.classList.add('is-dragging');
      }
      if (isDragging) {
        e.preventDefault();
        card.style.transform = `translateX(${Math.max(0, dx)}px)`;
      }
    }, { passive: false });

    wrapper.addEventListener('touchend', e => {
      if (!isDragging) return;
      card.classList.remove('is-dragging');
      const dx = e.changedTouches[0].clientX - startX;
      isDragging = false;
      if (dx > 60) {
        e.preventDefault();
        const slug = card.dataset.slug;
        const wasSold = card.classList.contains('is-sold');
        card.style.transform = '';
        api.updateProduct(slug, { sold: !wasSold }).then(() => {
          card.classList.toggle('is-sold', !wasSold);
          const reveal = wrapper.querySelector('.card-swipe-reveal');
          const badge = card.querySelector('.card-sold-badge');
          if (!wasSold) {
            if (!badge) card.querySelector('.card-meta').insertAdjacentHTML('beforeend', '<span class="card-sold-badge">Sold</span>');
            reveal.className = 'card-swipe-reveal unsold-action';
            reveal.textContent = '✓ Mark Unsold';
          } else {
            if (badge) badge.remove();
            reveal.className = 'card-swipe-reveal sold-action';
            reveal.textContent = '✓ Mark Sold';
          }
          const idx = currentProducts.findIndex(p => p.slug === slug);
          if (idx !== -1) currentProducts[idx] = { ...currentProducts[idx], sold: !wasSold };
        }).catch(err => showToast('Could not update: ' + err.message, 'error'));
      } else {
        card.style.transform = '';
      }
    }, { passive: false });
  });
}

function cardHTML(p) {
  const tint = p.tint || 'teal';
  const photoContent = p.photo
    ? `<img src="/${p.photo}" alt="${escHtml(p.name)}" loading="lazy">`
    : `<div class="card-thumb-placeholder" style="background:${tintHex(tint)}">
         <span>coming soon</span>
       </div>`;

  const soldBadge = p.sold
    ? `<span class="card-sold-badge">Sold</span>`
    : '';

  const cardInner = `
    <div class="product-card ${p.sold ? 'is-sold' : ''}" data-slug="${escHtml(p.slug)}" role="button" tabindex="0" aria-label="Edit ${escHtml(p.name)}">
      <div class="card-tint-bar" data-tint="${tint}"></div>
      <div class="card-thumb">${photoContent}</div>
      <div class="card-body">
        <div class="card-name">${escHtml(p.name)}</div>
        <div class="card-meta">
          <span class="card-price">${escHtml(p.price)}</span>
          <span class="card-category-pill" data-tint="${tint}">${escHtml(p.category)}</span>
          ${soldBadge}
        </div>
      </div>
      <div class="card-chevron">›</div>
    </div>
  `;

  return `
    <div class="card-swipe-wrapper">
      <div class="card-swipe-reveal ${p.sold ? 'unsold-action' : 'sold-action'}">${p.sold ? '✓ Mark Unsold' : '✓ Mark Sold'}</div>
      ${cardInner}
    </div>
  `;
}

function tintHex(tint) {
  const map = { teal: '#1F8A72', indigo: '#2C1A6B', lime: '#9BC53D', magenta: '#A82E97' };
  return map[tint] || map.teal;
}

function updatePublishBar() {
  if (unpublishedCount > 0) {
    elPublishBar.classList.remove('hidden');
    elPublishCount.textContent =
      unpublishedCount === 1
        ? '1 unpublished change'
        : `${unpublishedCount} unpublished changes`;
    // Adjust FAB position
    elFab.style.bottom = 'calc(100px + env(safe-area-inset-bottom, 0px))';
  } else {
    elPublishBar.classList.add('hidden');
    elFab.style.bottom = 'calc(20px + env(safe-area-inset-bottom, 0px))';
  }
}

// Search
function handleSearch(e) {
  const q = e.target.value.trim().toLowerCase();
  filteredProducts = q
    ? currentProducts.filter(p => p.name.toLowerCase().includes(q))
    : currentProducts;
  renderProductList(filteredProducts);
}

// Publish
async function handlePublish() {
  elPublishSteps.innerHTML = '';
  elPublishProgress.classList.remove('hidden');
  elPublishProgress.classList.add('show');
  elPublishBtn.disabled = true;

  try {
    const response = await api.publishStream();
    if (!response.ok) {
      throw new Error(`Server error ${response.status}`);
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split('\n\n');
      buffer = parts.pop();
      for (const part of parts) {
        const line = part.trim();
        if (!line.startsWith('data:')) continue;
        try {
          const payload = JSON.parse(line.slice(5).trim());
          renderPublishStep(payload);
          if (payload.done && payload.step === 'done') {
            showToast('Published!', 'success');
            const status = await api.getStatus();
            unpublishedCount = status.unpublished_count;
            updatePublishBar();
            setTimeout(() => elPublishProgress.classList.remove('show'), 3000);
          }
        } catch (_) { /* ignore malformed SSE lines */ }
      }
    }
  } catch (err) {
    showToast('Publish failed: ' + err.message, 'error');
    elPublishProgress.classList.remove('show');
  } finally {
    elPublishBtn.disabled = false;
  }
}

function renderPublishStep(payload) {
  const stepId = 'ps-' + payload.step;
  let el = document.getElementById(stepId);
  if (!el) {
    el = document.createElement('div');
    el.id = stepId;
    el.className = 'publish-step';
    el.innerHTML = '<span class="publish-step-icon"></span><span class="publish-step-msg"></span>';
    elPublishSteps.appendChild(el);
  }
  el.querySelector('.publish-step-msg').textContent = payload.msg;
  if (payload.done) el.classList.add('done');
}

// ---------------------------------------------------------------------------
// Editor view
// ---------------------------------------------------------------------------
async function openEditor(slug) {
  // Reset state
  pendingPhotoFile = null;
  currentSlug = slug;
  isNewProduct = !slug;

  clearAutosave();
  resetForm();
  showView('edit');

  if (slug) {
    // Editing existing
    elEditorTitle.textContent = 'Edit Product';
    elDeleteBtn.classList.remove('hidden');
    try {
      const product = await api.getProduct(slug);
      populateForm(product);
      currentPhotoPath = product.photo || null;
      updatePhotoDisplay(product.photo, product.tint);
      if (product.short || product.long || product.materials || product.care) {
        expandDetails();
      } else {
        collapseDetails();
      }
      refreshPreview();
    } catch (err) {
      showToast('Could not load product: ' + err.message, 'error');
      navigate('#list');
    }
  } else {
    // New product
    elEditorTitle.textContent = 'New Product';
    elDeleteBtn.classList.add('hidden');
    setTint('teal');
    updatePhotoDisplay(null, 'teal');
    collapseDetails();
    refreshPreview();
  }
}

function resetForm() {
  currentPhotoPath = null;
  elForm.reset();
  elAutosaveIndicator.classList.remove('show');
  elAutosaveIndicator.classList.add('hidden');
  // Clear tint selection
  $$('.tint-swatch').forEach(s => s.classList.remove('selected'));
  document.getElementById('f-tint').value = '';
  elPhotoImg.classList.add('hidden');
  elPhotoPlaceholder.classList.remove('hidden');
  elPhotoPlaceholder.removeAttribute('data-tint');
  elPhotoBtn.textContent = '📷 Add photo';
  elCardPreview.innerHTML = '';
}

function populateForm(p) {
  document.getElementById('f-name').value      = p.name || '';
  document.getElementById('f-category').value  = p.category || '';
  document.getElementById('f-price').value     = p.price || '';
  document.getElementById('f-short').value     = p.short || '';
  document.getElementById('f-long').value      = p.long || '';
  document.getElementById('f-materials').value = p.materials || '';
  document.getElementById('f-care').value      = p.care || '';
  document.getElementById('f-sold').checked    = !!p.sold;
  document.getElementById('f-sort-order').value = p.sort_order || 0;
  setTint(p.tint || 'teal');
}

function setTint(tint) {
  $$('.tint-swatch').forEach(s => {
    s.classList.toggle('selected', s.dataset.tint === tint);
  });
  document.getElementById('f-tint').value = tint;
}

function getFormData() {
  const name      = document.getElementById('f-name').value.trim();
  const category  = document.getElementById('f-category').value;
  const price     = document.getElementById('f-price').value.trim();
  const short     = document.getElementById('f-short').value.trim();
  const long      = document.getElementById('f-long').value.trim();
  const materials = document.getElementById('f-materials').value.trim();
  const care      = document.getElementById('f-care').value.trim();
  const tint      = document.getElementById('f-tint').value;
  const sold      = document.getElementById('f-sold').checked;
  const sort_order = parseInt(document.getElementById('f-sort-order').value, 10) || 0;

  return { name, category, price, short, long, materials, care, tint, sold, sort_order };
}

function validateForm(data) {
  const required = ['name', 'category', 'price'];
  const missing = required.filter(k => !data[k]);
  if (missing.length) return `Please fill in: ${missing.join(', ')}`;
  if (!data.price.startsWith('$')) return 'Price must start with $ (e.g. $68)';
  return null;
}

function expandDetails() {
  elDetailsBody.classList.add('open');
  elDetailsToggle.textContent = 'Details ›';
}

function collapseDetails() {
  elDetailsBody.classList.remove('open');
  elDetailsToggle.textContent = 'Add details ›';
}

// Photo display
function updatePhotoDisplay(photoPath, tint) {
  if (photoPath) {
    elPhotoImg.src = '/' + photoPath;
    elPhotoImg.classList.remove('hidden');
    elPhotoPlaceholder.classList.add('hidden');
    elPhotoBtn.textContent = '📷 Change photo';
  } else {
    elPhotoImg.classList.add('hidden');
    elPhotoPlaceholder.classList.remove('hidden');
    elPhotoPlaceholder.dataset.tint = tint || 'teal';
    elPhotoBtn.textContent = '📷 Add photo';
  }
}

// Live preview
function refreshPreview() {
  const data = getFormData();
  // If we have a pending local photo file, show it as blob URL
  let photoVal = pendingPhotoFile
    ? (elPhotoImg.classList.contains('hidden') ? null : elPhotoImg.src)
    : currentPhotoPath;
  renderPreview(elCardPreview, { ...data, photo: photoVal });
}

// Autosave (existing products only)
function scheduleAutosave() {
  if (isNewProduct) return;
  clearAutosave();
  autosaveTimer = setTimeout(performAutosave, 500);
}

function clearAutosave() {
  if (autosaveTimer) {
    clearTimeout(autosaveTimer);
    autosaveTimer = null;
  }
}

async function performAutosave() {
  if (!currentSlug || isNewProduct) return;
  const data = getFormData();
  try {
    await api.updateProduct(currentSlug, data);
    showAutosaveIndicator();
    // Update local cache
    const idx = currentProducts.findIndex(p => p.slug === currentSlug);
    if (idx !== -1) currentProducts[idx] = { ...currentProducts[idx], ...data };
  } catch (err) {
    showToast('Autosave failed: ' + err.message, 'error');
  }
}

function showAutosaveIndicator() {
  elAutosaveIndicator.classList.remove('hidden');
  elAutosaveIndicator.classList.add('show');
  setTimeout(() => {
    elAutosaveIndicator.classList.remove('show');
  }, 1800);
}

// Save (new products)
async function handleSave(e) {
  e.preventDefault();
  const data = getFormData();
  const err = validateForm(data);
  if (err) { showToast(err, 'error'); return; }

  if (!isNewProduct) {
    // Existing product — perform immediate save
    clearAutosave();
    elSaveBtn.classList.add('loading');
    elSaveBtn.disabled = true;
    try {
      await api.updateProduct(currentSlug, data);
      showToast('Saved!', 'success');
      navigate('#list');
    } catch (saveErr) {
      showToast('Save failed: ' + saveErr.message, 'error');
    } finally {
      elSaveBtn.classList.remove('loading');
      elSaveBtn.disabled = false;
    }
    return;
  }

  // New product — POST then optional photo upload
  elSaveBtn.classList.add('loading');
  elSaveBtn.disabled = true;
  try {
    const created = await api.createProduct(data);
    currentSlug = created.slug;

    // Upload queued photo if any
    if (pendingPhotoFile) {
      try {
        await api.uploadPhoto(created.slug, pendingPhotoFile);
        pendingPhotoFile = null;
      } catch (photoErr) {
        showToast('Product saved but photo upload failed: ' + photoErr.message, 'error');
      }
    }

    showToast('Product created!', 'success');
    navigate('#list');
  } catch (saveErr) {
    showToast('Could not create product: ' + saveErr.message, 'error');
  } finally {
    elSaveBtn.classList.remove('loading');
    elSaveBtn.disabled = false;
  }
}

// Delete
function handleDeleteClick() {
  elConfirmOverlay.classList.remove('hidden');
}

async function handleDeleteConfirm() {
  elConfirmOverlay.classList.add('hidden');
  try {
    await api.deleteProduct(currentSlug);
    showToast('Product deleted', 'success');
    navigate('#list');
  } catch (err) {
    showToast('Delete failed: ' + err.message, 'error');
  }
}

// Photo upload
async function handlePhotoChange(e) {
  const file = e.target.files[0];
  if (!file) return;

  if (isNewProduct || !currentSlug) {
    // Queue for after save
    pendingPhotoFile = file;
    // Show local preview
    const blobUrl = URL.createObjectURL(file);
    elPhotoImg.src = blobUrl;
    elPhotoImg.classList.remove('hidden');
    elPhotoPlaceholder.classList.add('hidden');
    elPhotoBtn.textContent = '📷 Change photo';
    refreshPreview();
    return;
  }

  // Existing product — upload immediately
  try {
    const updated = await api.uploadPhoto(currentSlug, file);
    currentPhotoPath = updated.photo || null;
    updatePhotoDisplay(updated.photo, updated.tint);
    // Update cache
    const idx = currentProducts.findIndex(p => p.slug === currentSlug);
    if (idx !== -1) currentProducts[idx] = updated;
    refreshPreview();
    showToast('Photo uploaded!', 'success');
  } catch (err) {
    showToast('Photo upload failed: ' + err.message, 'error');
  }
  // Reset input so same file can be re-selected
  elPhotoInput.value = '';
}

// ---------------------------------------------------------------------------
// Escape helper
// ---------------------------------------------------------------------------
function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ---------------------------------------------------------------------------
// Service Worker registration
// ---------------------------------------------------------------------------
function registerSW() {
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(err => {
      console.warn('SW registration failed:', err);
    });
  }
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
function init() {
  // Resolve DOM refs
  elViewList  = $('#view-list');
  elViewEdit  = $('#view-edit');
  elProductList = $('#product-list');
  elSearchInput = $('#search-input');
  elFab = $('#fab-add');
  elPublishBar = $('#publish-bar');
  elPublishCount = $('#publish-count');
  elPublishBtn = $('#publish-btn');
  elEditorTitle = $('#editor-title');
  elBackBtn = $('#back-btn');
  elAutosaveIndicator = $('#autosave-indicator');
  elPhotoPlaceholder = $('#photo-placeholder');
  elPhotoImg = $('#photo-img');
  elPhotoBtn = $('#photo-btn');
  elPhotoInput = $('#photo-input');
  elCardPreview = $('#card-preview');
  elForm = $('#product-form');
  elSaveBtn = $('#save-btn');
  elDeleteBtn = $('#delete-btn');
  elTintPicker = $('#tint-picker');
  elConfirmOverlay = $('#confirm-overlay');
  elConfirmOk = $('#confirm-ok');
  elConfirmCancel = $('#confirm-cancel');
  elToast = $('#toast');
  elDetailsToggle = $('#details-toggle');
  elDetailsBody = $('#details-body');
  elPublishProgress = $('#publish-progress');
  elPublishSteps = $('#publish-steps');

  // Register service worker
  registerSW();

  // ---- Event listeners ----

  // List view
  elSearchInput.addEventListener('input', handleSearch);
  elFab.addEventListener('click', () => navigate('#new'));
  elPublishBtn.addEventListener('click', handlePublish);

  // Editor view
  elBackBtn.addEventListener('click', () => navigate('#list'));

  // Form field changes → autosave (existing) + live preview
  elForm.addEventListener('input', (e) => {
    // Skip the hidden tint input (handled separately) and sort_order
    if (e.target.name === 'tint' || e.target.name === 'sort_order') return;
    refreshPreview();
    scheduleAutosave();
  });

  // Tint swatches
  elTintPicker.addEventListener('click', (e) => {
    const swatch = e.target.closest('.tint-swatch');
    if (!swatch) return;
    setTint(swatch.dataset.tint);
    refreshPreview();
    scheduleAutosave();
    // Update photo placeholder tint
    const photoPath = elPhotoImg.classList.contains('hidden') ? null : elPhotoImg.src;
    if (!photoPath) {
      elPhotoPlaceholder.dataset.tint = swatch.dataset.tint;
    }
  });

  // Photo
  elPhotoBtn.addEventListener('click', () => elPhotoInput.click());
  elPhotoInput.addEventListener('change', handlePhotoChange);

  // Form submit (new product save or explicit save for existing)
  elForm.addEventListener('submit', handleSave);

  // Details toggle
  elDetailsToggle.addEventListener('click', () => {
    if (elDetailsBody.classList.contains('open')) {
      collapseDetails();
    } else {
      expandDetails();
    }
  });

  // Delete
  elDeleteBtn.addEventListener('click', handleDeleteClick);
  elConfirmOk.addEventListener('click', handleDeleteConfirm);
  elConfirmCancel.addEventListener('click', () => elConfirmOverlay.classList.add('hidden'));

  // Close confirm on overlay click
  elConfirmOverlay.addEventListener('click', (e) => {
    if (e.target === elConfirmOverlay) elConfirmOverlay.classList.add('hidden');
  });

  // Keyboard support for product cards (accessibility)
  elProductList.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      const card = e.target.closest('.product-card');
      if (card) {
        e.preventDefault();
        navigate('#edit/' + card.dataset.slug);
      }
    }
  });

  // Hash routing
  window.addEventListener('hashchange', handleHashChange);

  // Initial route
  handleHashChange();
}

document.addEventListener('DOMContentLoaded', init);
