/**
 * Reports Page
 * Report generation, scheduling, and export functionality
 */

import { toast } from "../components/Toast";
import {
    deleteReport,
    downloadReportAsFile,
    generateReport,
    getRecentReports,
    getReportSchedules
} from "../services/reportsService";
import type { User } from "../types";

interface ReportTemplate {
    id: string;
    name: string;
    description: string;
    icon: string;
}

const reportTemplates: ReportTemplate[] = [
    {
        id: 'alert-summary',
        name: 'Alert Summary Report',
        description: 'Comprehensive alert statistics and trends',
        icon: 'security'
    },
    {
        id: 'incident-timeline',
        name: 'Incident Timeline',
        description: 'Chronological incident history and resolution',
        icon: 'timeline'
    },
    {
        id: 'model-performance',
        name: 'Model Performance',
        description: 'ML model metrics and accuracy analysis',
        icon: 'analytics'
    },
    {
        id: 'threat-intelligence',
        name: 'Threat Intelligence',
        description: 'Attack patterns and threat actor analysis',
        icon: 'shield'
    },
    {
        id: 'compliance',
        name: 'Compliance Report',
        description: 'Security compliance and audit trail',
        icon: 'fact_check'
    },
    {
        id: 'custom',
        name: 'Custom Report',
        description: 'Build a custom report with selected metrics',
        icon: 'edit_note'
    }
];

/**
 * Create the report generation modal container
 */
function createReportModal(): HTMLElement {
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.id = 'report-generation-modal';
    modal.style.display = 'none';
    return modal;
}

export const renderReportsPage = (user: User | null = null): HTMLElement => {
    const main = document.createElement('main');
    main.className = 'main-content';
    
    // Page container
    const container = document.createElement('div');
    container.className = 'reports-container';
    container.id = 'reports-container';
    
    // Header
    const header = document.createElement('div');
    header.className = 'reports-header';
    header.innerHTML = `
        <div class="header-left">
            <h2>Reports</h2>
            <p class="subtitle">Generate, schedule, and export security reports</p>
        </div>
        <div class="header-actions">
            <button class="btn btn-secondary" id="view-scheduled-reports-btn">
                <span class="material-symbols-outlined">schedule</span>
                Scheduled Reports
            </button>
            <button class="btn btn-primary" id="generate-report-btn">
                <span class="material-symbols-outlined">add</span>
                Generate Report
            </button>
        </div>
    `;
    
    // Main content area with tabs
    const contentArea = document.createElement('div');
    contentArea.className = 'reports-content';
    
    // Tabs
    const tabsNav = document.createElement('div');
    tabsNav.className = 'tabs-nav';
    tabsNav.innerHTML = `
        <button class="tab-btn active" data-tab="templates">
            <span class="material-symbols-outlined">folder_copy</span>
            Templates
        </button>
        <button class="tab-btn" data-tab="recent">
            <span class="material-symbols-outlined">history</span>
            Recent Reports
        </button>
        <button class="tab-btn" data-tab="scheduled">
            <span class="material-symbols-outlined">event_repeat</span>
            Scheduled
        </button>
    `;
    
    // Tab content
    const tabContent = document.createElement('div');
    tabContent.className = 'tab-content';
    tabContent.id = 'reports-tab-content';
    
    // Templates tab (default)
    const templatesTab = renderTemplatesTab();
    tabContent.appendChild(templatesTab);
    
    contentArea.appendChild(tabsNav);
    contentArea.appendChild(tabContent);
    
    // Assemble page
    container.appendChild(header);
    container.appendChild(contentArea);
    
    // Create modal container
    const modalContainer = createReportModal();
    container.appendChild(modalContainer);
    
    main.appendChild(container);
    
    // Setup tab switching
    setTimeout(() => {
        const tabBtns = tabsNav.querySelectorAll('.tab-btn');
        tabBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                tabBtns.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                const tab = btn.getAttribute('data-tab');
                handleTabSwitch(tab || 'templates');
            });
        });
    }, 0);
    
    return main;
};

/**
 * Render templates tab
 */
