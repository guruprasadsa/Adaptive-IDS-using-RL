/**
 * Loading Spinner Component
 * Displays a loading animation with optional text
 */

export interface LoadingSpinnerProps {
    size?: 'sm' | 'md' | 'lg';
    text?: string;
    center?: boolean;
}

export function createLoadingSpinner(props: LoadingSpinnerProps = {}): HTMLElement {
    const { size = 'md', text, center = false } = props;

    const container = document.createElement('div');
    container.className = `loading-spinner-container ${center ? 'loading-spinner-center' : ''}`;

    const sizeClasses = {
        sm: 'loading-spinner-sm',
        md: 'loading-spinner-md',
        lg: 'loading-spinner-lg'
    };

    container.innerHTML = `
        <div class="loading-spinner ${sizeClasses[size]}"></div>
        ${text ? `<p class="loading-text">${text}</p>` : ''}
    `;

    return container;
}

export function createLoadingState(text: string = 'Loading...'): HTMLElement {
    const main = document.createElement('main');
    main.className = 'main-content';
    main.appendChild(createLoadingSpinner({ size: 'lg', text, center: true }));
    return main;
}

// CSS Styles (add to index.css or component stylesheet)
export const loadingSpinnerStyles = `
/* ===== LOADING SPINNER COMPONENT ===== */
.loading-spinner-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-4);
}

.loading-spinner-center {
    justify-content: center;
    min-height: 200px;
}

.loading-spinner {
    border: 3px solid var(--border-color);
    border-top-color: var(--accent-color);
    border-radius: var(--radius-full);
    animation: spin 0.8s linear infinite;
}

.loading-spinner-sm {
    width: 24px;
    height: 24px;
    border-width: 2px;
}

.loading-spinner-md {
    width: 40px;
    height: 40px;
    border-width: 3px;
}

.loading-spinner-lg {
    width: 64px;
    height: 64px;
    border-width: 4px;
}

.loading-text {
    margin: 0;
    font-size: var(--font-size-base);
    color: var(--text-secondary);
    font-weight: var(--font-weight-medium);
}

@keyframes spin {
    from {
        transform: rotate(0deg);
    }
    to {
        transform: rotate(360deg);
    }
}
`;
