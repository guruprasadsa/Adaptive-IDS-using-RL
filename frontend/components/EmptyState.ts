/**
 * Empty State Component
 * Displays a friendly message when no data is available
 */

export interface EmptyStateProps {
    icon?: string;
    title: string;
    description?: string;
    actionText?: string;
    onAction?: () => void;
}

export function createEmptyState(props: EmptyStateProps): HTMLElement {
    const { icon = 'inbox', title, description, actionText, onAction } = props;

    const container = document.createElement('div');
    container.className = 'empty-state';

    container.innerHTML = `
        <div class="empty-state-icon">
            <span class="material-symbols-outlined">${icon}</span>
        </div>
        <h3 class="empty-state-title">${title}</h3>
        ${description ? `<p class="empty-state-description">${description}</p>` : ''}
        ${actionText ? `<button class="btn btn-primary empty-state-action">${actionText}</button>` : ''}
    `;

    if (actionText && onAction) {
        const actionBtn = container.querySelector('.empty-state-action');
        actionBtn?.addEventListener('click', onAction);
    }

    return container;
}

// CSS Styles (add to index.css)
export const emptyStateStyles = `
/* ===== EMPTY STATE COMPONENT ===== */
.empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: var(--space-16) var(--space-8);
    text-align: center;
    min-height: 300px;
}

.empty-state-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 80px;
    height: 80px;
    margin-bottom: var(--space-6);
    background-color: var(--bg-secondary);
    border-radius: var(--radius-full);
}

.empty-state-icon .material-symbols-outlined {
    font-size: 3rem;
    color: var(--text-tertiary);
}

.empty-state-title {
    margin: 0 0 var(--space-2) 0;
    font-size: var(--font-size-xl);
    font-weight: var(--font-weight-semibold);
    color: var(--text-primary);
}

.empty-state-description {
    margin: 0 0 var(--space-6) 0;
    max-width: 400px;
    font-size: var(--font-size-base);
    color: var(--text-secondary);
    line-height: var(--line-height-relaxed);
}

.empty-state-action {
    margin-top: var(--space-4);
}
`;
