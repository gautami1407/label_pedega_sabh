// ==========================
// auth.js v2 - Handles registration, login with backend API
// ==========================

document.addEventListener('DOMContentLoaded', function() {

    // --------------------------
    // Password Toggle
    // --------------------------
    function setupToggle(inputId, toggleId) {
        const input = document.getElementById(inputId);
        const toggle = document.getElementById(toggleId);
        if (input && toggle) {
            toggle.addEventListener('click', () => {
                if (input.type === 'password') {
                    input.type = 'text';
                    toggle.innerHTML = '<i class="bi bi-eye-slash"></i>';
                } else {
                    input.type = 'password';
                    toggle.innerHTML = '<i class="bi bi-eye"></i>';
                }
            });
        }
    }

    setupToggle('password', 'togglePassword');
    setupToggle('confirmPassword', 'toggleConfirmPassword');
    setupToggle('loginPassword', 'toggleLoginPassword');

    // --------------------------
    // Password Strength
    // --------------------------
    const passwordInput = document.getElementById('password');
    const strengthIndicator = document.getElementById('passwordStrength');

    if (passwordInput && strengthIndicator) {
        passwordInput.addEventListener('input', function() {
            const password = this.value;
            let strength = 0;

            if (password.length >= 8) strength += 20;
            if (password.length >= 12) strength += 20;
            if (/[a-z]/.test(password)) strength += 15;
            if (/[A-Z]/.test(password)) strength += 15;
            if (/[0-9]/.test(password)) strength += 15;
            if (/[^a-zA-Z0-9]/.test(password)) strength += 15;

            strengthIndicator.className = 'password-strength';

            if (password.length > 0) {
                if (strength < 30) {
                    strengthIndicator.classList.add('weak');
                    strengthIndicator.innerText = 'Weak';
                } else if (strength < 60) {
                    strengthIndicator.classList.add('medium');
                    strengthIndicator.innerText = 'Medium';
                } else {
                    strengthIndicator.classList.add('strong');
                    strengthIndicator.innerText = 'Strong';
                }
            } else {
                strengthIndicator.innerText = '';
            }
        });
    }

    // --------------------------
    // Registration Handler - Uses Backend API
    // --------------------------
    const registerForm = document.getElementById('registerForm');
    if (registerForm) {
        registerForm.addEventListener('submit', async function(e) {
            e.preventDefault();

            const submitBtn = this.querySelector('button[type="submit"]');
            const btnText = submitBtn.querySelector('.btn-text');
            const btnLoader = submitBtn.querySelector('.btn-loader');

            const fullName = document.getElementById('fullName').value.trim();
            const email = document.getElementById('email').value.trim().toLowerCase();
            const password = document.getElementById('password').value;
            const confirmPassword = document.getElementById('confirmPassword').value;
            const termsAccept = document.getElementById('termsAccept').checked;

            // Validation
            if (!fullName || !email || !password || !confirmPassword || !termsAccept) {
                showToast('Please fill all fields and accept terms.', 'warning');
                return;
            }

            if (!isValidEmail(email)) {
                showToast('Please enter a valid email address.', 'warning');
                return;
            }

            if (password.length < 8) {
                showToast('Password must be at least 8 characters long.', 'warning');
                return;
            }

            if (password !== confirmPassword) {
                showToast('Passwords do not match.', 'warning');
                return;
            }

            // Show loading
            btnText.style.display = 'none';
            btnLoader.style.display = 'inline';
            submitBtn.disabled = true;

            try {
                await registerUser(fullName, email, password);
                // Save email to pre-fill on login page
                localStorage.setItem('justRegisteredEmail', email);
                showToast('Registration successful! Redirecting to login...', 'success');
                setTimeout(() => {
                    window.location.href = 'login.html';
                }, 1500);
            } catch (error) {
                showToast(error.message || 'Registration failed. Please try again.', 'error');
                btnText.style.display = 'inline';
                btnLoader.style.display = 'none';
                submitBtn.disabled = false;
            }
        });
    }

    // --------------------------
    // Restore Remember Me email on page load
    // --------------------------
    const loginEmailInput = document.getElementById('loginEmail');
    const rememberMeCheckbox = document.getElementById('rememberMe');
    if (loginEmailInput && rememberMeCheckbox) {
        const savedEmail = localStorage.getItem('rememberedEmail');
        if (savedEmail) {
            loginEmailInput.value = savedEmail;
            rememberMeCheckbox.checked = true;
        }
        // If user just registered and was redirected, pre-fill the email
        const regEmail = localStorage.getItem('justRegisteredEmail');
        if (regEmail) {
            loginEmailInput.value = regEmail;
            localStorage.removeItem('justRegisteredEmail');
        }
    }

    // --------------------------
    // Login Handler - Uses Backend API
    // --------------------------
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', async function(e) {
            e.preventDefault();

            const submitBtn = this.querySelector('button[type="submit"]');
            const btnText = submitBtn.querySelector('.btn-text');
            const btnLoader = submitBtn.querySelector('.btn-loader');

            const email = document.getElementById('loginEmail').value.trim().toLowerCase();
            const password = document.getElementById('loginPassword').value;
            const rememberMe = document.getElementById('rememberMe').checked;

            if (!email || !password) {
                showToast('Please enter both email and password.', 'warning');
                return;
            }

            // Show loading
            btnText.style.display = 'none';
            btnLoader.style.display = 'inline';
            submitBtn.disabled = true;

            try {
                const user = await loginUser(email, password);
                if (rememberMe) {
                    localStorage.setItem('rememberMe', 'true');
                    localStorage.setItem('rememberedEmail', email);
                } else {
                    localStorage.removeItem('rememberedEmail');
                }
                
                showToast(`Welcome back, ${user.full_name}!`, 'success');
                setTimeout(() => {
                    window.location.href = 'dashboard.html';
                }, 1000);
            } catch (error) {
                showToast(error.message || 'Invalid email or password.', 'error');
                btnText.style.display = 'inline';
                btnLoader.style.display = 'none';
                submitBtn.disabled = false;
            }
        });
    }

    // --------------------------
    // Dashboard protection
    // --------------------------
    if (window.location.pathname.includes('dashboard.html')) {
        if (localStorage.getItem('isLoggedIn') !== 'true') {
            window.location.href = 'login.html';
        } else {
            try {
                const userRaw = localStorage.getItem('loggedInUser');
                const user = userRaw ? JSON.parse(userRaw) : null;
                const welcomeEl = document.getElementById('welcomeMessage');
                if (welcomeEl && user && user.full_name) {
                    welcomeEl.innerText = `Welcome, ${user.full_name}!`;
                }
            } catch (e) {
                console.warn('[auth] dashboard user parse error:', e);
            }
        }
    }

    // --------------------------
    // Logout function
    // --------------------------
    window.logout = function() {
        if (confirm('Are you sure you want to logout?')) {
            localStorage.clear();
            window.location.href = 'index.html';
        }
    };

    // --------------------------
    // Helper: Email validation
    // --------------------------
    function isValidEmail(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    }
});

// Dashboard protection & display user info (runs on every page load)
if (window.location.pathname.includes('dashboard.html')) {
    if (localStorage.getItem('isLoggedIn') !== 'true') {
        window.location.href = 'login.html';
    } else {
        try {
            const userRaw = localStorage.getItem('loggedInUser');
            const user = userRaw ? JSON.parse(userRaw) : null;
            const nameEl = document.getElementById('userName');
            const emailEl = document.getElementById('userEmail');

            if (nameEl) nameEl.innerText = (user && user.full_name) ? user.full_name : (localStorage.getItem('userName') || 'User');
            if (emailEl) emailEl.innerText = (user && user.email) ? user.email : (localStorage.getItem('userEmail') || '');
        } catch (e) {
            console.warn('[auth.js] Could not parse loggedInUser:', e);
        }
    }
}