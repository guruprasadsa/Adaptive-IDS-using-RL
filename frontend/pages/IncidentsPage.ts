import { createEmptyState } from "../components/EmptyState";
import { renderPagination } from "../components/Pagination";
import { toast } from "../components/Toast";
import { createIncident, updateIncidentStatus } from "../services/incidentsService";
import { Alert, Incident, IncidentsState } from "../types";

const formatLabel = (value: string): string => value.replace(/_/g, ' ').replace(/\b\w/g, (char: string) => char.toUpperCase());

const renderIncidentsToolbar = (state: IncidentsState): string => `
    <div class="alerts-toolbar">
        <div class="filter-group">
            <div class="search-wrapper">
                <span class="material-symbols-outlined">search</span>
                <input type="search" id="incident-search-input" class="search-input" placeholder="Search incidents..." value="${state.filters.search}" aria-label="Search incidents">
            </div>
            <select id="severity-filter" data-filter="severity" aria-label="Filter by severity" class="filter-select">
                <option value="all" ${state.filters.severity === 'all' ? 'selected' : ''}>All Severities</option>
                <option value="critical" ${state.filters.severity === 'critical' ? 'selected' : ''}>Critical</option>
                <option value="high" ${state.filters.severity === 'high' ? 'selected' : ''}>High</option>
                <option value="medium" ${state.filters.severity === 'medium' ? 'selected' : ''}>Medium</option>
                <option value="low" ${state.filters.severity === 'low' ? 'selected' : ''}>Low</option>
            </select>
            <select id="incident-status-filter" data-filter="status" aria-label="Filter by status" class="filter-select">
                <option value="all" ${state.filters.status === 'all' ? 'selected' : ''}>All Statuses</option>
                <option value="open" ${state.filters.status === 'open' ? 'selected' : ''}>Open</option>
                <option value="investigating" ${state.filters.status === 'investigating' ? 'selected' : ''}>Investigating</option>
                <option value="contained" ${state.filters.status === 'contained' ? 'selected' : ''}>Contained</option>
                <option value="resolved" ${state.filters.status === 'resolved' ? 'selected' : ''}>Resolved</option>
            </select>
        </div>
        <button class="btn btn-primary" id="create-incident-btn">
            <span class="material-symbols-outlined">add</span>
            Create Incident
        </button>
    </div>
`;

const renderIncidentDetailsRow = (incident: Incident, alerts: Alert[]): string => {
    const relatedAlerts = alerts.filter(a => incident.relatedAlertIds.includes(a.id));
    return `
        <tr class="incident-details-row">
            <td colspan="6">
                <div class="incident-details-content">
                    <h4>Summary</h4>
                    <p>${incident.summary}</p>
                    <p class="incident-description">${incident.description}</p>
                    <h4 class="related-alerts-header">Related Alerts (${relatedAlerts.length})</h4>
                    <ul class="related-alerts-list">
                        ${relatedAlerts.map(alert => `<li><strong>${formatLabel(alert.priority)}:</strong> ${alert.description} (Source: ${alert.source})</li>`).join('')}
                    </ul>
                </div>
            </td>
        </tr>
    `;
};

