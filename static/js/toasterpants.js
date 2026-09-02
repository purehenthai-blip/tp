/**
 * ToasterPants — Main JavaScript
 * ================================
 * Client-side utilities, UI helpers, and platform-specific logic.
 * Keeps the bread toasted and the interface smooth. 🍞⚡
 */

'use strict';

// ─── Utility: Get CSRF Token ───────────────────────────────────────────────
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    for (let cookie of document.cookie.split(';')) {
      cookie = cookie.trim();
      if (cookie.startsWith(name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

const csrfToken = getCookie('csrftoken');

// ─── Utility: AJAX POST helper ────────────────────────────────────────────
async function apiPost(url, data = {}) {
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken,
    },
    body: JSON.stringify(data),
  });
  return res.json();
}

// ─── Toast Notification (not the bread kind) ──────────────────────────────
function showToast(message, type = 'success', duration = 3000) {
  const colors = {
    success: 'bg-green-500 text-white',
    error:   'bg-red-500 text-white',
    warning: 'bg-yellow-500 text-black',
    info:    'bg-blue-500 text-white',
  };
  const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };

  const el = document.createElement('div');
  el.className = `tp-toast ${colors[type] || colors.info}`;
  el.innerHTML = `<span>${icons[type] || 'ℹ️'}</span> ${message}`;
  document.body.appendChild(el);

  setTimeout(() => {
    el.style.transition = 'opacity 0.4s';
    el.style.opacity = '0';
    setTimeout(() => el.remove(), 400);
  }, duration);
}

// ─── Copy to Clipboard ────────────────────────────────────────────────────
function copyToClipboard(text, label = 'Copied!') {
  navigator.clipboard.writeText(text).then(() => {
    showToast(`${label} 📋`, 'success', 2000);
  }).catch(() => {
    showToast('Copy failed. Try manually.', 'error');
  });
}

// ─── Confirm Dialog (better than browser default) ─────────────────────────
function tpConfirm(message, onConfirm) {
  if (confirm(message)) {
    onConfirm();
  }
}

// ─── Format crypto amounts ────────────────────────────────────────────────
function formatCrypto(amount, decimals = 8) {
  const n = parseFloat(amount);
  if (isNaN(n)) return '0.00';
  return n.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: decimals,
  });
}

// ─── Countdown Timer (reusable) ────────────────────────────────────────────
class CountdownTimer {
  constructor(endTime, displayEl, onEnd = null) {
    this.endTime = new Date(endTime);
    this.displayEl = displayEl;
    this.onEnd = onEnd;
    this.interval = null;
  }

  start() {
    this.update();
    this.interval = setInterval(() => this.update(), 1000);
  }

  stop() {
    if (this.interval) clearInterval(this.interval);
  }

  update() {
    const now = new Date();
    const diff = Math.max(0, Math.floor((this.endTime - now) / 1000));

    if (diff <= 0) {
      this.displayEl.textContent = '⏰ ENDED';
      this.stop();
      if (this.onEnd) this.onEnd();
      return;
    }

    const h = Math.floor(diff / 3600);
    const m = Math.floor((diff % 3600) / 60);
    const s = diff % 60;

    const formatted = h > 0
      ? `${h}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`
      : `${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;

    this.displayEl.textContent = formatted;

    // Color updates
    this.displayEl.classList.remove('text-green-400','text-yellow-400','text-red-400','auction-timer-critical');
    if (diff < 30)        this.displayEl.classList.add('auction-timer-critical');
    else if (diff < 60)   this.displayEl.classList.add('text-red-400');
    else if (diff < 600)  this.displayEl.classList.add('text-yellow-400');
    else                  this.displayEl.classList.add('text-green-400');
  }
}

// ─── Image preview on file select ─────────────────────────────────────────
function previewImage(input, previewEl) {
  if (input.files && input.files[0]) {
    const reader = new FileReader();
    reader.onload = (e) => {
      if (previewEl) {
        previewEl.src = e.target.result;
        previewEl.classList.remove('hidden');
      }
    };
    reader.readAsDataURL(input.files[0]);
  }
}

// ─── Auto-resize textarea ─────────────────────────────────────────────────
function autoResize(textarea) {
  textarea.style.height = 'auto';
  textarea.style.height = Math.min(textarea.scrollHeight, 300) + 'px';
}

document.addEventListener('DOMContentLoaded', () => {
  // Auto-resize all textareas
  document.querySelectorAll('textarea[data-auto-resize]').forEach(ta => {
    ta.addEventListener('input', () => autoResize(ta));
    autoResize(ta);
  });

  // Initialize any countdown timers on the page
  document.querySelectorAll('[data-countdown]').forEach(el => {
    const endTime = el.dataset.countdown;
    if (endTime) {
      const timer = new CountdownTimer(endTime, el);
      timer.start();
    }
  });

  // Copy buttons (data-copy attribute)
  document.querySelectorAll('[data-copy]').forEach(btn => {
    btn.addEventListener('click', () => {
      copyToClipboard(btn.dataset.copy, btn.dataset.copyLabel || 'Copied');
    });
  });

  // Dismiss flash messages after 5 seconds
  setTimeout(() => {
    const flashContainer = document.getElementById('flash-messages');
    if (flashContainer) {
      flashContainer.style.transition = 'opacity 0.5s';
      flashContainer.style.opacity = '0';
      setTimeout(() => flashContainer.remove(), 500);
    }
  }, 5000);

  // Re-init Lucide icons after any dynamic content loads
  if (window.lucide) lucide.createIcons();
});

// ─── Lazy load images ─────────────────────────────────────────────────────
if ('IntersectionObserver' in window) {
  const imgObserver = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        const img = e.target;
        if (img.dataset.src) {
          img.src = img.dataset.src;
          img.removeAttribute('data-src');
        }
        imgObserver.unobserve(img);
      }
    });
  });
  document.querySelectorAll('img[data-src]').forEach(img => imgObserver.observe(img));
}

// ─── File Manager selection (multi-select) ────────────────────────────────
let selectedFiles = new Set();

function toggleFileSelect(el, id) {
  if (selectedFiles.has(id)) {
    selectedFiles.delete(id);
    el.classList.remove('selected');
  } else {
    selectedFiles.add(id);
    el.classList.add('selected');
  }
  updateBulkActions();
}

function updateBulkActions() {
  const bar = document.getElementById('bulk-action-bar');
  const count = document.getElementById('selected-count');
  if (!bar) return;
  if (selectedFiles.size > 0) {
    bar.classList.remove('hidden');
    if (count) count.textContent = selectedFiles.size;
  } else {
    bar.classList.add('hidden');
  }
}

// ─── Wallet: quick deposit request ────────────────────────────────────────
function requestDepositConfirmation(currency) {
  const txHash = document.getElementById('tx-hash-' + currency)?.value;
  if (!txHash) {
    showToast('Please enter your transaction hash', 'warning');
    return;
  }
  showToast('Deposit request submitted! Admin will confirm shortly. 🍞', 'success');
}

// ─── Expose globals ──────────────────────────────────────────────────────
window.TP = {
  showToast,
  copyToClipboard,
  formatCrypto,
  CountdownTimer,
  getCookie,
  apiPost,
};
