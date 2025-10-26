/**
 * Modal Component
 * Customizable modal dialog with overlay
 */

export interface ModalOptions {
    title?: string;
    content: string | HTMLElement;
    footer?: HTMLElement;
    size?: 'sm' | 'md' | 'lg' | 'xl' | 'full';
    closeOnOverlayClick?: boolean;
    closeOnEscape?: boolean;
    showCloseButton?: boolean;
    onOpen?: () => void;
    onClose?: () => void;
}

export class Modal {
    private modal: HTMLDivElement | null = null;
    private overlay: HTMLDivElement | null = null;
    private options: ModalOptions;
    private isOpen: boolean = false;

    constructor(options: ModalOptions) {
        this.options = {
            size: 'md',
            closeOnOverlayClick: true,
            closeOnEscape: true,
            showCloseButton: true,
            ...options
        };
    }

    private createModal(): void {
        // Create overlay
        this.overlay = document.createElement('div');
        this.overlay.className = 'modal-overlay';
        this.overlay.setAttribute('role', 'presentation');

        if (this.options.closeOnOverlayClick) {
            this.overlay.addEventListener('click', (e) => {
                if (e.target === this.overlay) {
                    this.close();
                }
            });
        }

        // Create modal container
        this.modal = document.createElement('div');
        this.modal.className = `modal modal-${this.options.size}`;
        this.modal.setAttribute('role', 'dialog');
        this.modal.setAttribute('aria-modal', 'true');
        if (this.options.title) {
            this.modal.setAttribute('aria-labelledby', 'modal-title');
        }

        // Build modal content
        let modalHTML = '';

        // Header
        if (this.options.title || this.options.showCloseButton) {
            modalHTML += '<div class="modal-header">';
            if (this.options.title) {
                modalHTML += `<h2 class="modal-title" id="modal-title">${this.options.title}</h2>`;
            }
            if (this.options.showCloseButton) {
                modalHTML += `
                    <button class="modal-close" aria-label="Close modal">
                        <span class="material-symbols-outlined">close</span>
                    </button>
                `;
            }
            modalHTML += '</div>';
        }

        // Body
        modalHTML += '<div class="modal-body">';
        if (typeof this.options.content === 'string') {
            modalHTML += this.options.content;
        }
        modalHTML += '</div>';

        // Footer
        if (this.options.footer) {
            modalHTML += '<div class="modal-footer"></div>';
        }

        this.modal.innerHTML = modalHTML;

        // Append custom content if not string
        if (typeof this.options.content !== 'string') {
            const body = this.modal.querySelector('.modal-body');
            if (body) {
                body.appendChild(this.options.content);
            }
        }

        // Append custom footer
        if (this.options.footer) {
            const footer = this.modal.querySelector('.modal-footer');
            if (footer) {
                footer.appendChild(this.options.footer);
            }
        }

        // Attach close button handler
        if (this.options.showCloseButton) {
            const closeBtn = this.modal.querySelector('.modal-close');
            if (closeBtn) {
                closeBtn.addEventListener('click', () => this.close());
            }
        }

        this.overlay.appendChild(this.modal);
    }

    private handleEscape = (e: KeyboardEvent): void => {
        if (e.key === 'Escape' && this.options.closeOnEscape && this.isOpen) {
            this.close();
        }
    };

    open(): void {
        if (this.isOpen) return;

        if (!this.modal) {
            this.createModal();
        }

        // Add to DOM
        document.body.appendChild(this.overlay!);
        
        // Prevent body scroll
        document.body.style.overflow = 'hidden';

        // Add escape key listener
        if (this.options.closeOnEscape) {
            document.addEventListener('keydown', this.handleEscape);
        }

        // Focus trap (trap focus within modal)
        setTimeout(() => {
            const focusableElements = this.modal!.querySelectorAll(
                'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
            );
            if (focusableElements.length > 0) {
                (focusableElements[0] as HTMLElement).focus();
            }
        }, 100);

        this.isOpen = true;

        // Trigger animation
        requestAnimationFrame(() => {
            this.overlay?.classList.add('modal-overlay-active');
            this.modal?.classList.add('modal-active');
        });

        if (this.options.onOpen) {
            this.options.onOpen();
        }
    }

    close(): void {
        if (!this.isOpen) return;

        // Remove animation classes
        this.overlay?.classList.remove('modal-overlay-active');
        this.modal?.classList.remove('modal-active');

        // Wait for animation to complete
        setTimeout(() => {
            this.overlay?.remove();
            document.body.style.overflow = '';
            document.removeEventListener('keydown', this.handleEscape);
            this.isOpen = false;

            if (this.options.onClose) {
                this.options.onClose();
            }
        }, 200);
    }

