// ============================================================
// LPS API Client — auth, profile, and authenticated requests
// ============================================================

const LPS_API_BASE = (() => {
    const host = window.location.hostname;
    const port = window.location.port;
    if (host === 'localhost' || host === '127.0.0.1') {
        const apiPort = port === '5000' ? '5000' : '8000';
        return `http://${host}:${apiPort}/api`;
    }
    return '/api';
})();

function getAccessToken() {
    return localStorage.getItem('accessToken') || '';
}

function getRefreshToken() {
    return localStorage.getItem('refreshToken') || '';
}

function setAuthSession(authResponse) {
    localStorage.setItem('accessToken', authResponse.access_token);
    localStorage.setItem('refreshToken', authResponse.refresh_token);
    localStorage.setItem('isLoggedIn', 'true');
    localStorage.setItem('loggedInUser', JSON.stringify(authResponse.user));
    localStorage.setItem('userName', authResponse.user.full_name || 'User');
    localStorage.setItem('userEmail', authResponse.user.email || '');
    localStorage.setItem('userTier', authResponse.user.tier || 'free');
}

function clearAuthSession() {
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
    localStorage.removeItem('isLoggedIn');
    localStorage.removeItem('loggedInUser');
    localStorage.removeItem('userName');
    localStorage.removeItem('userEmail');
    localStorage.removeItem('userTier');
}

async function apiRequest(path, options = {}) {
    const headers = Object.assign({ 'Content-Type': 'application/json' }, options.headers || {});
    const token = getAccessToken();
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${LPS_API_BASE}${path}`, {
        ...options,
        headers,
    });

    if (response.status === 401 && getRefreshToken()) {
        const refreshed = await refreshAccessToken();
        if (refreshed) {
            headers['Authorization'] = `Bearer ${getAccessToken()}`;
            return fetch(`${LPS_API_BASE}${path}`, { ...options, headers });
        }
    }

    return response;
}

async function refreshAccessToken() {
    const refreshToken = getRefreshToken();
    if (!refreshToken) return false;

    try {
        const response = await fetch(`${LPS_API_BASE}/v1/auth/refresh`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: refreshToken }),
        });
        if (!response.ok) {
            clearAuthSession();
            return false;
        }
        const data = await response.json();
        setAuthSession(data);
        return true;
    } catch {
        clearAuthSession();
        return false;
    }
}

async function registerUser(payload) {
    const response = await fetch(`${LPS_API_BASE}/v1/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.detail || data.error || 'Registration failed');
    }
    setAuthSession(data);
    return data;
}

async function loginUser(payload) {
    const response = await fetch(`${LPS_API_BASE}/v1/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.detail || data.error || 'Login failed');
    }
    setAuthSession(data);
    return data;
}

async function guestLogin() {
    const response = await fetch(`${LPS_API_BASE}/v1/auth/guest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
    });
    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.detail || data.error || 'Guest login failed');
    }
    setAuthSession(data);
    return data;
}

async function fetchUserProfile() {
    const response = await apiRequest('/v1/users/profile');
    if (!response.ok) {
        throw new Error('Failed to load profile');
    }
    return response.json();
}

async function saveUserProfile(profileData) {
    const payload = {
        age: profileData.age ? parseInt(profileData.age, 10) : null,
        gender: profileData.gender || null,
        allergies: profileData.allergies || [],
        health_conditions: profileData.health_conditions || [],
        dietary_preference: profileData.dietaryPreference || profileData.dietary_preference || null,
        pregnancy_status: !!profileData.pregnancy_status,
        fitness_goals: profileData.fitness_goals || [],
        sensitivities: profileData.sensitivities || null,
        other_allergy: profileData.otherAllergy || null,
        other_diet: profileData.otherDiet || null,
        height: profileData.height ? parseFloat(profileData.height) : null,
        weight: profileData.weight ? parseFloat(profileData.weight) : null,
    };

    const response = await apiRequest('/v1/users/profile', {
        method: 'PUT',
        body: JSON.stringify(payload),
    });
    if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to save profile');
    }
    const saved = await response.json();
    localStorage.setItem('healthProfile', JSON.stringify(mapProfileToLocal(saved)));
    return saved;
}

function mapProfileToLocal(profile) {
    return {
        age: profile.age,
        gender: profile.gender,
        allergies: profile.allergies || [],
        health_conditions: profile.health_conditions || [],
        dietaryPreference: profile.dietary_preference,
        pregnancy_status: profile.pregnancy_status,
        fitness_goals: profile.fitness_goals || [],
        sensitivities: profile.sensitivities,
        otherAllergy: profile.other_allergy,
        otherDiet: profile.other_diet,
        height: profile.height,
        weight: profile.weight,
    };
}
