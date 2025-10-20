// --- IMPORT TYPES ---
import { Alert, AlertsState, Incident, IncidentsState, StatCardData, User, ModelMetrics, PredictionResult, DashboardStats } from './types';
import { apiService } from './api';

// --- IMPORT DATA ---
import { generateMockData, navItems, defaultStatCards, buildFallbackDashboardStats } from './data';

// --- IMPORT PAGE RENDERERS ---
import { renderDashboard } from './pages/Dashboard';
import { renderAlertsPage } from './pages/AlertsPage';
import { renderIncidentsPage } from './pages/IncidentsPage';
import { renderPlaceholderPage } from './pages/PlaceholderPage';
import { renderLoginPage } from './pages/LoginPage';
import { renderRLModelPage } from './pages/RLModelPage';

// --- IMPORT COMPONENT RENDERERS ---
import { renderHeader } from './components/Header';
import { createTrafficChart } from './components/Chart';

// --- IMPORT SERVICES ---
import { authService, AuthState } from './services/authService';

// --- IMPORT UTILITIES ---
import { getRealtimeClient } from './utils/realtimeClient';
import type { SSEMessage } from './types';

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
            // Fallback to mock data if backend is not available
            const { alerts, incidents } = generateMockData();
            this.alerts = alerts;
            this.incidents = incidents;
            this.dashboardStats = buildFallbackDashboardStats(alerts, incidents);
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
                    mainContent = renderAlertsPage(paginatedAlerts, processedAlerts.length, this.alertsState);
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
                    mainContent = renderPlaceholderPage('Network Analytics');
                    break;
                case 'rl_model':
                    mainContent = renderRLModelPage(
                        this.modelMetrics || this.dashboardStats?.model_metrics || null,
                        this.handlePrediction.bind(this)
                    );
                    break;
                case 'reports':
                    mainContent = renderPlaceholderPage('Export Reports');
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
        });
        
        // --- CHANGE LISTENER --- for select dropdowns
        this.appContainer.addEventListener('change', (e) => {
            const target = e.target as HTMLElement;
            if (target.closest('.filter-select')) {
                if (this.activePage === 'alerts') this.handleAlertsFilterChange(target as HTMLSelectElement);
                if (this.activePage === 'incidents') this.handleIncidentsFilterChange(target as HTMLSelectElement);
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
                case 'incident':
                    // Handle new incident
                    if (message.data) {
                        this.handleRealtimeIncident(message.data);
                    }
                    break;
                case 'heartbeat':
                    // Connection is alive
                    break;
                case 'connected':
                    console.log('Connected to realtime stream');
                    break;
                default:
                    console.log('Unknown event type:', message.type);
            }
        });

        // Connect to the stream
        realtimeClient.connect();
    }

    private disconnectRealtime(): void {
        const realtimeClient = getRealtimeClient();
        realtimeClient.disconnect();
    }

    private handleRealtimeAlert(alert: Alert): void {
        // Add new alert to the beginning of the list
        this.alerts.unshift(alert);
        
        // Keep only the latest 100 alerts in memory
        if (this.alerts.length > 100) {
            this.alerts = this.alerts.slice(0, 100);
        }
        
        // Re-render if on alerts page
        if (this.activePage === 'alerts') {
            this.render();
        }
        
        // Show notification (could be enhanced with toast notifications)
        console.log('New alert received:', alert.description);
    }

    private handleRealtimeIncident(incident: Incident): void {
        // Add new incident to the beginning of the list
        this.incidents.unshift(incident);
        
        // Keep only the latest 100 incidents in memory
        if (this.incidents.length > 100) {
            this.incidents = this.incidents.slice(0, 100);
        }
        
        // Re-render if on incidents page
        if (this.activePage === 'incidents') {
            this.render();
        }
        
        // Show notification
        console.log('New incident received:', incident.title);
    }
}

// Initialize the app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new App();
});