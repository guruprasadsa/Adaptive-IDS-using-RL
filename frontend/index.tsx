// --- IMPORT TYPES ---
import { apiService } from './api';
import { Alert, AlertsState, DashboardStats, Incident, IncidentsState, ModelMetrics, PredictionResult, StatCardData } from './types';

// --- IMPORT DATA ---
import { defaultStatCards, navItems } from './data';

// --- IMPORT PAGE RENDERERS ---
import { renderAlertsPage } from './pages/AlertsPage';
import { renderAnalyticsPage } from './pages/AnalyticsPage';
import { renderDashboard } from './pages/Dashboard';
import { renderIncidentsPage, setupIncidentsEventListeners } from './pages/IncidentsPage';
import { renderLoginPage } from './pages/LoginPage';
import { renderReportsPage } from './pages/ReportsPage';
import { renderRLModelPage } from './pages/RLModelPage';

// --- IMPORT COMPONENT RENDERERS ---
import { createTrafficChart } from './components/Chart';
import { renderHeader } from './components/Header';
import { toast } from './components/Toast';

// --- IMPORT SERVICES ---
import { authService, AuthState } from './services/authService';

// --- IMPORT UTILITIES ---
import type { SSEMessage } from './types';
import { exportAlertsToCSV, generateCSVFilename } from './utils/csvExport';
import { getRealtimeClient } from './utils/realtimeClient';

// --- APP LOGIC ---

class App {
    private appContainer: HTMLElement;
    private activePage: string;
    private alerts: Alert[] = [];
    private incidents: Incident[] = [];
    private dashboardStats: DashboardStats | null = null;
    private isLoading: boolean = false;
    private backendAvailable: boolean = true;
    private modelMetrics: ModelMetrics | null = null;
    private authState: AuthState = {
        isAuthenticated: false,
        user: null,
        isLoading: false
    };
    private loginError: string = '';
    private loginLoading: boolean = false;
    private alertsState: AlertsState = {
        currentPage: 1,
        itemsPerPage: 10,
        sortColumn: 'timestamp',
        sortDirection: 'desc',
        filters: {
            priority: 'all',
            status: 'all',
            search: '',
        },
    };
    private incidentsState: IncidentsState = {
        currentPage: 1,
        itemsPerPage: 10,
        sortColumn: 'lastUpdatedAt',
        sortDirection: 'desc',
        filters: {
            severity: 'all',
            status: 'all',
            search: '',
        },
        expandedIncidentId: null,
    };
    private realtimeRefreshInFlight: boolean = false;
    private lastRealtimeRefreshMs: number = 0;

    constructor() {
        this.appContainer = document.getElementById('app-container')!;
        this.activePage = this.getInitialPage();

        // Subscribe to auth state changes
        authService.subscribe((state: AuthState) => {
            this.authState = state;
            
            // If user just logged in, load data
            if (state.isAuthenticated && !this.dashboardStats) {
                this.loadInitialData();
            }
            
            // If user logged out, disconnect realtime
            if (!state.isAuthenticated) {
                this.disconnectRealtime();
            }
            
            this.render();
        });

        this.attachEventListeners();
    }
    
    private async loadInitialData() {
        try {
            this.isLoading = true;
            this.render(); // Show loading state

            // Load dashboard stats and model metrics in parallel
            const [dashboardStats, modelMetrics] = await Promise.all([
                apiService.getDashboardStats(),
                apiService.getModelMetrics()
            ]);
            
            this.dashboardStats = dashboardStats;
            this.modelMetrics = modelMetrics;
            this.backendAvailable = true;
            
            // Load initial alerts and incidents
            const alertsResponse = await apiService.getAlerts(1, 50);
            const incidentsResponse = await apiService.getIncidents(1, 50);
            
            this.alerts = alertsResponse.alerts;
            this.incidents = incidentsResponse.incidents;
            
            // Connect to realtime after successful data load
            this.connectRealtime();
            
        } catch (error) {
            console.error('Failed to load data from backend:', error);
            toast.show({
                message: 'Failed to connect to backend. Live data unavailable.',
                type: 'error',
                duration: 5000
            });
            // Do not populate any demo data in production mode
            this.alerts = [];
            this.incidents = [];
            this.dashboardStats = null;
            this.backendAvailable = false;
        } finally {
            this.isLoading = false;
            this.render();
        }
    }