function renderTemplatesTab(): HTMLElement {
    const tab = document.createElement('div');
    tab.className = 'tab-pane active';
    tab.id = 'templates-tab';
    
    const templateGrid = document.createElement('div');
    templateGrid.className = 'report-templates-grid';
    
    reportTemplates.forEach(template => {
        const card = document.createElement('div');
        card.className = 'report-template-card';
        card.innerHTML = `
            <div class="template-icon">
                <span class="material-symbols-outlined">${template.icon}</span>
            </div>
            <div class="template-content">
                <h3>${template.name}</h3>
                <p>${template.description}</p>
            </div>
            <button class="btn btn-primary btn-block generate-template-btn" 
                    data-template-id="${template.id}">
                <span class="material-symbols-outlined">play_arrow</span>
                Generate
            </button>
        `;
        
        templateGrid.appendChild(card);
    });
    
    tab.appendChild(templateGrid);
    
    return tab;
}

/**
 * Render recent reports tab
 */
export function renderRecentReportsTab(reports: any[] = []): HTMLElement {
    const tab = document.createElement('div');
    tab.className = 'tab-pane';
    tab.id = 'recent-reports-tab';
    
    if (reports.length === 0) {
        tab.innerHTML = `
            <div class="empty-state">
                <span class="material-symbols-outlined empty-icon">description</span>
                <h3>No Recent Reports</h3>
                <p>Generated reports will appear here</p>
            </div>
        `;
    } else {
        const table = document.createElement('div');
        table.className = 'reports-table';
        table.innerHTML = renderReportsTable(reports);
        tab.appendChild(table);
    }
    
    return tab;
}

/**
 * Render scheduled reports tab
 */
export function renderScheduledReportsTab(schedules: any[] = []): HTMLElement {
    const tab = document.createElement('div');
    tab.className = 'tab-pane';
    tab.id = 'scheduled-reports-tab';
    
    if (schedules.length === 0) {
        tab.innerHTML = `
            <div class="empty-state">
                <span class="material-symbols-outlined empty-icon">event_busy</span>
                <h3>No Scheduled Reports</h3>
                <p>Create automated report schedules to receive regular updates</p>
                <button class="btn btn-primary" id="create-schedule-btn">
                    <span class="material-symbols-outlined">add</span>
                    Create Schedule
                </button>
            </div>
        `;
    } else {
        const table = document.createElement('div');
        table.className = 'schedules-table';
        table.innerHTML = renderSchedulesTable(schedules);
        tab.appendChild(table);
    }
    
    return tab;
}

/**
 * Handle tab switching
 */
function handleTabSwitch(tab: string): void {
    const contentArea = document.getElementById('reports-tab-content');
    if (!contentArea) return;
    
    // Remove all existing tabs
    contentArea.innerHTML = '';
    
    let newTab: HTMLElement;
    
    switch (tab) {
        case 'templates':
            newTab = renderTemplatesTab();
            contentArea.appendChild(newTab);
            // Re-setup template button listeners after rendering
            setTimeout(() => setupTemplateButtons(), 0);
            break;
        case 'recent':
            newTab = renderRecentReportsTab();
            contentArea.appendChild(newTab);
            // Load recent reports
            loadRecentReports();
            break;
        case 'scheduled':
            newTab = renderScheduledReportsTab();
            contentArea.appendChild(newTab);
            // Load scheduled reports
            loadScheduledReports();
            break;
        default:
            newTab = renderTemplatesTab();
            contentArea.appendChild(newTab);
            setTimeout(() => setupTemplateButtons(), 0);
    }
}

/**
 * Render report generation modal
 */
