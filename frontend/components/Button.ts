/**
 * Button Component
 * Reusable button with multiple variants, sizes, and states
 */

export type ButtonVariant = 'primary' | 'secondary' | 'success' | 'danger' | 'warning' | 'ghost' | 'link';
export type ButtonSize = 'sm' | 'md' | 'lg';

export interface ButtonProps {
    variant?: ButtonVariant;
    size?: ButtonSize;
    disabled?: boolean;
    loading?: boolean;
    icon?: string;
    iconPosition?: 'left' | 'right';
    fullWidth?: boolean;
    type?: 'button' | 'submit' | 'reset';
    ariaLabel?: string;
    onClick?: (e: MouseEvent) => void;
    children: string | HTMLElement[];
}

export function createButton(props: ButtonProps): HTMLButtonElement {
    const {
        variant = 'secondary',
        size = 'md',
        disabled = false,
        loading = false,
        icon,
        iconPosition = 'left',
        fullWidth = false,
        type = 'button',
        ariaLabel,
        onClick,
        children
    } = props;

    const button = document.createElement('button');
    button.type = type;
    button.className = `btn btn-${variant} btn-${size}`;
    
    if (fullWidth) button.classList.add('btn-full-width');
    if (disabled || loading) button.disabled = true;
    if (loading) button.classList.add('btn-loading');
    if (ariaLabel) button.setAttribute('aria-label', ariaLabel);

    // Build button content
    const content: (string | HTMLElement)[] = [];

    if (loading) {
        const spinner = document.createElement('span');
        spinner.className = 'btn-spinner';
        content.push(spinner);
    } else if (icon && iconPosition === 'left') {
        const iconElement = document.createElement('span');
        iconElement.className = 'btn-icon material-symbols-outlined';
        iconElement.textContent = icon;
        content.push(iconElement);
    }

    if (typeof children === 'string') {
        const textSpan = document.createElement('span');
        textSpan.className = 'btn-text';
        textSpan.textContent = children;
        content.push(textSpan);
    } else {
        content.push(...children);
    }

    if (icon && iconPosition === 'right' && !loading) {
        const iconElement = document.createElement('span');
        iconElement.className = 'btn-icon material-symbols-outlined';
        iconElement.textContent = icon;
        content.push(iconElement);
    }

    content.forEach(item => {
        if (typeof item === 'string') {
            button.appendChild(document.createTextNode(item));
        } else {
            button.appendChild(item);
        }
    });

    if (onClick) {
        button.addEventListener('click', onClick);
    }

    return button;
}

// CSS Styles (add to index.css)
export const buttonStyles = `
/* ===== BUTTON COMPONENT ===== */
.btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-4);
    border: 1px solid transparent;
    border-radius: var(--radius-base);
    font-family: var(--font-family-base);
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
    line-height: var(--line-height-tight);
    text-decoration: none;
    white-space: nowrap;
    cursor: pointer;
    transition: all var(--transition-fast);
    user-select: none;
}

.btn:focus-visible {
    outline: 2px solid var(--accent-color);
    outline-offset: 2px;
}

.btn:disabled,
.btn.btn-loading {
    opacity: 0.6;
    cursor: not-allowed;
    pointer-events: none;
}

/* Button Sizes */
.btn-sm {
    padding: var(--space-1) var(--space-3);
    font-size: var(--font-size-xs);
}

.btn-md {
    padding: var(--space-2) var(--space-4);
    font-size: var(--font-size-sm);
}

.btn-lg {
    padding: var(--space-3) var(--space-6);
    font-size: var(--font-size-base);
}

/* Button Variants */
.btn-primary {
    background-color: var(--accent-color);
    border-color: var(--accent-color);
    color: var(--text-inverse);
}

.btn-primary:hover:not(:disabled) {
    background-color: var(--accent-color-hover);
    border-color: var(--accent-color-hover);
    transform: translateY(-1px);
    box-shadow: var(--shadow-sm);
}

.btn-primary:active:not(:disabled) {
    transform: translateY(0);
}

.btn-secondary {
    background-color: var(--bg-card);
    border-color: var(--border-color);
    color: var(--text-primary);
}

.btn-secondary:hover:not(:disabled) {
    background-color: var(--bg-hover);
    border-color: var(--border-color-dark);
}

.btn-success {
    background-color: var(--color-success);
    border-color: var(--color-success);
    color: var(--text-inverse);
}

.btn-success:hover:not(:disabled) {
    background-color: var(--color-success-dark);
}

.btn-danger {
    background-color: var(--color-danger);
    border-color: var(--color-danger);
    color: var(--text-inverse);
}

.btn-danger:hover:not(:disabled) {
    background-color: var(--color-danger-dark);
}

.btn-warning {
    background-color: var(--color-warning);
    border-color: var(--color-warning);
    color: var(--color-neutral-900);
}

.btn-warning:hover:not(:disabled) {
    background-color: var(--color-warning-dark);
}

.btn-ghost {
    background-color: transparent;
    border-color: transparent;
    color: var(--text-primary);
}

.btn-ghost:hover:not(:disabled) {
    background-color: var(--bg-hover);
}

.btn-link {
    background-color: transparent;
    border-color: transparent;
    color: var(--accent-color);
    padding: 0;
}

.btn-link:hover:not(:disabled) {
    color: var(--accent-color-hover);
    text-decoration: underline;
}

/* Button States */
.btn-full-width {
    width: 100%;
}

.btn-spinner {
    display: inline-block;
    width: 16px;
    height: 16px;
    border: 2px solid currentColor;
    border-top-color: transparent;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
}

.btn-icon {
    font-size: 1.25em;
}
`;