    private async loadAlerts(page: number = 1, filters: Record<string, any> = {}) {
        if (!this.backendAvailable) {
            return null;
        }
        try {
            const response = await apiService.getAlerts(page, this.alertsState.itemsPerPage, filters);
            this.alerts = response.alerts;
            return response;
        } catch (error) {
            console.error('Failed to load alerts:', error);
            this.backendAvailable = false;
            return null;
        }
    }

    private async loadIncidents(page: number = 1, filters: Record<string, any> = {}) {
        if (!this.backendAvailable) {
            return null;
        }
        try {
            const response = await apiService.getIncidents(page, this.incidentsState.itemsPerPage, filters);
            this.incidents = response.incidents;
            return response;
        } catch (error) {
            console.error('Failed to load incidents:', error);
            this.backendAvailable = false;
            return null;
        }
    }

    private getInitialPage(): string {
        const hash = window.location.hash.substring(1);
        return navItems.some(item => item.id === hash) ? hash : 'dashboard';
    }
    
    private processAlerts(): Alert[] {
        const { filters, sortColumn, sortDirection } = this.alertsState;

        const filtered = this.alerts.filter(alert => {
            const searchMatch = filters.search.toLowerCase() === '' || 
                                alert.description.toLowerCase().includes(filters.search.toLowerCase()) ||
                                alert.source.toLowerCase().includes(filters.search.toLowerCase());
            const priorityMatch = filters.priority === 'all' || alert.priority === filters.priority;
            const statusMatch = filters.status === 'all' || alert.status === filters.status;
            return searchMatch && priorityMatch && statusMatch;
        });

        return filtered.sort((a, b) => {
            const valA = a[sortColumn];
            const valB = b[sortColumn];
            
            if (valA < valB) return sortDirection === 'asc' ? -1 : 1;
            if (valA > valB) return sortDirection === 'asc' ? 1 : -1;
            return 0;
        });
    }

    private processIncidents(): Incident[] {
        const { filters, sortColumn, sortDirection } = this.incidentsState;

        const filtered = this.incidents.filter(incident => {
            const searchMatch = filters.search.toLowerCase() === '' || 
                                incident.title.toLowerCase().includes(filters.search.toLowerCase()) ||
                                incident.id.toLowerCase().includes(filters.search.toLowerCase());
            const severityMatch = filters.severity === 'all' || incident.severity === filters.severity;
            const statusMatch = filters.status === 'all' || incident.status === filters.status;
            return searchMatch && severityMatch && statusMatch;
        });

        return filtered.sort((a, b) => {
            const valA = a[sortColumn];
            const valB = b[sortColumn];
            
            if (valA < valB) return sortDirection === 'asc' ? -1 : 1;
            if (valA > valB) return sortDirection === 'asc' ? 1 : -1;
            return 0;
        });
    }

    private render() {
        this.appContainer.innerHTML = ''; // Clear previous content

        // Show login page if not authenticated
        if (!this.authState.isAuthenticated) {
            const loginPage = renderLoginPage(
                this.handleLogin.bind(this),
                this.loginError,
                this.loginLoading
            );
            this.appContainer.appendChild(loginPage);
            return;
        }

        const header = renderHeader(this.activePage, this.authState.user, this.handleLogout.bind(this));
        let mainContent: HTMLElement;

        if (this.isLoading) {
            mainContent = this.renderLoadingState();
        } else {
            switch(this.activePage) {
                case 'dashboard':
                    mainContent = renderDashboard(this.getStatCards(), this.getRecentAlerts());
                    break;
                case 'alerts': {
                    const processedAlerts = this.processAlerts();
                    const paginatedAlerts = processedAlerts.slice(
                        (this.alertsState.currentPage - 1) * this.alertsState.itemsPerPage,
                        this.alertsState.currentPage * this.alertsState.itemsPerPage
                    );
                    mainContent = renderAlertsPage(paginatedAlerts, processedAlerts.length, this.alertsState, this.authState.user);
                    break;
                }
                case 'incidents': {
                    const processedIncidents = this.processIncidents();
                    const paginatedIncidents = processedIncidents.slice(
                        (this.incidentsState.currentPage - 1) * this.incidentsState.itemsPerPage,
                        this.incidentsState.currentPage * this.incidentsState.itemsPerPage
                    );
                    mainContent = renderIncidentsPage(paginatedIncidents, processedIncidents.length, this.incidentsState, this.alerts);
                    break;
                }
                case 'analytics':
                    mainContent = renderAnalyticsPage(this.authState.user);
                    break;
                case 'rl_model':
                    mainContent = renderRLModelPage(
                        this.modelMetrics || this.dashboardStats?.model_metrics || null
                    );
                    break;
                case 'reports':
                    mainContent = renderReportsPage(this.authState.user);
                    break;
                default:
                    mainContent = renderDashboard();
            }
        }

        this.appContainer.appendChild(header);
        this.appContainer.appendChild(mainContent);

        // Initialize chart if on dashboard
        if (this.activePage === 'dashboard' && !this.isLoading) {
            this.initializeDashboardCharts();
        }

        // Initialize incidents page event listeners
        if (this.activePage === 'incidents' && !this.isLoading) {
            setupIncidentsEventListeners(() => this.loadIncidents(), this.alerts);
        }

        // Initialize reports page event listeners
        if (this.activePage === 'reports' && !this.isLoading) {
            const { setupReportsEventListeners } = require('./pages/ReportsPage');
            setupReportsEventListeners();
        }
    }