const renderIncidentsTable = (incidents: Incident[], state: IncidentsState, alerts: Alert[]): HTMLElement => {
    const wrapper = document.createElement('div');
    wrapper.className = 'alerts-table-wrapper';

    // If no incidents, show empty state
    if (incidents.length === 0) {
        const emptyState = createEmptyState({
            icon: 'fact_check',
            title: 'No Incidents Found',
            description: 'There are no incidents matching your current filters. Try adjusting your search or filter criteria.'
        });
        wrapper.appendChild(emptyState);
        return wrapper;
    }

    const severityClasses: Record<Incident['severity'], string> = {
        critical: 'priority-critical', high: 'priority-high', medium: 'priority-medium', low: 'priority-low',
    };
    const statusClasses: Record<Incident['status'], string> = {
        open: 'status-new',
        investigating: 'status-investigating',
        contained: 'status-resolved',
        resolved: 'status-resolved'
    };
    
    const headers: { key: keyof Omit<Incident, 'relatedAlertIds' | 'summary' | 'createdAt' | 'id'>; label: string }[] = [
        { key: 'severity', label: 'Severity' },
        { key: 'title', label: 'Title' },
        { key: 'status', label: 'Status' },
        { key: 'assignedTo', label: 'Assigned To' },
        { key: 'lastUpdatedAt', label: 'Last Updated' },
    ];
    
    const actionsHeader = '<th>Actions</th>';

    const renderHeader = (header: { key: keyof Incident; label: string }) => {
        const isSorted = state.sortColumn === header.key;
        const sortIcon = isSorted ? (state.sortDirection === 'asc' ? 'arrow_upward' : 'arrow_downward') : 'swap_vert';
        const ariaSort = isSorted ? (state.sortDirection === 'asc' ? 'ascending' : 'descending') : 'none';
        return `<th class="sortable" data-sort-key="${header.key}" aria-sort="${ariaSort}">
                    ${header.label}
                    <span class="material-symbols-outlined sort-icon">${sortIcon}</span>
                </th>`;
    };
    
    const renderActionButtons = (incident: Incident): string => {
        const statusActions = {
            'open': ['investigating', 'resolved'],
            'investigating': ['contained', 'resolved'],
            'contained': ['resolved'],
            'resolved': []
        };
        
        const availableActions = statusActions[incident.status as keyof typeof statusActions] || [];
        
        return `
            <div class="action-buttons">
                ${availableActions.map(action => `
                    <button class="btn-icon update-status-btn" 
                            data-incident-id="${incident.id}" 
                            data-new-status="${action}"
                            title="Mark as ${formatLabel(action)}">
                        <span class="material-symbols-outlined">
                            ${action === 'investigating' ? 'search' : action === 'contained' ? 'shield' : 'check_circle'}
                        </span>
                    </button>
                `).join('')}
            </div>
        `;
    };

    const table = document.createElement('table');
    table.className = 'alerts-table incidents-table';
    
    table.innerHTML = `
        <thead>
            <tr>
                ${headers.map(renderHeader).join('')}
                ${actionsHeader}
            </tr>
        </thead>
        <tbody>
            ${incidents.map(incident => `
                <tr class="incident-row" data-incident-id="${incident.id}" aria-expanded="${state.expandedIncidentId === incident.id}">
                    <td>
                        <div class="priority-cell">
                            <span class="priority-indicator ${severityClasses[incident.severity]}"></span>
                            ${formatLabel(incident.severity)}
                        </div>
                    </td>
                    <td>${incident.title}</td>
                    <td><span class="status-badge ${statusClasses[incident.status]}">${formatLabel(incident.status)}</span></td>
                    <td>${incident.assignedTo}</td>
                    <td>${new Date(incident.lastUpdatedAt).toLocaleString()}</td>
                    <td>${renderActionButtons(incident)}</td>
                </tr>
                ${state.expandedIncidentId === incident.id ? renderIncidentDetailsRow(incident, alerts) : ''}
            `).join('')}
        </tbody>
    `;
    
    wrapper.appendChild(table);
    return wrapper;
};


export const renderIncidentsPage = (incidents: Incident[], totalIncidents: number, state: IncidentsState, alerts: Alert[]): HTMLElement => {
    const main = document.createElement('main');
    main.className = 'main-content';
    main.innerHTML = `
        <div class="card full-height-card">
            <div id="incidents-page-container">
                ${renderIncidentsToolbar(state)}
            </div>
        </div>
    `;
    const container = main.querySelector('#incidents-page-container');
    if (container) {
        container.append(renderIncidentsTable(incidents, state, alerts));
        container.append(renderPagination(totalIncidents, state, true));
    }
    return main;
};