export function renderReportGenerationModal(templateId: string): string {
    const template = reportTemplates.find(t => t.id === templateId);
    if (!template) return '';
    
    return `
        <div class="modal-content">
            <div class="modal-header">
                <h3>Generate ${template.name}</h3>
                <button class="modal-close" id="close-report-modal">
                    <span class="material-symbols-outlined">close</span>
                </button>
            </div>
            <div class="modal-body">
                <form id="report-generation-form">
                    <div class="form-group">
                        <label>Report Name</label>
                        <input type="text" class="form-control" 
                               value="${template.name} - ${new Date().toLocaleDateString()}" 
                               id="report-name">
                    </div>
                    
                    <div class="form-group">
                        <label>Date Range</label>
                        <select class="form-control" id="report-date-range">
                            <option value="24h">Last 24 Hours</option>
                            <option value="7d" selected>Last 7 Days</option>
                            <option value="30d">Last 30 Days</option>
                            <option value="90d">Last 90 Days</option>
                            <option value="ytd">Year to Date</option>
                            <option value="custom">Custom Range</option>
                        </select>
                    </div>
                    
                    <div class="form-group" id="custom-date-range" style="display: none;">
                        <label>Start Date</label>
                        <input type="date" class="form-control" id="report-start-date">
                        <label>End Date</label>
                        <input type="date" class="form-control" id="report-end-date">
                    </div>
                    
                    <div class="form-group">
                        <label>Export Format</label>
                        <div class="checkbox-group">
                            <label class="checkbox-label">
                                <input type="checkbox" checked id="format-pdf"> PDF
                            </label>
                            <label class="checkbox-label">
                                <input type="checkbox" id="format-csv"> CSV
                            </label>
                            <label class="checkbox-label">
                                <input type="checkbox" id="format-json"> JSON
                            </label>
                        </div>
                    </div>
                    
                    <div class="form-group">
                        <label>
                            <input type="checkbox" id="report-email"> 
                            Email report when ready
                        </label>
                    </div>
                    
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" id="cancel-report-btn">
                            Cancel
                        </button>
                        <button type="submit" class="btn btn-primary" id="submit-report-btn">
                            <span class="material-symbols-outlined">play_arrow</span>
                            Generate Report
                        </button>
                    </div>
                </form>
            </div>
        </div>
    `;
}

/**
 * Setup event listeners for reports page
 */
export const setupReportsEventListeners = async (): Promise<void> => {
    // Generate Report button (header)
    const generateBtn = document.getElementById('generate-report-btn');
    if (generateBtn) {
        generateBtn.addEventListener('click', () => {
            showGenerateReportModal('alert-summary');
        });
    }

    // View Scheduled Reports button
    const scheduledBtn = document.getElementById('view-scheduled-reports-btn');
    if (scheduledBtn) {
        scheduledBtn.addEventListener('click', () => {
            switchToScheduledTab();
        });
    }

    // Template generation buttons
    setupTemplateButtons();

    // Tab switching
    const tabBtns = document.querySelectorAll('.tab-btn');
    tabBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            const target = e.target as HTMLElement;
            const tabBtn = target.closest('.tab-btn') as HTMLElement;
            if (tabBtn) {
                const tabName = tabBtn.dataset.tab;
                if (tabName) {
                    switchTab(tabName);
                }
            }
        });
    });

    // Load recent reports
    await loadRecentReports();
};

/**
 * Setup event listeners for template buttons
 */
function setupTemplateButtons(): void {
    const templateButtons = document.querySelectorAll('.generate-template-btn');
    templateButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            const target = e.target as HTMLElement;
            const button = target.closest('.generate-template-btn') as HTMLElement;
            if (button) {
                const templateId = button.dataset.templateId;
                if (templateId) {
                    showGenerateReportModal(templateId);
                }
            }
        });
    });
}

/**
 * Switch to a specific tab
 */
const switchTab = (tabName: string): void => {
    // Update active tab button
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    const activeBtn = document.querySelector(`[data-tab="${tabName}"]`);
    if (activeBtn) {
        activeBtn.classList.add('active');
    }

    // Show corresponding tab pane
    document.querySelectorAll('.tab-pane').forEach(pane => {
        pane.classList.remove('active');
    });
    const activePane = document.getElementById(`${tabName}-reports-tab`);
    if (activePane) {
        activePane.classList.add('active');
    }

    // Load data for the tab
    if (tabName === 'recent') {
        loadRecentReports();
    } else if (tabName === 'scheduled') {
        loadScheduledReports();
    }
};