    private getStatCards(): StatCardData[] {
        if (!this.dashboardStats) {
            return defaultStatCards;
        }

    const { total_alerts, critical_alerts, open_incidents, model_metrics } = this.dashboardStats;
    const formatNumber = (value: number) => value.toLocaleString();
    const accuracyValue = model_metrics.accuracy > 1 ? model_metrics.accuracy : model_metrics.accuracy * 100;
    const accuracyPercent = `${accuracyValue.toFixed(1)}%`;

        return [
            { title: 'Active Alerts', value: formatNumber(total_alerts), icon: 'shield_with_heart', colorClass: 'icon-orange' },
            { title: 'Critical Alerts', value: formatNumber(critical_alerts), icon: 'warning', colorClass: 'icon-blue' },
            { title: 'Open Incidents', value: formatNumber(open_incidents), icon: 'report', colorClass: 'icon-purple' },
            { title: 'Model Accuracy', value: accuracyPercent, icon: 'model_training', colorClass: 'icon-green' },
        ];
    }

    private getRecentAlerts(): Alert[] {
        const sourceAlerts = this.dashboardStats?.recent_alerts?.length ? this.dashboardStats.recent_alerts : this.alerts;
        const sorted = [...sourceAlerts].sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
        const highPriority = sorted.filter(alert => alert.priority === 'critical' || alert.priority === 'high');
        return (highPriority.length >= 4 ? highPriority : sorted).slice(0, 4);
    }

    private renderLoadingState(): HTMLElement {
        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'main-content';
        loadingDiv.innerHTML = `
            <div class="loading-container">
                <div class="loading-spinner"></div>
                <p>Loading data from backend...</p>
            </div>
        `;
        return loadingDiv;
    }

    private initializeDashboardCharts() {
        // Initialize traffic chart if it exists
        const chartContainer = document.getElementById('trafficChart');
        if (chartContainer) {
            createTrafficChart();
        }
    }

