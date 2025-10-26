/**
 * Metric Card Component
 * Displays a metric with label, value, and optional icon/trend
 */

export interface MetricCardProps {
    label: string;
    value: string | number;
    icon?: string;
    colorClass?: string;
    trend?: {
        value: number;
        label: string;
        direction: 'up' | 'down' | 'neutral';
    };
    description?: string;
}

export function createMetricCard(props: MetricCardProps): HTMLElement {
    const { label, value, icon, colorClass = 'metric-default', trend, description } = props;

    const card = document.createElement('div');
    card.className = 'metric-card';

    const getTrendIcon = (direction: 'up' | 'down' | 'neutral') => {
        switch (direction) {
            case 'up': return 'trending_up';
            case 'down': return 'trending_down';
            case 'neutral': return 'trending_flat';
        }
    };

    const getTrendClass = (direction: 'up' | 'down' | 'neutral') => {
        switch (direction) {
            case 'up': return 'metric-trend-up';
            case 'down': return 'metric-trend-down';
            case 'neutral': return 'metric-trend-neutral';
        }
    };

    card.innerHTML = `
        ${icon ? `
            <div class="metric-icon ${colorClass}">
                <span class="material-symbols-outlined">${icon}</span>
            </div>
        ` : ''}
        <div class="metric-content">
            <p class="metric-label">${label}</p>
            <h3 class="metric-value">${value}</h3>
            ${description ? `<p class="metric-description">${description}</p>` : ''}
            ${trend ? `
                <div class="metric-trend ${getTrendClass(trend.direction)}">
                    <span class="material-symbols-outlined">${getTrendIcon(trend.direction)}</span>
                    <span class="metric-trend-value">${trend.value > 0 ? '+' : ''}${trend.value}%</span>
                    <span class="metric-trend-label">${trend.label}</span>
                </div>
            ` : ''}
        </div>
    `;

    return card;
}

// CSS Styles (add to index.css)
export const metricCardStyles = `
/* ===== METRIC CARD COMPONENT ===== */
.metric-card {
    display: flex;
    align-items: flex-start;
    gap: var(--space-4);
    padding: var(--space-6);
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
    transition: all var(--transition-fast);
}

.metric-card:hover {
    box-shadow: var(--shadow-md);
    transform: translateY(-2px);
}

.metric-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 56px;
    height: 56px;
    flex-shrink: 0;
    border-radius: var(--radius-lg);
}

.metric-icon .material-symbols-outlined {
    font-size: 2rem;
}

.metric-default {
    background-color: var(--bg-secondary);
    color: var(--text-primary);
}

.metric-success {
    background-color: var(--color-success-light);
    color: var(--color-success-dark);
}

.metric-warning {
    background-color: var(--color-warning-light);
    color: var(--color-warning-dark);
}

.metric-danger {
    background-color: var(--color-danger-light);
    color: var(--color-danger-dark);
}

.metric-info {
    background-color: var(--color-info-light);
    color: var(--color-info-dark);
}

.metric-content {
    flex: 1;
    min-width: 0;
}

.metric-label {
    margin: 0 0 var(--space-1) 0;
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.metric-value {
    margin: 0;
    font-size: var(--font-size-3xl);
    font-weight: var(--font-weight-bold);
    color: var(--text-primary);
    line-height: var(--line-height-tight);
}

.metric-description {
    margin: var(--space-2) 0 0 0;
    font-size: var(--font-size-sm);
    color: var(--text-secondary);
    line-height: var(--line-height-normal);
}

.metric-trend {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    margin-top: var(--space-3);
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
}

.metric-trend .material-symbols-outlined {
    font-size: 1.125rem;
}

.metric-trend-up {
    color: var(--color-success);
}

.metric-trend-down {
    color: var(--color-danger);
}

.metric-trend-neutral {
    color: var(--text-secondary);
}

.metric-trend-label {
    color: var(--text-secondary);
    font-weight: var(--font-weight-normal);
}
`;
