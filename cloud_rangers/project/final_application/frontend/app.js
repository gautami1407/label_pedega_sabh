// ============================================================
// LABEL PADEGHA SABH — Shared Frontend Utilities
// ============================================================

function checkAuth() {
    const isLoggedIn = localStorage.getItem('isLoggedIn') === 'true';
    const hasToken = typeof getAccessToken === 'function' && !!getAccessToken();
    const currentPage = window.location.pathname.split('/').pop();
    const protectedPages = [
        'dashboard.html',
        'ai-chat.html',
        'health-profile.html',
        'barcodescanner.html',
    ];

    if ((!isLoggedIn && !hasToken) && protectedPages.includes(currentPage)) {
        window.location.href = 'login.html';
    }
}

function logout() {
    if (confirm('Are you sure you want to logout?')) {
        if (typeof clearAuthSession === 'function') {
            clearAuthSession();
        } else {
            localStorage.clear();
        }
        window.location.href = 'login.html';
    }
}

function getHealthProfile() {
    try {
        return JSON.parse(localStorage.getItem('healthProfile') || '{}');
    } catch {
        return {};
    }
}

document.addEventListener('DOMContentLoaded', () => {
    checkAuth();
});