    private attachEventListeners() {
        // --- CLICK LISTENER --- for navigation, pagination buttons, etc.
        this.appContainer.addEventListener('click', (e) => {
            const target = e.target as HTMLElement;
            
            // Navigation
            if (target.closest('.nav-link')) {
                const navLink = target.closest('.nav-link') as HTMLElement;
                const page = navLink.dataset.page;
                if (page && page !== this.activePage) {
                    // Clean up chart when leaving dashboard
                    if (this.activePage === 'dashboard') {
                        const { destroyTrafficChart } = require('./components/Chart');
                        destroyTrafficChart();
                    }
                    
                    this.activePage = page;
                    window.location.hash = page;
                    this.render();
                }
            }

            // Pagination
            if (target.closest('.pagination-btn')) {
                if (this.activePage === 'alerts') this.handleAlertsPagination(target);
                if (this.activePage === 'incidents') this.handleIncidentsPagination(target);
            }

            // Advanced filters toggle button
            if (target.closest('#toggle-filters-btn')) {
                this.toggleAdvancedFilters();
            }

            // Export CSV button
            if (target.closest('#export-csv-btn')) {
                this.exportAlertsCSV();
            }

            // Refresh alerts button
            if (target.closest('#refresh-alerts-btn')) {
                this.refreshAlerts();
            }

            // Apply filters button
            if (target.closest('#apply-filters-btn')) {
                this.applyAdvancedFilters();
            }

            // Clear filters button
            if (target.closest('#clear-filters-btn')) {
                this.clearAllFilters();
            }

            // Acknowledge alert button
            if (target.closest('.ack-alert-btn')) {
                const btn = target.closest('.ack-alert-btn') as HTMLElement;
                const alertId = btn.dataset.alertId;
                if (alertId) {
                    this.acknowledgeAlert(alertId);
                }
            }

            // Mark as false positive button
            if (target.closest('.fp-alert-btn')) {
                const btn = target.closest('.fp-alert-btn') as HTMLElement;
                const alertId = btn.dataset.alertId;
                if (alertId) {
                    this.markAlertFalsePositive(alertId);
                }
            }

            // View alert details button
            if (target.closest('.view-alert-btn')) {
                const btn = target.closest('.view-alert-btn') as HTMLElement;
                const alertId = btn.dataset.alertId;
                if (alertId) {
                    this.viewAlertDetails(alertId);
                }
            }

            // Table sorting - for both alerts and incidents
            if (target.closest('.sortable')) {
                const th = target.closest('.sortable') as HTMLElement;
                const sortKey = th.dataset.sortKey;
                if (sortKey) {
                    if (this.activePage === 'alerts') {
                        this.handleAlertsSort(sortKey as keyof Alert);
                    }
                    if (this.activePage === 'incidents') {
                        this.handleIncidentsSort(sortKey as keyof Incident);
                    }
                }
            }

            // Incident row expansion
            if (target.closest('.incident-row')) {
                const row = target.closest('.incident-row') as HTMLElement;
                const incidentId = row.dataset.incidentId;
                if (incidentId) {
                    this.toggleIncidentExpansion(incidentId);
                }
            }
        });
        
        // --- CHANGE LISTENER --- for select dropdowns and advanced filter inputs
        this.appContainer.addEventListener('change', (e) => {
            const target = e.target as HTMLElement;
            if (target.closest('.filter-select')) {
                const select = target as HTMLSelectElement;
                if (this.activePage === 'alerts') {
                    // Check if it's a basic filter (priority/status) or advanced filter
                    const filterType = select.dataset.filter;
                    if (filterType === 'priority' || filterType === 'status') {
                        this.handleAlertsFilterChange(select);
                    } else {
                        // Advanced filter - update state but don't apply yet
                        this.handleAdvancedFilterChange(select);
                    }
                }
                if (this.activePage === 'incidents') {
                    this.handleIncidentsFilterChange(select);
                }
            }

            // Advanced filter inputs (text, number, date)
            if (target.closest('.filter-input')) {
                const input = target as HTMLInputElement;
                if (this.activePage === 'alerts') {
                    this.handleAdvancedFilterChange(input);
                }
            }
        });
        
        // --- INPUT LISTENER --- for search fields (updates as you type)
        this.appContainer.addEventListener('input', (e) => {
            const target = e.target as HTMLElement;
            if (target.closest('.search-input')) {
                if (this.activePage === 'alerts') this.handleAlertsSearch(target as HTMLInputElement);
                if (this.activePage === 'incidents') this.handleIncidentsSearch(target as HTMLInputElement);
            }
        });

        // Handle browser back/forward
        window.addEventListener('hashchange', () => {
            this.activePage = this.getInitialPage();
            this.render();
        });
    }

    // --- ALERTS PAGE EVENT HANDLERS ---
    private handleAlertsPagination(target: HTMLElement) {
        const btn = target.closest('.pagination-btn') as HTMLElement;
        const page = parseInt(btn.dataset.page || '1');
        if (page !== this.alertsState.currentPage) {
            this.alertsState.currentPage = page;
            this.loadAlerts(page, this.alertsState.filters).then(() => {
                this.render();
            });
        }
    }

    private handleAlertsFilterChange(select: HTMLSelectElement) {
        const filterType = select.dataset.filter;
        const value = select.value;
        
        if (filterType && value) {
            if (filterType === 'priority') {
                this.alertsState.filters.priority = value as 'all' | Alert['priority'];
            } else if (filterType === 'status') {
                this.alertsState.filters.status = value as 'all' | Alert['status'];
            }
            this.alertsState.currentPage = 1;
            this.loadAlerts(1, this.alertsState.filters).then(() => {
                this.render();
            });
        }
    }

