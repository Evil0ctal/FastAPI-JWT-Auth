const API_BASE_URL = '/api/v1';

// Check if demo mode
async function checkDemoMode() {
    try {
        const response = await fetch(`${API_BASE_URL}/demo-mode`);
        if (response.ok) {
            const data = await response.json();
            if (data.is_demo) {
                const demoAlert = document.getElementById('demoAlert');
                if (demoAlert) {
                    demoAlert.style.display = 'block';
                }
            }
        }
    } catch (error) {
        console.error('Error checking demo mode:', error);
    }
}

// Show alert message
function showAlert(message, type = 'error') {
    const alert = document.getElementById('alert');
    alert.className = `alert alert-${type}`;
    alert.textContent = message;
    alert.style.display = 'block';
    
    setTimeout(() => {
        alert.style.display = 'none';
    }, 5000);
}

// Handle login form submission
document.getElementById('loginForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const formData = new FormData(e.target);
    const loginData = {
        email: formData.get('email'),
        password: formData.get('password')
    };
    
    try {
        const response = await fetch(`${API_BASE_URL}/auth/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(loginData)
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // Store tokens in localStorage
            localStorage.setItem('access_token', data.access_token);
            localStorage.setItem('refresh_token', data.refresh_token);
            showAlert('Login successful! Redirecting...', 'success');
            
            // Redirect to dashboard
            setTimeout(() => {
                window.location.href = '/static/dashboard.html';
            }, 1000);
        } else {
            showAlert(data.detail || 'Login failed');
        }
    } catch (error) {
        showAlert('Network error. Please try again.');
        console.error('Login error:', error);
    }
});

// Handle register form submission
document.getElementById('registerForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const formData = new FormData(e.target);
    
    // Check if passwords match
    if (formData.get('password') !== formData.get('confirm_password')) {
        showAlert('Passwords do not match');
        return;
    }
    
    const registerData = {
        email: formData.get('email'),
        username: formData.get('username'),
        password: formData.get('password'),
        full_name: formData.get('full_name') || null,
        phone: formData.get('phone') || null
    };
    
    try {
        const response = await fetch(`${API_BASE_URL}/auth/register`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(registerData)
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showAlert('Registration successful! Please log in.', 'success');
            
            // Redirect to login page
            setTimeout(() => {
                window.location.href = '/static/login.html';
            }, 2000);
        } else {
            showAlert(data.detail || 'Registration failed');
        }
    } catch (error) {
        showAlert('Network error. Please try again.');
        console.error('Registration error:', error);
    }
});

// Check if user is already logged in
if (localStorage.getItem('access_token')) {
    // If on login/register page, redirect to dashboard
    if (window.location.pathname.includes('login.html') || 
        window.location.pathname.includes('register.html')) {
        window.location.href = '/static/dashboard.html';
    }
}

// API request wrapper with token refresh
async function apiRequest(url, options = {}) {
    // Add authorization header
    const accessToken = localStorage.getItem('access_token');
    if (accessToken) {
        options.headers = {
            ...options.headers,
            'Authorization': `Bearer ${accessToken}`
        };
    }
    
    // Make request
    let response = await fetch(url, options);
    
    // If unauthorized, try to refresh token
    if (response.status === 401) {
        const refreshToken = localStorage.getItem('refresh_token');
        if (refreshToken) {
            const refreshResponse = await fetch(`${API_BASE_URL}/auth/refresh`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ refresh_token: refreshToken })
            });
            
            if (refreshResponse.ok) {
                const data = await refreshResponse.json();
                // Store new tokens
                localStorage.setItem('access_token', data.access_token);
                localStorage.setItem('refresh_token', data.refresh_token);
                
                // Retry original request with new token
                options.headers['Authorization'] = `Bearer ${data.access_token}`;
                response = await fetch(url, options);
            } else {
                // Refresh failed, clear tokens and redirect to login
                localStorage.removeItem('access_token');
                localStorage.removeItem('refresh_token');
                window.location.href = '/static/login.html';
            }
        } else {
            // No refresh token, redirect to login
            localStorage.removeItem('access_token');
            window.location.href = '/static/login.html';
        }
    }
    
    return response;
}

// Logout function
async function logout() {
    const refreshToken = localStorage.getItem('refresh_token');
    
    if (refreshToken) {
        try {
            await apiRequest(`${API_BASE_URL}/auth/logout`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ refresh_token: refreshToken })
            });
        } catch (error) {
            console.error('Logout error:', error);
        }
    }
    
    // Clear tokens and redirect
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    window.location.href = '/static/login.html';
}

// Export functions for use in other files
window.apiRequest = apiRequest;
window.logout = logout;

// Load OAuth providers
async function loadOAuthProviders() {
    try {
        const response = await fetch(`${API_BASE_URL}/oauth/providers`);
        if (response.ok) {
            const data = await response.json();
            const oauthButtons = document.getElementById('oauthButtons');
            
            if (oauthButtons && data.providers.length > 0) {
                oauthButtons.innerHTML = data.providers.map(provider => `
                    <a href="/api/v1/oauth/authorize/${provider.name}" class="btn-oauth btn-oauth-${provider.name}">
                        <svg class="oauth-icon" viewBox="0 0 24 24">
                            ${getProviderIcon(provider.name)}
                        </svg>
                        Continue with ${provider.display_name}
                    </a>
                `).join('');
            }
        }
    } catch (error) {
        console.error('Error loading OAuth providers:', error);
    }
}

// Get SVG icon for OAuth provider
function getProviderIcon(provider) {
    const icons = {
        google: '<path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>',
        github: '<path fill="currentColor" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"/>'
    };
    return icons[provider] || '';
}

// Handle OAuth callback
function handleOAuthCallback() {
    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token');
    const error = urlParams.get('oauth_error');
    
    if (token) {
        // Store token and redirect to dashboard
        localStorage.setItem('access_token', token);
        window.location.href = '/static/dashboard.html';
    } else if (error) {
        showAlert('OAuth authentication failed. Please try again.', 'error');
    }
}

// Check demo mode on page load
window.addEventListener('DOMContentLoaded', () => {
    checkDemoMode();
    loadOAuthProviders();
    handleOAuthCallback();
});