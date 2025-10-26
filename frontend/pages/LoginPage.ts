/**
 * frontend/pages/LoginPage.ts
 * Login page with email/username and password authentication
 */

import { createButton } from '../components/Button';

export function renderLoginPage(
    onLogin: (emailOrUsername: string, password: string) => Promise<void>,
    errorMessage: string = '',
    isLoading: boolean = false
): HTMLElement {
    const loginContainer = document.createElement('div');
    loginContainer.className = 'login-container';

    // Create form container
    const formCard = document.createElement('div');
    formCard.className = 'login-card';

    // Header
    const header = document.createElement('div');
    header.className = 'login-header';
    header.innerHTML = `
        <span class="login-icon">
            <svg xmlns="http://www.w3.org/2000/svg" x="0px" y="0px" width="64" height="64" viewBox="0 0 48 48" style="fill:#40C057;">
                <path d="M 24 4 L 6 10 L 6 24 C 6 33.57 15.75 40.429688 21 43.429688 L 21 38.75 C 16.46 35.83 10 30.52 10 24 L 24 24 L 24 4 z M 24 24 L 24 45 C 24 45 42 37 42 24 L 42 10 L 27 5 L 27 9.2207031 L 38 12.880859 L 38 24 L 24 24 z"></path>
            </svg>
        </span>
        <h1 class="login-title">Adaptive IDS</h1>
        <p class="login-subtitle">Intrusion Detection System Dashboard</p>
    `;

    // Form
    const form = document.createElement('form');
    form.className = 'login-form';
    form.id = 'loginForm';

    // Email/Username field
    const emailGroup = document.createElement('div');
    emailGroup.className = 'form-group';
    emailGroup.innerHTML = `
        <label for="emailOrUsername" class="form-label">
            <span class="form-label-icon">
                <svg xmlns="http://www.w3.org/2000/svg" x="0px" y="0px" width="20" height="20" viewBox="0 0 24 24" style="fill:#40C057;">
                    <path d="M12 2C9.794 2 8 3.794 8 6v1c0 2.206 1.794 4 4 4s4-1.794 4-4V6C16 3.794 14.206 2 12 2zM20.832 17.445c-.09-.136-2.264-3.334-6.589-4.416-.409-.101-.84.063-1.075.416L12 15.197l-1.168-1.752c-.235-.353-.667-.518-1.075-.416-4.325 1.082-6.499 4.28-6.589 4.416C3.059 17.609 3 17.803 3 18v2c0 .552.448 1 1 1h16c.552 0 1-.448 1-1v-2C21 17.803 20.941 17.609 20.832 17.445z"></path>
                </svg>
            </span>
            Email or Username
        </label>
        <input
            type="text"
            id="emailOrUsername"
            name="emailOrUsername"
            class="form-input"
            placeholder="Enter your email or username"
            required
            autocomplete="username"
            ${isLoading ? 'disabled' : ''}
        />
    `;

    // Password field
    const passwordGroup = document.createElement('div');
    passwordGroup.className = 'form-group';
    passwordGroup.innerHTML = `
        <label for="password" class="form-label">
            <span class="form-label-icon">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 48 48" style="fill:#40C057;">
                    <path d="M 24 4 C 19.599415 4 16 7.599415 16 12 L 16 16 L 12.5 16 C 10.019 16 8 18.019 8 20.5 L 8 39.5 C 8 41.981 10.019 44 12.5 44 L 35.5 44 C 37.981 44 40 41.981 40 39.5 L 40 20.5 C 40 18.019 37.981 16 35.5 16 L 32 16 L 32 12 C 32 7.599415 28.400585 4 24 4 z M 24 7 C 26.779415 7 29 9.220585 29 12 L 29 16 L 19 16 L 19 12 C 19 9.220585 21.220585 7 24 7 z M 24 27 C 25.657 27 27 28.343 27 30 C 27 31.657 25.657 33 24 33 C 22.343 33 21 31.657 21 30 C 21 28.343 22.343 27 24 27 z"></path>
                </svg>
            </span>
            Password
        </label>
        <input
            type="password"
            id="password"
            name="password"
            class="form-input"
            placeholder="Enter your password"
            required
            autocomplete="current-password"
            ${isLoading ? 'disabled' : ''}
        />
    `;

    // Error message
    const errorContainer = document.createElement('div');
    if (errorMessage) {
        errorContainer.className = 'error-message animate-shake';
        errorContainer.setAttribute('role', 'alert');
        errorContainer.innerHTML = `
            <span class="material-symbols-outlined error-icon">error</span>
            <span class="error-text">${errorMessage}</span>
        `;
    }

    // Submit button using createButton component
    const submitButton = createButton({
        variant: 'primary',
        size: 'lg',
        type: 'submit',
        fullWidth: true,
        loading: isLoading,
        disabled: isLoading,
        children: isLoading ? 'Signing in...' : 'Sign In'
    });
    submitButton.className += ' login-button';

    // Assemble form
    form.appendChild(emailGroup);
    form.appendChild(passwordGroup);
    if (errorMessage) {
        form.appendChild(errorContainer);
    }
    form.appendChild(submitButton);

    // Assemble card
    formCard.appendChild(header);
    formCard.appendChild(form);
    loginContainer.appendChild(formCard);

    // Attach form submit handler
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const emailOrUsername = (form.querySelector('#emailOrUsername') as HTMLInputElement).value.trim();
        const password = (form.querySelector('#password') as HTMLInputElement).value;

        if (!emailOrUsername || !password) {
            return;
        }

        await onLogin(emailOrUsername, password);
    });

    return loginContainer;
}