    private handleAlertsSearch(input: HTMLInputElement) {
        this.alertsState.filters.search = input.value;
        this.alertsState.currentPage = 1;
        this.loadAlerts(1, this.alertsState.filters).then(() => {
            this.render();
        });
    }

    private handleAdvancedFilterChange(element: HTMLInputElement | HTMLSelectElement) {
        const filterType = element.dataset.filter as keyof AlertsState['filters'];
        const value = element.value;
        
        if (!filterType) return;

        // Update filter state based on type
        switch (filterType) {
            case 'severity':
            case 'className':
            case 'srcIp':
            case 'dstIp':
            case 'startTime':
            case 'endTime':
                (this.alertsState.filters as any)[filterType] = value || undefined;
                break;
            case 'minConfidence':
            case 'maxConfidence':
                (this.alertsState.filters as any)[filterType] = value ? parseFloat(value) : undefined;
                break;
        }
    }

    private applyAdvancedFilters() {
        this.alertsState.currentPage = 1;
        this.loadAlerts(1, this.alertsState.filters).then(() => {
            this.render();
        });
    }

    private clearAllFilters() {
        // Reset all filters to defaults
        this.alertsState.filters = {
            priority: 'all',
            status: 'all',
            search: '',
            severity: undefined,
            className: undefined,
            srcIp: undefined,
            dstIp: undefined,
            minConfidence: undefined,
            maxConfidence: undefined,
            startTime: undefined,
            endTime: undefined,
        };
        this.alertsState.currentPage = 1;
        this.loadAlerts(1, this.alertsState.filters).then(() => {
            this.render();
        });
    }

    private toggleAdvancedFilters() {
        const advancedFilters = document.getElementById('advanced-filters');
        if (advancedFilters) {
            const isHidden = advancedFilters.style.display === 'none';
            advancedFilters.style.display = isHidden ? 'block' : 'none';
        }
    }

    private async acknowledgeAlert(alertId: string) {
        try {
            const notes = prompt('Add acknowledgment notes (optional):');
            await apiService.acknowledgeAlert(alertId, notes || undefined);
            
            // Update local alert status
            const matchedAlert = this.alerts.find(a => a.id === alertId);
            if (matchedAlert) {
                matchedAlert.status = 'resolved';
                if (notes) matchedAlert.notes = notes;
            }
            
            toast.show({
                message: 'Alert acknowledged successfully',
                type: 'success',
                duration: 3000
            });
            
            this.render();
        } catch (error) {
            console.error('Failed to acknowledge alert:', error);
            toast.show({
                message: 'Failed to acknowledge alert. Please try again.',
                type: 'error',
                duration: 4000
            });
        }
    }

    private async markAlertFalsePositive(alertId: string) {
        try {
            const feedback = prompt('Why is this a false positive? (optional):');
            await apiService.markAlertFalsePositive(alertId, feedback || undefined);
            
            // Update local alert status
            const matchedAlert = this.alerts.find(a => a.id === alertId);
            if (matchedAlert) {
                matchedAlert.status = 'false_positive';
                if (feedback) matchedAlert.notes = feedback;
            }
            
            toast.show({
                message: 'Alert marked as false positive',
                type: 'success',
                duration: 3000
            });
            
            this.render();
        } catch (error) {
            console.error('Failed to mark alert as false positive:', error);
            toast.show({
                message: 'Failed to mark alert as false positive. Please try again.',
                type: 'error',
                duration: 4000
            });
        }
    }

    private viewAlertDetails(alertId: string) {
        const matchedAlert = this.alerts.find(a => a.id === alertId);
        if (!matchedAlert) {
            console.error('Alert not found:', alertId);
            return;
        }

        // Format alert details
        const details = `
Alert Details:
--------------
ID: ${matchedAlert.id}
Priority: ${matchedAlert.priority}
Severity: ${matchedAlert.severity || 'N/A'}
Status: ${matchedAlert.status}
Class: ${matchedAlert.className || 'Unknown'}
Confidence: ${matchedAlert.confidence !== undefined ? (matchedAlert.confidence * 100).toFixed(1) + '%' : 'N/A'}

Network:
Source IP: ${matchedAlert.srcIp || matchedAlert.source || 'N/A'}
Source Port: ${matchedAlert.srcPort || 'N/A'}
Destination IP: ${matchedAlert.dstIp || 'N/A'}
Destination Port: ${matchedAlert.dstPort || 'N/A'}
Protocol: ${matchedAlert.protocol || 'N/A'}

Description: ${matchedAlert.description}
Timestamp: ${new Date(matchedAlert.timestamp).toLocaleString()}

Model: ${matchedAlert.modelVersion || 'N/A'}
Assigned To: ${matchedAlert.assignedTo || 'Unassigned'}
Notes: ${matchedAlert.notes || 'None'}
        `.trim();

        window.alert(details);
    }

