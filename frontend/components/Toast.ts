/**
 * Toast Notification Component
 * Displays temporary notifications with auto-dismiss
 */

export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface ToastOptions {
    message: string;
    type?: ToastType;
    duration?: number; // milliseconds (0 = no auto-dismiss)
    position?: 'top-right' | 'top-left' | 'bottom-right' | 'bottom-left' | 'top-center' | 'bottom-center';
    dismissible?: boolean;
}

class ToastManager {
    private container: HTMLDivElement | null = null;
    private toasts: Map<string, HTMLDivElement> = new Map();

    constructor() {
        this.createContainer();
    }

    private createContainer(): void {
        if (this.container) return;

        this.container = document.createElement('div');
        this.container.id = 'toast-container';
        this.container.className = 'toast-container toast-position-top-right';
        this.container.setAttribute('aria-live', 'polite');
        this.container.setAttribute('aria-atomic', 'true');
        document.body.appendChild(this.container);
    }

    private getIcon(type: ToastType): string {
        const icons = {
            success: 'check_circle',
            error: 'error',
            warning: 'warning',
            info: 'info'
        };
        return icons[type];
    }

    show(options: ToastOptions): string {
        const {
            message,
            type = 'info',
            duration = 4000,
            position = 'top-right',
            dismissible = true
        } = options;

        if (!this.container) this.createContainer();

        // Update container position if needed
        if (this.container) {
            this.container.className = `toast-container toast-position-${position}`;
        }

        // Create toast element
        const toastId = `toast-${Date.now()}-${Math.random()}`;
        const toast = document.createElement('div');
        toast.id = toastId;
        toast.className = `toast toast-${type} animate-slideInRight`;
        toast.setAttribute('role', 'alert');

        toast.innerHTML = `
            <div class="toast-icon">
                <span class="material-symbols-outlined">${this.getIcon(type)}</span>
            </div>
            <div class="toast-message">${message}</div>
            ${dismissible ? `
                <button class="toast-close" aria-label="Close notification">
                    <span class="material-symbols-outlined">close</span>
                </button>
            ` : ''}
        `;

        // Add close handler
        if (dismissible) {
            const closeBtn = toast.querySelector('.toast-close');
            if (closeBtn) {
                closeBtn.addEventListener('click', () => this.dismiss(toastId));
            }
        }

        // Add to container
        this.container?.appendChild(toast);
        this.toasts.set(toastId, toast);

        // Auto-dismiss
        if (duration > 0) {
            setTimeout(() => this.dismiss(toastId), duration);
        }

        return toastId;
    }

    dismiss(toastId: string): void {
        const toast = this.toasts.get(toastId);
        if (!toast) return;

        // Fade out animation
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';

        setTimeout(() => {
            toast.remove();
            this.toasts.delete(toastId);
        }, 300);
    }

    dismissAll(): void {
        this.toasts.forEach((_, id) => this.dismiss(id));
    }

    success(message: string, duration?: number): string {
        return this.show({ message, type: 'success', duration });
    }

    error(message: string, duration?: number): string {
        return this.show({ message, type: 'error', duration: duration || 6000 });
    }

    warning(message: string, duration?: number): string {
        return this.show({ message, type: 'warning', duration });
    }

    info(message: string, duration?: number): string {
        return this.show({ message, type: 'info', duration });
    }
}

// Export singleton instance
export const toast = new ToastManager();

// CSS Styles (add to index.css)
export const toastStyles = `
/* ===== TOAST NOTIFICATION COMPONENT ===== */
.toast-container {
    position: fixed;
    z-index: var(--z-index-toast);
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    max-width: 400px;
    pointer-events: none;
}

.toast-position-top-right {
    top: var(--space-6);
    right: var(--space-6);
}

.toast-position-top-left {
    top: var(--space-6);
    left: var(--space-6);
}

.toast-position-bottom-right {
    bottom: var(--space-6);
    right: var(--space-6);
}

.toast-position-bottom-left {
    bottom: var(--space-6);
    left: var(--space-6);
}

.toast-position-top-center {
    top: var(--space-6);
    left: 50%;
    transform: translateX(-50%);
}

.toast-position-bottom-center {
    bottom: var(--space-6);
    left: 50%;
    transform: translateX(-50%);
}

.toast {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-4);
    background-color: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-lg);
    pointer-events: auto;
    transition: all var(--transition-base);
}

.toast-icon {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    border-radius: var(--radius-full);
}

.toast-icon .material-symbols-outlined {
    font-size: 1.25rem;
}

.toast-message {
    flex: 1;
    font-size: var(--font-size-sm);
    line-height: var(--line-height-normal);
    color: var(--text-primary);
}

.toast-close {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    padding: 0;
    background: transparent;
    border: none;
    border-radius: var(--radius-base);
    color: var(--text-secondary);
    cursor: pointer;
    transition: all var(--transition-fast);
}

.toast-close:hover {
    background-color: var(--bg-hover);
    color: var(--text-primary);
}

.toast-close .material-symbols-outlined {
    font-size: 1rem;
}

/* Toast Type Variants */
.toast-success {
    border-left: 4px solid var(--color-success);
}

.toast-success .toast-icon {
    background-color: var(--color-success-light);
    color: var(--color-success-dark);
}

.toast-error {
    border-left: 4px solid var(--color-danger);
}

.toast-error .toast-icon {
    background-color: var(--color-danger-light);
    color: var(--color-danger-dark);
}

.toast-warning {
    border-left: 4px solid var(--color-warning);
}

.toast-warning .toast-icon {
    background-color: var(--color-warning-light);
    color: var(--color-warning-dark);
}

.toast-info {
    border-left: 4px solid var(--color-info);
}

.toast-info .toast-icon {
    background-color: var(--color-info-light);
    color: var(--color-info-dark);
}

/* Mobile responsive */
@media (max-width: 640px) {
    .toast-container {
        max-width: calc(100vw - 2rem);
        left: 1rem !important;
        right: 1rem !important;
        transform: none !important;
    }
}
`;