const renderCreateIncidentModal = (alerts: Alert[]): HTMLElement => {
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.id = 'create-incident-modal';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-labelledby', 'create-incident-title');
    modal.setAttribute('aria-modal', 'true');

    modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h2 id="create-incident-title">Create New Incident</h2>
                <button class="modal-close" aria-label="Close modal">
                    <span class="material-symbols-outlined">close</span>
                </button>
            </div>
            <div class="modal-body">
                <form id="create-incident-form">
                    <div class="form-group">
                        <label for="incident-title">Title *</label>
                        <input type="text" id="incident-title" name="title" required 
                               placeholder="Enter incident title" maxlength="200">
                    </div>
                    
                    <div class="form-group">
                        <label for="incident-description">Description *</label>
                        <textarea id="incident-description" name="description" required 
                                  placeholder="Describe the incident details..." rows="4"></textarea>
                    </div>
                    
                    <div class="form-group">
                        <label for="incident-severity">Severity *</label>
                        <select id="incident-severity" name="severity" required>
                            <option value="">Select severity</option>
                            <option value="critical">Critical</option>
                            <option value="high">High</option>
                            <option value="medium">Medium</option>
                            <option value="low">Low</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label for="incident-alerts">Related Alerts</label>
                        <div class="alerts-selector">
                            <div class="search-box">
                                <span class="material-symbols-outlined">search</span>
                                <input type="text" id="alert-search" placeholder="Search alerts...">
                            </div>
                            <div class="alerts-list" id="alerts-list">
                                ${alerts.slice(0, 10).map(alert => `
                                    <label class="alert-checkbox">
                                        <input type="checkbox" name="alert_ids" value="${alert.id}">
                                        <span class="alert-info">
                                            <span class="alert-type">${alert.type}</span>
                                            <span class="alert-meta">${alert.srcIp || alert.source} → ${alert.dstIp || 'N/A'}</span>
                                            <span class="alert-time">${new Date(alert.timestamp).toLocaleString()}</span>
                                        </span>
                                    </label>
                                `).join('')}
                            </div>
                        </div>
                    </div>
                    
                    <div class="modal-actions">
                        <button type="button" class="btn btn-secondary" id="cancel-create-incident">Cancel</button>
                        <button type="submit" class="btn btn-primary">
                            <span class="material-symbols-outlined">add</span>
                            Create Incident
                        </button>
                    </div>
                </form>
            </div>
        </div>
    `;

    return modal;
};

/**
 * Setup event listeners for incidents page
 */
export const setupIncidentsEventListeners = (
    onRefresh: () => void,
    alerts: Alert[]
): void => {
    // Create Incident button
    const createBtn = document.getElementById('create-incident-btn');
    if (createBtn) {
        createBtn.addEventListener('click', () => {
            showCreateIncidentModal(onRefresh, alerts);
        });
    }

    // Status update buttons (delegated event)
    document.addEventListener('click', async (e) => {
        const target = e.target as HTMLElement;
        const statusBtn = target.closest('.update-status-btn') as HTMLButtonElement;
        
        if (statusBtn) {
            e.preventDefault();
            const incidentId = statusBtn.dataset.incidentId;
            const newStatus = statusBtn.dataset.newStatus as 'open' | 'investigating' | 'contained' | 'resolved';
            
            if (incidentId && newStatus) {
                await handleStatusUpdate(incidentId, newStatus, onRefresh);
            }
        }
    });
};

/**
 * Show create incident modal
 */
const showCreateIncidentModal = (onRefresh: () => void, alerts: Alert[]): void => {
    // Remove existing modal if any
    const existingModal = document.getElementById('create-incident-modal');
    if (existingModal) {
        existingModal.remove();
    }

    const modal = renderCreateIncidentModal(alerts);
    document.body.appendChild(modal);

    // Show modal
    setTimeout(() => modal.classList.add('show'), 10);

    // Close button
    const closeBtn = modal.querySelector('.modal-close');
    if (closeBtn) {
        closeBtn.addEventListener('click', () => {
            modal.classList.remove('show');
            setTimeout(() => modal.remove(), 300);
        });
    }

    // Cancel button
    const cancelBtn = document.getElementById('cancel-create-incident');
    if (cancelBtn) {
        cancelBtn.addEventListener('click', () => {
            modal.classList.remove('show');
            setTimeout(() => modal.remove(), 300);
        });
    }

    // Close on backdrop click
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.remove('show');
            setTimeout(() => modal.remove(), 300);
        }
    });

    // Alert search filter
    const alertSearch = document.getElementById('alert-search') as HTMLInputElement;
    if (alertSearch) {
        alertSearch.addEventListener('input', (e) => {
            const searchTerm = (e.target as HTMLInputElement).value.toLowerCase();
            const alertsList = document.getElementById('alerts-list');
            if (alertsList) {
                const checkboxes = alertsList.querySelectorAll('.alert-checkbox');
                checkboxes.forEach((checkbox) => {
                    const text = checkbox.textContent?.toLowerCase() || '';
                    const parent = checkbox as HTMLElement;
                    parent.style.display = text.includes(searchTerm) ? 'flex' : 'none';
                });
            }
        });
    }

    // Form submit
    const form = document.getElementById('create-incident-form') as HTMLFormElement;
    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            await handleCreateIncident(form, modal, onRefresh);
        });
    }
};

/**
 * Handle create incident form submission
 */
const handleCreateIncident = async (
    form: HTMLFormElement,
    modal: HTMLElement,
    onRefresh: () => void
): Promise<void> => {
    const formData = new FormData(form);
    const title = formData.get('title') as string;
    const description = formData.get('description') as string;
    const severity = formData.get('severity') as 'low' | 'medium' | 'high' | 'critical';
    const alertIds = Array.from(formData.getAll('alert_ids')) as string[];

    if (!title || !description || !severity) {
        toast.show({ message: 'Please fill in all required fields', type: 'error' });
        return;
    }

    const submitBtn = form.querySelector('button[type="submit"]') as HTMLButtonElement;
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Creating...';
    }

    try {
        await createIncident({
            title,
            description,
            severity,
            alert_ids: alertIds.length > 0 ? alertIds : undefined
        });

        toast.show({ message: 'Incident created successfully', type: 'success' });
        
        // Close modal
        modal.classList.remove('show');
        setTimeout(() => modal.remove(), 300);

        // Refresh incidents list
        onRefresh();
    } catch (error) {
        console.error('Error creating incident:', error);
        toast.show({ message: 'Failed to create incident', type: 'error' });
    } finally {
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<span class="material-symbols-outlined">add</span> Create Incident';
        }
    }
};

/**
 * Handle status update
 */
const handleStatusUpdate = async (
    incidentId: string,
    newStatus: 'open' | 'investigating' | 'contained' | 'resolved',
    onRefresh: () => void
): Promise<void> => {
    try {
        await updateIncidentStatus(incidentId, newStatus);
        toast.show({ message: `Incident status updated to ${newStatus}`, type: 'success' });
        onRefresh();
    } catch (error) {
        console.error('Error updating incident status:', error);
        toast.show({ message: 'Failed to update incident status', type: 'error' });
    }
};

export const renderIncidentsPageContent = (incidents: Incident[], totalIncidents: number, state: IncidentsState, alerts: Alert[]): { table: HTMLElement, pagination: HTMLElement } => {
    const newTable = renderIncidentsTable(incidents, state, alerts);
    const newPagination = renderPagination(totalIncidents, state, true);
    return { table: newTable, pagination: newPagination };
};