/**
 * Switch to scheduled tab
 */
const switchToScheduledTab = (): void => {
    switchTab('scheduled');
};

/**
 * Load recent reports
 */
const loadRecentReports = async (): Promise<void> => {
    try {
        const { reports } = await getRecentReports(20);
        
        const recentTab = document.getElementById('recent-reports-tab');
        if (recentTab && reports.length > 0) {
            recentTab.innerHTML = renderReportsTable(reports);
            
            // Add delete button listeners
            recentTab.querySelectorAll('[data-action="delete"]').forEach(btn => {
                btn.addEventListener('click', async (e) => {
                    const target = e.target as HTMLElement;
                    const deleteBtn = target.closest('[data-report-id]') as HTMLElement;
                    if (deleteBtn) {
                        const reportId = deleteBtn.dataset.reportId;
                        if (reportId && confirm('Are you sure you want to delete this report?')) {
                            await handleDeleteReport(reportId);
                        }
                    }
                });
            });
        }
    } catch (error) {
        console.error('Error loading recent reports:', error);
        toast.show({ message: 'Failed to load recent reports', type: 'error' });
    }
};

/**
 * Load scheduled reports
 */
const loadScheduledReports = async (): Promise<void> => {
    try {
        const { schedules } = await getReportSchedules();
        
        const scheduledTab = document.getElementById('scheduled-reports-tab');
        if (scheduledTab && schedules.length > 0) {
            scheduledTab.innerHTML = renderSchedulesTable(schedules);
        }
    } catch (error) {
        console.error('Error loading scheduled reports:', error);
        toast.show({ message: 'Failed to load scheduled reports', type: 'error' });
    }
};

/**
 * Show generate report modal
 */
const showGenerateReportModal = (templateId: string): void => {
    const modal = document.getElementById('report-generation-modal');
    if (!modal) return;

    // Populate modal with content
    modal.innerHTML = renderReportGenerationModal(templateId);
    modal.style.display = 'flex';
    modal.classList.add('show');

    // Modal close handlers
    const closeBtn = modal.querySelector('.modal-close');
    if (closeBtn) {
        closeBtn.addEventListener('click', () => {
            modal.style.display = 'none';
            modal.classList.remove('show');
        });
    }

    const cancelBtn = document.getElementById('cancel-report-btn');
    if (cancelBtn) {
        cancelBtn.addEventListener('click', () => {
            modal.style.display = 'none';
            modal.classList.remove('show');
        });
    }

    // Backdrop click
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.style.display = 'none';
            modal.classList.remove('show');
        }
    });

    // Date range selector
    const dateRangeSelect = document.getElementById('report-date-range') as HTMLSelectElement;
    const customDateRange = document.getElementById('custom-date-range');
    if (dateRangeSelect && customDateRange) {
        dateRangeSelect.addEventListener('change', () => {
            customDateRange.style.display = dateRangeSelect.value === 'custom' ? 'block' : 'none';
        });
    }

    // Form submit
    const form = document.getElementById('report-generation-form') as HTMLFormElement;
    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            await handleGenerateReport(form, modal, templateId);
        });
    }
};

/**
 * Handle report generation
 */