    private exportAlertsCSV() {
        const processedAlerts = this.processAlerts();
        if (processedAlerts.length === 0) {
            toast.show({
                message: 'No alerts to export',
                type: 'warning',
                duration: 3000
            });
            return;
        }

        const filename = generateCSVFilename('alerts');
        exportAlertsToCSV(processedAlerts, filename);
        toast.show({
            message: `Exported ${processedAlerts.length} alerts to ${filename}`,
            type: 'success',
            duration: 4000
        });
    }

    private refreshAlerts() {
        this.loadAlerts(this.alertsState.currentPage, this.alertsState.filters).then(() => {
            this.render();
            toast.show({
                message: 'Alerts refreshed',
                type: 'success',
                duration: 2000
            });
        }).catch((error) => {
            console.error('Failed to refresh alerts:', error);
            toast.show({
                message: 'Failed to refresh alerts',
                type: 'error',
                duration: 3000
            });
        });
    }

    // --- INCIDENTS PAGE EVENT HANDLERS ---
    private handleIncidentsPagination(target: HTMLElement) {
        const btn = target.closest('.pagination-btn') as HTMLElement;
        const page = parseInt(btn.dataset.page || '1');
        if (page !== this.incidentsState.currentPage) {
            this.incidentsState.currentPage = page;
            this.loadIncidents(page, this.incidentsState.filters).then(() => {
                this.render();
            });
        }
    }

    private handleIncidentsFilterChange(select: HTMLSelectElement) {
        const filterType = select.dataset.filter;
        const value = select.value;
        
        if (filterType && value) {
            if (filterType === 'severity') {
                this.incidentsState.filters.severity = value as 'all' | Incident['severity'];
            } else if (filterType === 'status') {
                this.incidentsState.filters.status = value as 'all' | Incident['status'];
            }
            this.incidentsState.currentPage = 1;
            this.loadIncidents(1, this.incidentsState.filters).then(() => {
                this.render();
            });
        }
    }

    private handleIncidentsSearch(input: HTMLInputElement) {
        this.incidentsState.filters.search = input.value;
        this.incidentsState.currentPage = 1;
        this.loadIncidents(1, this.incidentsState.filters).then(() => {
            this.render();
        });
    }

    private handleAlertsSort(sortKey: keyof Alert) {
        // Toggle sort direction if clicking the same column
        if (this.alertsState.sortColumn === sortKey) {
            this.alertsState.sortDirection = this.alertsState.sortDirection === 'asc' ? 'desc' : 'asc';
        } else {
            this.alertsState.sortColumn = sortKey;
            this.alertsState.sortDirection = 'desc';
        }
        this.render();
    }

    private handleIncidentsSort(sortKey: keyof Incident) {
        // Toggle sort direction if clicking the same column
        if (this.incidentsState.sortColumn === sortKey) {
            this.incidentsState.sortDirection = this.incidentsState.sortDirection === 'asc' ? 'desc' : 'asc';
        } else {
            this.incidentsState.sortColumn = sortKey;
            this.incidentsState.sortDirection = 'desc';
        }
        this.render();
    }

    private toggleIncidentExpansion(incidentId: string) {
        // Toggle expansion: if already expanded, collapse it; otherwise expand it
        if (this.incidentsState.expandedIncidentId === incidentId) {
            this.incidentsState.expandedIncidentId = null;
        } else {
            this.incidentsState.expandedIncidentId = incidentId;
        }
        this.render();
    }

    // --- AUTHENTICATION EVENT HANDLERS ---
    private async handleLogin(emailOrUsername: string, password: string): Promise<void> {
        this.loginLoading = true;
        this.loginError = '';
        this.render();

        const result = await authService.login(emailOrUsername, password);

        if (!result.success) {
            this.loginError = result.error || 'Login failed. Please try again.';
            this.loginLoading = false;
            this.render();
        } else {
            // Success - auth service will trigger re-render via subscription
            this.loginError = '';
            this.loginLoading = false;
        }
    }

