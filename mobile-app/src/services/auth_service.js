const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

export async function loginStaff(staff_id, password) {
  try {
    const res = await fetch(`${API_BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ staff_id, password })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Login failed');
    }

    const data = await res.json();
    localStorage.setItem('vigil_token', data.access_token);
    localStorage.setItem('vigil_staff', JSON.stringify(data));
    return data;
  } catch (error) {
    // Offline fallback for active logged-in staff
    const cachedStaff = getStoredStaff();
    if (cachedStaff && cachedStaff.staff_id === staff_id) {
      return cachedStaff;
    }
    throw error;
  }
}

export function getStoredStaff() {
  const staffStr = localStorage.getItem('vigil_staff');
  return staffStr ? JSON.parse(staffStr) : null;
}

export function getStoredToken() {
  return localStorage.getItem('vigil_token');
}

export function logoutStaff() {
  localStorage.removeItem('vigil_token');
  localStorage.removeItem('vigil_staff');
}