const handleGenerateReport = async (form: HTMLFormElement, modal: HTMLElement, templateId: string): Promise<void> => {
    const reportName = (document.getElementById('report-name') as HTMLInputElement)?.value || '';
    const dateRangeSelect = (document.getElementById('report-date-range') as HTMLSelectElement)?.value || '7d';
    
    // Determine format (for now, use first checked format)
    let format: 'json' | 'csv' | 'pdf' = 'json';
    if ((document.getElementById('format-csv') as HTMLInputElement)?.checked) {
        format = 'csv';
    } else if ((document.getElementById('format-pdf') as HTMLInputElement)?.checked) {
        format = 'pdf';
    }

    // Build custom date range if needed
    let finalDateRange = dateRangeSelect;
    if (dateRangeSelect === 'custom') {
        const startDate = (document.getElementById('report-start-date') as HTMLInputElement)?.value;
        const endDate = (document.getElementById('report-end-date') as HTMLInputElement)?.value;
        if (startDate && endDate) {
            finalDateRange = `${startDate}:${endDate}`;
        } else {
            toast.show({ message: 'Please select both start and end dates', type: 'error' });
            return;
        }
    }

    const submitBtn = document.getElementById('submit-report-btn') as HTMLButtonElement;
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Generating...';
    }

    try {
        const response = await generateReport({
            report_type: templateId as any,
            date_range: finalDateRange,
            format
        });

        toast.show({ message: 'Report generated successfully', type: 'success' });

        // If CSV, download immediately
        if (format === 'csv' && response.content) {
            const filename = `${templateId}-${response.date_range.replace(/\s/g, '-')}.csv`;
            downloadReportAsFile(response.content, filename, 'csv');
        }

        // If JSON, download data
        if (format === 'json' && response.data) {
            const filename = `${templateId}-${response.date_range.replace(/\s/g, '-')}.json`;
            const content = JSON.stringify(response.data, null, 2);
            downloadReportAsFile(content, filename, 'json');
        }

        // Close modal
        modal.style.display = 'none';
        modal.classList.remove('show');

        // Reload recent reports
        await loadRecentReports();

    } catch (error: any) {
        console.error('Error generating report:', error);
        const message = error?.response?.data?.message || 'Failed to generate report';
        toast.show({ message, type: 'error' });
    } finally {
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<span class="material-symbols-outlined">play_arrow</span> Generate Report';
        }
    }
};

/**
 * Handle report deletion
 */
const handleDeleteReport = async (reportId: string): Promise<void> => {
    try {
        await deleteReport(reportId);
        toast.show({ message: 'Report deleted successfully', type: 'success' });
        await loadRecentReports();
    } catch (error) {
        console.error('Error deleting report:', error);
        toast.show({ message: 'Failed to delete report', type: 'error' });
    }
};

/**
 * Render reports table (helper function moved from inline)
 */
function renderReportsTable(reports: any[]): string {
    return `
        <table class="data-table">
            <thead>
                <tr>
                    <th>Report Name</th>
                    <th>Type</th>
                    <th>Generated</th>
                    <th>Date Range</th>
                    <th>Size</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                ${reports.map(report => `
                    <tr>
                        <td>
                            <span class="material-symbols-outlined" style="vertical-align: middle; margin-right: 8px; color: #6c757d;">
                                description
                            </span>
                            <strong>${report.name}</strong>
                        </td>
                        <td><span class="badge">${report.type}</span></td>
                        <td>${new Date(report.generated_at).toLocaleString()}</td>
                        <td>${report.date_range}</td>
                        <td>${report.size}</td>
                        <td>
                            <div class="action-buttons">
                                <button class="btn-icon danger" title="Delete" 
                                        data-report-id="${report.id}" 
                                        data-action="delete">
                                    <span class="material-symbols-outlined">delete</span>
                                </button>
                            </div>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

/**
 * Render schedules table (helper function)
 */
function renderSchedulesTable(schedules: any[]): string {
    return `
        <table class="data-table">
            <thead>
                <tr>
                    <th>Report Type</th>
                    <th>Frequency</th>
                    <th>Next Run</th>
                    <th>Format</th>
                    <th>Status</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                ${schedules.map(schedule => `
                    <tr>
                        <td><strong>${schedule.name}</strong></td>
                        <td>${schedule.frequency}</td>
                        <td>${schedule.next_run ? new Date(schedule.next_run).toLocaleString() : 'N/A'}</td>
                        <td><span class="badge">${schedule.format.toUpperCase()}</span></td>
                        <td>
                            <span class="status-badge ${schedule.enabled ? 'status-active' : 'status-inactive'}">
                                ${schedule.enabled ? 'Active' : 'Inactive'}
                            </span>
                        </td>
                        <td>
                            <div class="action-buttons">
                                <button class="btn-icon danger" title="Delete" 
                                        data-schedule-id="${schedule.id}" 
                                        data-action="delete-schedule">
                                    <span class="material-symbols-outlined">delete</span>
                                </button>
                            </div>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}
