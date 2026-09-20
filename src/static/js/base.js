/**
 * NirmanSathi Base Frontend JavaScript Utilities
 */

const API_BASE = '/api/v1';

// Token & Session Storage Keys
const ACCESS_TOKEN_KEY = 'ns_access_token';
const REFRESH_TOKEN_KEY = 'ns_refresh_token';
const USER_KEY = 'ns_user';

// Frontend Translation Helper
function _t(key, defaultText) {
  if (window.NIRMAN_I18N && window.NIRMAN_I18N.t && window.NIRMAN_I18N.t[key]) {
    return window.NIRMAN_I18N.t[key];
  }
  return defaultText !== undefined ? defaultText : key;
}

// Auth Token Helper Functions
function getToken() {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

function setTokens(access, refresh) {
  if (access) localStorage.setItem(ACCESS_TOKEN_KEY, access);
  if (refresh) localStorage.setItem(REFRESH_TOKEN_KEY, refresh);
}

function clearSession() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

function getUser() {
  const userStr = localStorage.getItem(USER_KEY);
  try {
    return userStr ? JSON.parse(userStr) : null;
  } catch (e) {
    return null;
  }
}

function setUser(userObj) {
  if (userObj) {
    localStorage.setItem(USER_KEY, JSON.stringify(userObj));
  }
}

// Authenticated Download URL Helper (appends ?token=<jwt>)
function getAuthDownloadUrl(endpoint) {
  const token = getToken();
  let url = endpoint;
  if (!url.startsWith('http') && !url.startsWith('/api/v1') && !url.startsWith('/media/')) {
    url = `${API_BASE}${url.startsWith('/') ? '' : '/'}${url}`;
  }
  if (!token) return url;
  const separator = url.includes('?') ? '&' : '?';
  return `${url}${separator}token=${encodeURIComponent(token)}`;
}

// Authenticated File Downloader (Fetches blob via Authorization header and initiates download)
async function downloadFileWithAuth(endpoint, defaultFilename = 'document.pdf') {
  const token = getToken();
  let url = endpoint;
  if (!url.startsWith('http') && !url.startsWith('/api/v1') && !url.startsWith('/media/')) {
    url = `${API_BASE}${url.startsWith('/') ? '' : '/'}${url}`;
  }
  const headers = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  try {
    const res = await fetch(url, { headers });
    if (!res.ok) {
      if (res.status === 401) {
        showToast(_t('unauthorized_download', 'Unauthorized to download this document. Please log in.'), 'danger');
        return;
      }
      const data = await res.json().catch(() => ({}));
      throw new Error(data.error || data.detail || `Download failed with status ${res.status}`);
    }

    const blob = await res.blob();
    const disposition = res.headers.get('content-disposition');
    let filename = defaultFilename;
    if (disposition && disposition.includes('filename=')) {
      const match = disposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
      if (match && match[1]) {
        filename = match[1].replace(/['"]/g, '');
      }
    }

    const blobUrl = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = blobUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => window.URL.revokeObjectURL(blobUrl), 10000);
  } catch (err) {
    showToast(err.message || _t('download_failed', 'Failed to download file.'), 'danger');
  }
}

function getCsrfToken() {
  const match = document.cookie.match(/(^|;)\s*csrftoken\s*=\s*([^;]+)/);
  if (match) return decodeURIComponent(match[2]);
  const csrfInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
  return csrfInput ? csrfInput.value : '';
}

// API Fetch Helper
async function apiFetch(endpoint, options = {}) {
  const token = getToken();
  const headers = options.headers || {};

  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  // Include CSRF token if present
  const csrf = getCsrfToken();
  if (csrf && !headers['X-CSRFToken']) {
    headers['X-CSRFToken'] = csrf;
  }

  // Include current language header if available
  if (window.NIRMAN_I18N && window.NIRMAN_I18N.lang) {
    headers['Accept-Language'] = window.NIRMAN_I18N.lang;
  }

  options.headers = headers;

  try {
    const response = await fetch(`${API_BASE}${endpoint}`, options);

    // Handle 401 Unauthorized
    if (response.status === 401 && !endpoint.includes('/accounts/login/')) {
      clearSession();
      showToast(_t('session_expired', 'Session expired. Please log in again.'), 'danger');
      setTimeout(() => {
        window.location.href = '/login/';
      }, 1200);
      throw new Error('Unauthorized');
    }

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      const errorMsg = parseErrorMessage(data) || `Request failed with status ${response.status}`;
      throw new Error(errorMsg);
    }

    return data;
  } catch (err) {
    throw err;
  }
}

// Helper to format DRF error responses
function parseErrorMessage(data) {
  if (!data) return null;
  if (typeof data === 'string') return data;
  if (data.detail) return data.detail;
  if (data.error) return data.error;
  if (data.message) return data.message;
  if (data.non_field_errors) return data.non_field_errors.join(' ');

  // Field errors: { field: ["error message"] }
  const fieldErrors = [];
  for (const [key, val] of Object.entries(data)) {
    if (Array.isArray(val)) {
      fieldErrors.push(`${key}: ${val.join(', ')}`);
    } else if (typeof val === 'string') {
      fieldErrors.push(`${key}: ${val}`);
    }
  }
  return fieldErrors.length > 0 ? fieldErrors.join(' | ') : null;
}

// Toast Notifications
function showToast(message, type = 'success', duration = 3500) {
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const bgClass = type === 'success' ? 'bg-success' : type === 'danger' || type === 'error' ? 'bg-danger' : type === 'warning' ? 'bg-warning text-dark' : 'bg-primary';

  const toastEl = document.createElement('div');
  toastEl.className = `toast align-items-center text-white ${bgClass} border-0 show shadow`;
  toastEl.setAttribute('role', 'alert');
  toastEl.setAttribute('aria-live', 'assertive');
  toastEl.setAttribute('aria-atomic', 'true');

  toastEl.innerHTML = `
    <div class="d-flex">
      <div class="toast-body font-weight-medium">
        ${message}
      </div>
      <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="${_t('close', 'Close')}"></button>
    </div>
  `;

  container.appendChild(toastEl);

  setTimeout(() => {
    toastEl.classList.remove('show');
    setTimeout(() => toastEl.remove(), 400);
  }, duration);
}

// Render dynamic navbar user section based on logged in state
function updateNavbarAuthUI() {
  const user = getUser();
  const authNav = document.getElementById('navbarAuthNav');
  const userRoleNav = document.getElementById('navbarRoleNav');

  if (!authNav) return;

  if (user && getToken()) {
    const roleBadge = user.role === 'CITIZEN' ? _t('citizen', 'Citizen') :
      user.role === 'MUNICIPALITY_OFFICER' ? _t('municipality_officer', 'Municipality Officer') :
        user.role === 'MATERIAL_SUPPLIER' ? _t('supplier', 'Supplier') : _t('admin', 'Admin');

    const dashboardUrl = user.role === 'CITIZEN' ? '/dashboard/citizen/' :
      user.role === 'MUNICIPALITY_OFFICER' ? '/dashboard/officer/' :
        user.role === 'MATERIAL_SUPPLIER' ? '/dashboard/supplier/' : '/dashboard/admin/';

    // Populate navbar role-specific quick links
    if (userRoleNav) {
      if (user.role === 'CITIZEN') {
        userRoleNav.innerHTML = `
          <li class="nav-item"><a class="nav-link" href="/permits/apply/"><i class="bi bi-file-earmark-plus me-1"></i>${_t('apply_permit', 'Apply Permit')}</a></li>
          <li class="nav-item"><a class="nav-link" href="/permits/my-applications/"><i class="bi bi-journal-text me-1"></i>${_t('my_permits', 'My Permits')}</a></li>
          <li class="nav-item"><a class="nav-link" href="/marketplace/"><i class="bi bi-cart3 me-1"></i>${_t('marketplace', 'Marketplace')}</a></li>
          <li class="nav-item"><a class="nav-link" href="/marketplace/orders/"><i class="bi bi-bag-check me-1"></i>${_t('my_orders', 'My Orders')}</a></li>
        `;
      } else if (user.role === 'MUNICIPALITY_OFFICER') {
        userRoleNav.innerHTML = `
          <li class="nav-item"><a class="nav-link" href="/dashboard/officer/"><i class="bi bi-check2-square me-1"></i>${_t('permit_review_queue', 'Permit Review Queue')}</a></li>
        `;
      } else if (user.role === 'MATERIAL_SUPPLIER') {
        userRoleNav.innerHTML = `
          <li class="nav-item"><a class="nav-link" href="/marketplace/supplier/products/"><i class="bi bi-box-seam me-1"></i>${_t('manage_products', 'Manage Products')}</a></li>
          <li class="nav-item"><a class="nav-link" href="/marketplace/supplier/orders/"><i class="bi bi-truck me-1"></i>${_t('supplier_orders', 'Supplier Orders')}</a></li>
        `;
      } else if (user.role === 'ADMIN') {
        userRoleNav.innerHTML = `
          <li class="nav-item"><a class="nav-link" href="/dashboard/admin/"><i class="bi bi-people me-1"></i>${_t('users_roles', 'Users & Roles')}</a></li>
          <li class="nav-item"><a class="nav-link" href="/admin/"><i class="bi bi-gear me-1"></i>${_t('django_admin', 'Django Admin')}</a></li>
        `;
      }
    }

    authNav.innerHTML = `
      <div class="dropdown">
        <button class="btn btn-outline-light dropdown-toggle d-flex align-items-center gap-2" type="button" id="userMenuBtn" data-bs-toggle="dropdown" aria-expanded="false">
          <i class="bi bi-person-circle"></i>
          <span>${user.first_name || user.username || user.email}</span>
          <span class="badge bg-info text-dark ms-1">${roleBadge}</span>
        </button>
        <ul class="dropdown-menu dropdown-menu-end shadow" aria-labelledby="userMenuBtn">
          <li><a class="dropdown-item fw-bold" href="${dashboardUrl}"><i class="bi bi-speedometer2 me-2"></i>${_t('dashboard', 'Dashboard')}</a></li>
          <li><a class="dropdown-item" href="/profile/"><i class="bi bi-person-lines-fill me-2"></i>${_t('my_profile', 'My Profile & Details')}</a></li>
          <li><hr class="dropdown-divider"></li>
          <li><button class="dropdown-item text-danger" id="logoutBtn"><i class="bi bi-box-arrow-right me-2"></i>${_t('logout', 'Logout')}</button></li>
        </ul>
      </div>
    `;

    document.getElementById('logoutBtn')?.addEventListener('click', () => {
      const confirmLogout = window.confirm(_t('confirm_logout', 'Are you sure you want to log out?'));
      if (!confirmLogout) return;

      clearSession();
      showToast(_t('logged_out_success', 'Logged out successfully'), 'info');
      setTimeout(() => {
        window.location.href = '/login/';
      }, 500);
    });
  } else {
    if (userRoleNav) {
      userRoleNav.innerHTML = `
      <li class="nav-item">
        <a class="nav-link" href="/permits/apply/">
          <i class="bi bi-file-earmark-plus me-1"></i>${_t('apply_permit', 'Apply Permit')}
        </a>
      </li>

      <li class="nav-item">
        <a class="nav-link" href="/marketplace/">
          <i class="bi bi-cart3 me-1"></i>${_t('marketplace', 'Marketplace')}
        </a>
      </li>
    `;
    }

    authNav.innerHTML = `
    <a href="/login/" class="btn btn-outline-light me-2">
      <i class="bi bi-box-arrow-in-right me-1"></i>${_t('login', 'Login')}
    </a>
    <a href="/register/" class="btn btn-warning fw-semibold">
      <i class="bi bi-person-plus me-1"></i>${_t('register', 'Register')}
    </a>
  `;
  }

  updateCartBadge();

  // Ensure global marketplace/apply-permit links are not visible to supplier users
  if (user && user.role === 'MATERIAL_SUPPLIER') {
    try {
      document.querySelectorAll('a[href="/marketplace/"], a[href="/permits/apply/"]').forEach(el => {
        // hide instead of remove to preserve DOM structure for other scripts
        el.classList.add('d-none');
      });
    } catch (e) {
      // ignore
    }
  }
}

// Cart Badge Count update
function updateCartBadge() {
  const badge = document.getElementById('navCartCount');
  const globalBadge = document.getElementById('navGlobalCartBadge');
  const cartBtn = document.getElementById('navbarCartBtn');
  const user = getUser();

  if (user && user.role === 'MATERIAL_SUPPLIER') {
    if (cartBtn) cartBtn.classList.add('d-none');
    return;
  }

  // Only show cart button for CITIZEN role
  if (!user || user.role !== 'CITIZEN') {
    if (cartBtn) cartBtn.classList.add('d-none');
    return;
  }

  if (cartBtn) cartBtn.classList.remove('d-none');

  if (user && getToken()) {
    apiFetch('/marketplace/cart/')
      .then(cart => {
        const count = cart.items ? cart.items.reduce((sum, item) => sum + item.quantity, 0) : 0;
        if (badge) {
          badge.textContent = count;
          badge.classList.toggle('d-none', count === 0);
        }
        if (globalBadge) {
          globalBadge.textContent = count;
          globalBadge.classList.toggle('d-none', count === 0);
        }
      })
      .catch(() => {
        if (badge) badge.classList.add('d-none');
        if (globalBadge) globalBadge.classList.add('d-none');
      });
  } else {
    if (badge) badge.classList.add('d-none');
    if (globalBadge) globalBadge.classList.add('d-none');
  }
}

// DOM Loaded Initializer
document.addEventListener('DOMContentLoaded', () => {
  updateNavbarAuthUI();
});
