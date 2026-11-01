// Shared state and helpers used by every page.
const EXAM_TYPES = ['Viva', 'Practical', 'Project Demo', 'Assessment'];

const store = Vue.reactive({
  token: localStorage.getItem('token') || '',
  role: localStorage.getItem('role') || '',
  name: localStorage.getItem('name') || '',
  toasts: [],
});

function setSession(d) {
  store.token = d.token; store.role = d.role; store.name = d.name;
  localStorage.setItem('token', d.token);
  localStorage.setItem('role', d.role);
  localStorage.setItem('name', d.name);
}

function clearSession() {
  store.token = ''; store.role = ''; store.name = '';
  ['token', 'role', 'name'].forEach(k => localStorage.removeItem(k));
}

function homeFor(role) {
  return { admin: '/admin', examiner: '/examiner', student: '/student' }[role] || '/login';
}

function toast(message, type = 'success') {
  const id = Date.now() + Math.random();
  store.toasts.push({ id, message, type });
  setTimeout(() => { store.toasts = store.toasts.filter(t => t.id !== id); }, 4500);
}

async function api(path, method = 'GET', body = null) {
  const headers = { 'Content-Type': 'application/json' };
  if (store.token) headers['Authorization'] = 'Bearer ' + store.token;
  const res = await fetch('/api' + path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  let data = {};
  try { data = await res.json(); } catch (e) { /* empty body */ }
  if (res.status === 401 && store.token) {
    clearSession();
    window.location.hash = '#/login';
  }
  if (!res.ok) throw new Error(data.error || 'Request failed (' + res.status + ')');
  return data;
}

async function downloadFile(path, filename) {
  const res = await fetch('/api' + path, { headers: { Authorization: 'Bearer ' + store.token } });
  if (!res.ok) {
    let msg = 'Download failed';
    try { msg = (await res.json()).error || msg; } catch (e) { /* ignore */ }
    throw new Error(msg);
  }
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement('a');
  a.href = url; a.download = filename; document.body.appendChild(a); a.click();
  a.remove(); URL.revokeObjectURL(url);
}

function badge(status) {
  const map = {
    'Draft': 'secondary', 'Slot Creation': 'info', 'Booking Open': 'success', 'Closed': 'warning',
    'Completed': 'dark', 'Available': 'success', 'Full': 'warning', 'Cancelled': 'danger',
    'Booked': 'primary', 'Active': 'success', 'Inactive': 'secondary',
  };
  return 'badge bg-' + (map[status] || 'secondary');
}

function fdate(d) { return d || '-'; }
