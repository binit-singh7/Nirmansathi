/**
 * NirmanSathi Base Frontend JavaScript Utilities
 */

const API_BASE = '/api/v1';

// Token & Session Storage Keys
const ACCESS_TOKEN_KEY = 'ns_access_token';
const REFRESH_TOKEN_KEY = 'ns_refresh_token';
const USER_KEY = 'ns_user';

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

  options.headers = headers;

  try {
    const response = await fetch(`${API_BASE}${endpoint}`, options);
    
    // Handle 401 Unauthorized
    if (response.status === 401 && !endpoint.includes('/accounts/login/')) {
      clearSession();
      showToast('Session expired. Please log in again.', 'danger');
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
      <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
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
    const roleBadge = user.role === 'CITIZEN' ? 'Citizen' :
                      user.role === 'MUNICIPALITY_OFFICER' ? 'Municipality Officer' :
                      user.role === 'MATERIAL_SUPPLIER' ? 'Supplier' : 'Admin';

    const dashboardUrl = user.role === 'CITIZEN' ? '/dashboard/citizen/' :
                         user.role === 'MUNICIPALITY_OFFICER' ? '/dashboard/officer/' :
                         user.role === 'MATERIAL_SUPPLIER' ? '/dashboard/supplier/' : '/dashboard/admin/';

    // Populate navbar role-specific quick links
    if (userRoleNav) {
      if (user.role === 'CITIZEN') {
        userRoleNav.innerHTML = `
          <li class="nav-item"><a class="nav-link" href="/permits/apply/"><i class="bi bi-file-earmark-plus me-1"></i>Apply Permit</a></li>
          <li class="nav-item"><a class="nav-link" href="/permits/my-applications/"><i class="bi bi-journal-text me-1"></i>My Permits</a></li>
          <li class="nav-item"><a class="nav-link" href="/marketplace/"><i class="bi bi-cart3 me-1"></i>Marketplace</a></li>
          <li class="nav-item"><a class="nav-link" href="/marketplace/orders/"><i class="bi bi-bag-check me-1"></i>My Orders</a></li>
        `;
      } else if (user.role === 'MUNICIPALITY_OFFICER') {
        userRoleNav.innerHTML = `
          <li class="nav-item"><a class="nav-link" href="/dashboard/officer/"><i class="bi bi-check2-square me-1"></i>Permit Review Queue</a></li>
        `;
      } else if (user.role === 'MATERIAL_SUPPLIER') {
        userRoleNav.innerHTML = `
          <li class="nav-item"><a class="nav-link" href="/marketplace/supplier/products/"><i class="bi bi-box-seam me-1"></i>Manage Products</a></li>
          <li class="nav-item"><a class="nav-link" href="/marketplace/supplier/orders/"><i class="bi bi-truck me-1"></i>Supplier Orders</a></li>
        `;
      } else if (user.role === 'ADMIN') {
        userRoleNav.innerHTML = `
          <li class="nav-item"><a class="nav-link" href="/admin-portal/users/"><i class="bi bi-people me-1"></i>Users</a></li>
          <li class="nav-item"><a class="nav-link" href="/admin-portal/locations/"><i class="bi bi-geo-alt me-1"></i>Locations</a></li>
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
          <li><a class="dropdown-item fw-bold" href="${dashboardUrl}"><i class="bi bi-speedometer2 me-2"></i>Dashboard</a></li>
          <li><hr class="dropdown-divider"></li>
          <li><button class="dropdown-item text-danger" id="logoutBtn"><i class="bi bi-box-arrow-right me-2"></i>Logout</button></li>
        </ul>
      </div>
    `;

    document.getElementById('logoutBtn')?.addEventListener('click', () => {
      clearSession();
      showToast('Logged out successfully', 'info');
      setTimeout(() => {
        window.location.href = '/';
      }, 500);
    });
  } else {
    if (userRoleNav) {
      userRoleNav.innerHTML = `
        <li class="nav-item"><a class="nav-link" href="/marketplace/"><i class="bi bi-cart3 me-1"></i>Marketplace</a></li>
      `;
    }
    authNav.innerHTML = `
      <a href="/login/" class="btn btn-outline-light me-2"><i class="bi bi-box-arrow-in-right me-1"></i>Login</a>
      <a href="/register/" class="btn btn-warning fw-semibold"><i class="bi bi-person-plus me-1"></i>Register</a>
    `;
  }

  updateCartBadge();
}

// Cart Badge Count update
function updateCartBadge() {
  const badge = document.getElementById('navCartCount');
  if (!badge) return;
  const user = getUser();
  if (user && getToken()) {
    apiFetch('/marketplace/cart/')
      .then(cart => {
        const count = cart.items ? cart.items.reduce((sum, item) => sum + item.quantity, 0) : 0;
        badge.textContent = count;
        badge.classList.toggle('d-none', count === 0);
      })
      .catch(() => {
        badge.classList.add('d-none');
      });
  } else {
    badge.classList.add('d-none');
  }
}

// DOM Loaded Initializer
document.addEventListener('DOMContentLoaded', () => {
  updateNavbarAuthUI();
});