    destroy(): void {
        this.close();
        this.modal = null;
        this.overlay = null;
    }

    updateContent(content: string | HTMLElement): void {
        const body = this.modal?.querySelector('.modal-body');
        if (!body) return;

        if (typeof content === 'string') {
            body.innerHTML = content;
        } else {
            body.innerHTML = '';
            body.appendChild(content);
        }
    }
}

// Helper functions for common modal patterns
export function showConfirmDialog(options: {
    title: string;
    message: string;
    confirmText?: string;
    cancelText?: string;
    onConfirm: () => void;
    onCancel?: () => void;
    danger?: boolean;
}): Modal {
    const {
        title,
        message,
        confirmText = 'Confirm',
        cancelText = 'Cancel',
        onConfirm,
        onCancel,
        danger = false
    } = options;

    const content = document.createElement('div');
    content.innerHTML = `<p style="margin: 0; line-height: 1.5;">${message}</p>`;

    const footer = document.createElement('div');
    footer.style.cssText = 'display: flex; gap: 12px; justify-content: flex-end;';
    
    const cancelBtn = document.createElement('button');
    cancelBtn.className = 'btn btn-secondary';
    cancelBtn.textContent = cancelText;
    
    const confirmBtn = document.createElement('button');
    confirmBtn.className = `btn btn-${danger ? 'danger' : 'primary'}`;
    confirmBtn.textContent = confirmText;

    footer.appendChild(cancelBtn);
    footer.appendChild(confirmBtn);

    const modal = new Modal({
        title,
        content,
        footer,
        size: 'sm'
    });

    cancelBtn.addEventListener('click', () => {
        modal.close();
        if (onCancel) onCancel();
    });

    confirmBtn.addEventListener('click', () => {
        onConfirm();
        modal.close();
    });

    modal.open();
    return modal;
}

// CSS Styles (add to index.css)
export const modalStyles = `
/* ===== MODAL COMPONENT ===== */
.modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: var(--bg-overlay);
    z-index: var(--z-index-modal-backdrop);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: var(--space-4);
    opacity: 0;
    transition: opacity var(--transition-base);
}

.modal-overlay-active {
    opacity: 1;
}

.modal {
    background-color: var(--bg-card);
    border-radius: var(--radius-xl);
    box-shadow: var(--shadow-2xl);
    max-height: calc(100vh - 2rem);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    transform: scale(0.95);
    opacity: 0;
    transition: all var(--transition-base);
    z-index: var(--z-index-modal);
}

.modal-active {
    transform: scale(1);
    opacity: 1;
}

/* Modal Sizes */
.modal-sm {
    width: 100%;
    max-width: 400px;
}

.modal-md {
    width: 100%;
    max-width: 600px;
}

.modal-lg {
    width: 100%;
    max-width: 800px;
}

.modal-xl {
    width: 100%;
    max-width: 1200px;
}

.modal-full {
    width: calc(100% - 2rem);
    height: calc(100% - 2rem);
    max-width: none;
    max-height: none;
}

/* Modal Parts */
.modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--space-6);
    border-bottom: 1px solid var(--border-color);
}

.modal-title {
    margin: 0;
    font-size: var(--font-size-xl);
    font-weight: var(--font-weight-semibold);
    color: var(--text-primary);
}

.modal-close {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    padding: 0;
    background: transparent;
    border: none;
    border-radius: var(--radius-base);
    color: var(--text-secondary);
    cursor: pointer;
    transition: all var(--transition-fast);
}

.modal-close:hover {
    background-color: var(--bg-hover);
    color: var(--text-primary);
}

.modal-close .material-symbols-outlined {
    font-size: 1.25rem;
}

.modal-body {
    flex: 1;
    padding: var(--space-6);
    overflow-y: auto;
    color: var(--text-primary);
}

.modal-footer {
    padding: var(--space-6);
    border-top: 1px solid var(--border-color);
    background-color: var(--bg-secondary);
}

/* Mobile responsive */
@media (max-width: 640px) {
    .modal-overlay {
        padding: 0;
    }

    .modal-sm,
    .modal-md,
    .modal-lg,
    .modal-xl {
        width: 100%;
        max-width: none;
        height: 100%;
        max-height: none;
        border-radius: 0;
    }
}
`;
