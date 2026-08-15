/**
 * Authentication & Session Management Module -- Plan B (bearer tokens)
 * ----------------------------------------------------------------------
 * Handles Signup, Login, Logout, navbar UI syncing, and route protection
 * for the AI Resume Screening & Job Recommendation System.
 */

const AuthApp = {
    // ---- Config ----
    apiBase: 'http://127.0.0.1:5000',
    currentUser: null,

    // localStorage keys. MUST match the key script.js reads for the
    // resume-upload Authorization header.
    TOKEN_KEY: 'resumeai_token',
    USER_KEY: 'resumeai_user',

    // Single, explicit navbar mount point.
    navContainerId: 'navAuthContainer',

    // Guards so repeated init() calls never double-bind listeners.
    _logoutListenerBound: false,
    _formsBound: { login: false, signup: false },

    /**
     * Entry point — wires up everything the current page needs.
     */
    init() {
        this.setupPasswordToggles();
        this.setupLoginForm();
        this.setupSignupForm();
        this.bindLogoutDelegate();
        this.checkSession();
    },

    // -----------------------------------------------------------------
    // TOKEN STORAGE HELPERS
    // -----------------------------------------------------------------

    /** @returns {string|null} the stored bearer token, if any */
    getToken() {
        return localStorage.getItem(this.TOKEN_KEY);
    },

    /**
     * Persist the token + user returned by a successful /login, and
     * update in-memory state to match.
     */
    setSession(token, user) {
        if (token) localStorage.setItem(this.TOKEN_KEY, token);
        if (user) localStorage.setItem(this.USER_KEY, JSON.stringify(user));
        this.currentUser = user || null;
    },

    /** Remove any stored token/user (logout, or an invalid/expired token). */
    clearSession() {
        localStorage.removeItem(this.TOKEN_KEY);
        localStorage.removeItem(this.USER_KEY);
        this.currentUser = null;
    },

    /**
     * Build the Authorization header for an authenticated fetch call.
     * @returns {object} either {Authorization: 'Bearer ...'} or {} if
     *                    there is no stored token.
     */
    authHeader() {
        const token = this.getToken();
        return token ? { 'Authorization': `Bearer ${token}` } : {};
    },

    // -----------------------------------------------------------------
    // SESSION HANDLING
    // -----------------------------------------------------------------

    /**
     * Ask the backend whether the stored token is still valid.
     * @returns {Promise<object|null>} the current user object, or null
     */
    async checkSession() {
        const token = this.getToken();

        if (!token) {
            this.currentUser = null;
            this.updateNavForGuestUser();
            return null;
        }

        try {
            const response = await fetch(`${this.apiBase}/me`, {
                method: 'GET',
                headers: { 'Content-Type': 'application/json', ...this.authHeader() }
            });
            const data = await response.json();

            if (data.success && data.authenticated && data.user) {
                this.currentUser = data.user;
                localStorage.setItem(this.USER_KEY, JSON.stringify(data.user));
                this.updateNavForAuthenticatedUser(data.user);
            } else {
                this.clearSession();
                this.updateNavForGuestUser();
            }
        } catch (err) {
            console.error('Session verification failed:', err);
            this.updateNavForGuestUser();
        }

        return this.currentUser;
    },

    /**
     * Guard for pages that require an authenticated user.
     */
    async protectRoute(redirectTo = 'login.html') {
        const user = this.currentUser || (await this.checkSession());

        if (!user) {
            window.location.href = redirectTo;
            return false;
        }

        return true;
    },

    // -----------------------------------------------------------------
    // NAVBAR RENDERING
    // -----------------------------------------------------------------

    updateNavForGuestUser() {
        const container = document.getElementById(this.navContainerId);
        if (!container) return;

        container.innerHTML = `
            <a href="login.html" class="btn btn-outline-light btn-sm btn-modern">Sign In</a>
            <a href="signup.html" class="btn btn-primary btn-sm btn-modern btn-gradient">Get Started</a>
        `;
    },

    updateNavForAuthenticatedUser(user) {
        const container = document.getElementById(this.navContainerId);
        if (!container) return;

        const fullName = user.full_name || 'User';
        const firstName = fullName.split(' ')[0];

        container.innerHTML = `
            <div class="dropdown">
                <button class="btn btn-outline-light btn-sm btn-modern dropdown-toggle d-flex align-items-center gap-2"
                        type="button" id="userMenuBtn" data-bs-toggle="dropdown" aria-expanded="false">
                    <i class="fas fa-user-circle"></i>
                    <span>${this.escapeHtml(firstName)}</span>
                </button>
                <ul class="dropdown-menu dropdown-menu-end shadow-lg border-0 mt-2" aria-labelledby="userMenuBtn">
                    <li>
                        <div class="dropdown-header">
                            <strong class="d-block text-dark">${this.escapeHtml(fullName)}</strong>
                            <small class="text-muted">${this.escapeHtml(user.email || '')}</small>
                        </div>
                    </li>
                    <li><hr class="dropdown-divider"></li>
                    <li>
                        <a class="dropdown-item text-danger d-flex align-items-center gap-2 logout-btn-trigger" href="#">
                            <i class="fas fa-sign-out-alt"></i> Logout
                        </a>
                    </li>
                </ul>
            </div>
        `;
    },

    bindLogoutDelegate() {
        if (this._logoutListenerBound) return;

        document.addEventListener('click', (e) => {
            const trigger = e.target.closest('.logout-btn-trigger, #logoutBtn');
            if (!trigger) return;

            e.preventDefault();
            this.handleLogout();
        });

        this._logoutListenerBound = true;
    },

    // -----------------------------------------------------------------
    // AUTH ACTIONS
    // -----------------------------------------------------------------

    async handleLogin(email, password) {
        try {
            const response = await fetch(`${this.apiBase}/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });

            const data = await response.json();

            if (response.ok && data.success) {
                this.setSession(data.token, data.user);
            }

            return data;
        } catch (err) {
            console.error('Login error:', err);
            return {
                success: false,
                message: 'Server connection failed. Please try again later.'
            };
        }
    },

    async handleSignup(fullName, email, password) {
        try {
            const response = await fetch(`${this.apiBase}/signup`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ full_name: fullName, email, password })
            });

            return await response.json();
        } catch (err) {
            console.error('Signup error:', err);
            return {
                success: false,
                message: 'Server connection failed. Please try again later.'
            };
        }
    },

    async handleLogout() {
        const token = this.getToken();

        try {
            if (token) {
                await fetch(`${this.apiBase}/logout`, {
                    method: 'GET',
                    headers: this.authHeader()
                });
            }
        } catch (err) {
            console.error('Logout error:', err);
        } finally {
            this.clearSession();
            this.updateNavForGuestUser();
            window.location.href = 'index.html';
        }
    },

    // -----------------------------------------------------------------
    // FORM WIRING
    // -----------------------------------------------------------------

    setupLoginForm() {
        const form = document.getElementById('loginForm');
        if (!form || this._formsBound.login) return;
        this._formsBound.login = true;

        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            const emailInput = document.getElementById('loginEmail');
            const passwordInput = document.getElementById('loginPassword');
            const submitBtn = document.getElementById('loginSubmitBtn');
            const spinner = document.getElementById('loginSpinner');
            const btnText = document.getElementById('loginBtnText');
            const alertBox = document.getElementById('loginAlert');

            this.hideAlert(alertBox);

            const email = emailInput.value.trim();
            const password = passwordInput.value;

            if (!email || !password) {
                this.showAlert(alertBox, 'danger', 'Please fill in all fields.');
                return;
            }

            if (!this.validateEmail(email)) {
                this.showAlert(alertBox, 'danger', 'Please provide a valid email address.');
                return;
            }

            this.setLoading(submitBtn, spinner, btnText, true);

            const data = await this.handleLogin(email, password);

            if (data.success) {
                this.showAlert(alertBox, 'success', 'Login successful! Redirecting...');
                setTimeout(() => {
                    window.location.href = 'index.html#upload';
                }, 1000);
            } else {
                this.showAlert(alertBox, 'danger', data.message || 'Invalid credentials. Please try again.');
                this.setLoading(submitBtn, spinner, btnText, false);
            }
        });
    },

    setupSignupForm() {
        const form = document.getElementById('signupForm');
        if (!form || this._formsBound.signup) return;
        this._formsBound.signup = true;

        const passwordInput = document.getElementById('signupPassword');
        if (passwordInput) {
            passwordInput.addEventListener('input', (e) => {
                this.checkPasswordStrength(e.target.value);
            });
        }

        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            const nameInput = document.getElementById('signupName');
            const emailInput = document.getElementById('signupEmail');
            const passwordEl = document.getElementById('signupPassword');
            const confirmPasswordInput = document.getElementById('signupConfirmPassword');
            const submitBtn = document.getElementById('signupSubmitBtn');
            const spinner = document.getElementById('signupSpinner');
            const btnText = document.getElementById('signupBtnText');
            const alertBox = document.getElementById('signupAlert');

            this.hideAlert(alertBox);

            const fullName = nameInput.value.trim();
            const email = emailInput.value.trim();
            const password = passwordEl.value;
            const confirmPassword = confirmPasswordInput.value;

            if (!fullName || !email || !password || !confirmPassword) {
                this.showAlert(alertBox, 'danger', 'All fields are required.');
                return;
            }

            if (!this.validateEmail(email)) {
                this.showAlert(alertBox, 'danger', 'Please provide a valid email address.');
                return;
            }

            if (password.length < 6) {
                this.showAlert(alertBox, 'danger', 'Password must be at least 6 characters long.');
                return;
            }

            if (password !== confirmPassword) {
                this.showAlert(alertBox, 'danger', 'Passwords do not match.');
                return;
            }

            this.setLoading(submitBtn, spinner, btnText, true);

            const data = await this.handleSignup(fullName, email, password);

            if (data.success) {
                this.showAlert(alertBox, 'success', 'Account created successfully! Redirecting to login...');
                setTimeout(() => {
                    window.location.href = 'login.html';
                }, 1500);
            } else {
                this.showAlert(alertBox, 'danger', data.message || 'Signup failed. Please try again.');
                this.setLoading(submitBtn, spinner, btnText, false);
            }
        });
    },

    setupPasswordToggles() {
        document.addEventListener('click', (e) => {
            const btn = e.target.closest('.toggle-password');
            if (!btn) return;

            const targetId = btn.getAttribute('data-target');
            const input = document.getElementById(targetId);
            if (!input) return;

            const icon = btn.querySelector('i');
            const isHidden = input.type === 'password';

            input.type = isHidden ? 'text' : 'password';

            if (icon) {
                icon.classList.toggle('fa-eye', !isHidden);
                icon.classList.toggle('fa-eye-slash', isHidden);
            }
        });
    },

    // -----------------------------------------------------------------
    // UTILITIES
    // -----------------------------------------------------------------

    checkPasswordStrength(password) {
        const strengthBar = document.getElementById('passwordStrengthBar');
        const strengthText = document.getElementById('passwordStrengthText');
        if (!strengthBar || !strengthText) return;

        let score = 0;
        if (password.length >= 6) score++;
        if (password.length >= 10) score++;
        if (/[A-Z]/.test(password)) score++;
        if (/[0-9]/.test(password)) score++;
        if (/[^A-Za-z0-9]/.test(password)) score++;

        let width = '0%';
        let colorClass = 'bg-danger';
        let label = 'Weak';

        if (password.length === 0) {
            width = '0%';
            label = '';
        } else if (score <= 2) {
            width = '33%';
            colorClass = 'bg-danger';
            label = 'Weak';
        } else if (score <= 4) {
            width = '66%';
            colorClass = 'bg-warning';
            label = 'Medium';
        } else {
            width = '100%';
            colorClass = 'bg-success';
            label = 'Strong';
        }

        strengthBar.style.width = width;
        strengthBar.className = `progress-bar ${colorClass}`;
        strengthText.textContent = label ? `Strength: ${label}` : '';
    },

    validateEmail(email) {
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
    },

    setLoading(button, spinner, text, isLoading) {
        if (!button) return;

        if (isLoading) {
            button.disabled = true;
            if (spinner) spinner.classList.remove('d-none');
            if (text) text.textContent = 'Processing...';
        } else {
            button.disabled = false;
            if (spinner) spinner.classList.add('d-none');
            if (text) text.textContent = button.getAttribute('data-default-text') || 'Submit';
        }
    },

    showAlert(alertElement, type, message) {
        if (!alertElement) return;
        alertElement.className = `alert alert-${type} mb-4`;
        alertElement.textContent = message;
        alertElement.classList.remove('d-none');
    },

    hideAlert(alertElement) {
        if (!alertElement) return;
        alertElement.classList.add('d-none');
    },

    escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }
};

document.addEventListener('DOMContentLoaded', () => {
    AuthApp.init();
});