    private async handleLogout(): Promise<void> {
        await authService.logout();
        // Clear app data
        this.alerts = [];
        this.incidents = [];
        this.dashboardStats = null;
        this.modelMetrics = null;
        this.activePage = 'dashboard';
        window.location.hash = '';
    }

    // --- RL MODEL EVENT HANDLERS ---
    private async handlePrediction(features: Record<string, number>): Promise<PredictionResult> {
        return await apiService.predict({ features });
    }

    // --- REALTIME CONNECTION HANDLERS ---
    // --- REALTIME CONNECTION HANDLERS ---
    private connectRealtime(): void {
        const realtimeClient = getRealtimeClient();
        
        // Subscribe to SSE events
        realtimeClient.onEvent((message: SSEMessage) => {
            console.log('Realtime event received:', message);
            
            switch (message.type) {
                case 'alert':
                    // Handle new alert
                    if (message.data) {
                        this.handleRealtimeAlert(message.data);
                    }
                    break;
                case 'prediction':
                    // On predictions, lightly refresh alerts and dashboard stats (throttled)
                    this.handleRealtimePrediction();
                    break;
                case 'heartbeat':
                    // Connection is alive
                    console.debug('Heartbeat received');
                    break;
                case 'connected':
                    console.log('Connected to realtime stream');
                    toast.show({
                        message: 'Connected to live updates',
                        type: 'success',
                        duration: 2000
                    });
                    break;
                case 'error':
                    console.error('SSE error event:', message.data);
                    toast.show({
                        message: 'Connection error. Attempting to reconnect...',
                        type: 'error',
                        duration: 3000
                    });
                    break;
                default:
                    console.log('Unknown event type:', message.type);
            }
        });

    // Connect to the 'predictions' topic for live updates.
    // Note: The alerting service currently writes alerts to the database and integrations,
    // not to a Kafka 'alerts' topic. Streaming 'predictions' ensures realtime UI updates.
    realtimeClient.connect('predictions');
    }
    private disconnectRealtime(): void {
        const realtimeClient = getRealtimeClient();
        realtimeClient.disconnect();
    }

    private async handleRealtimePrediction() {
        const now = Date.now();
        // Throttle to at most once every 5 seconds
        if (this.realtimeRefreshInFlight || (now - this.lastRealtimeRefreshMs) < 5000) {
            return;
        }
        this.realtimeRefreshInFlight = true;
        try {
            // Refresh alerts current page and dashboard stats in parallel
            await Promise.all([
                this.loadAlerts(this.alertsState.currentPage, this.alertsState.filters),
                (async () => {
                    try {
                        const stats = await apiService.getDashboardStats();
                        this.dashboardStats = stats;
                    } catch (e) {
                        // ignore
                    }
                })()
            ]);
            this.lastRealtimeRefreshMs = Date.now();
            this.render();
        } finally {
            this.realtimeRefreshInFlight = false;
        }
    }

    private handleRealtimeAlert(alert: Alert): void {
        // Add new alert to the beginning of the list
        this.alerts.unshift(alert);
        
        // Keep only the latest 100 alerts in memory
        if (this.alerts.length > 100) {
            this.alerts = this.alerts.slice(0, 100);
        }
        
        // Show toast notification
        const priorityIcon = alert.priority === 'critical' ? '🚨' : alert.priority === 'high' ? '⚠️' : 'ℹ️';
        toast.show({
            message: `${priorityIcon} New ${alert.priority} alert: ${alert.description.substring(0, 50)}...`,
            type: alert.priority === 'critical' ? 'error' : alert.priority === 'high' ? 'warning' : 'info',
            duration: 5000
        });
        
        // Re-render if on alerts page
        if (this.activePage === 'alerts') {
            this.render();
        }
    }

    private handleRealtimeIncident(incident: Incident): void {
        // Add new incident to the beginning of the list
        this.incidents.unshift(incident);
        
        // Keep only the latest 100 incidents in memory
        if (this.incidents.length > 100) {
            this.incidents = this.incidents.slice(0, 100);
        }
        
        // Show toast notification
        toast.show({
            message: `New incident: ${incident.title}`,
            type: incident.severity === 'critical' ? 'error' : 'warning',
            duration: 5000
        });
        
        // Re-render if on incidents page
        if (this.activePage === 'incidents') {
            this.render();
        }
    }
}

// Initialize the app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new App();
});