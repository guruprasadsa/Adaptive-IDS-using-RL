// --- IMPORT TYPES ---
import { Alert, AlertsState, Incident, IncidentsState } from './types';
import { apiService, DashboardStats, AlertsResponse, IncidentsResponse } from './api';

// --- NAV ITEMS ---
import { navItems } from './data';

// --- IMPORT PAGE RENDERERS ---
import { renderDashboard } from './pages/Dashboard';
import { renderAlertsPage, renderAlertsPageContent } from './pages/AlertsPage';
import { renderIncidentsPage, renderIncidentsPageContent } from './pages/IncidentsPage';
import { renderPlaceholderPage } from './pages/PlaceholderPage';

// --- IMPORT COMPONENT RENDERERS ---
import { renderSidebar } from './components/Sidebar';
import { renderHeader } from './components/Header';
import { createTrafficChart } from './components/Chart';

// --- APP LOGIC ---

class App {
    private appContainer: HTMLElement;
    private activePage: string;
    private currentTheme: 'light' | 'dark';
    private alerts: Alert[] = [];
    private incidents: Incident[] = [];
    private dashboardStats: DashboardStats | null = null;
    private isLoading: boolean = false;
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

        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        this.currentTheme = localStorage.getItem('theme') as 'light' | 'dark' || (prefersDark ? 'dark' : 'light');
        document.body.dataset.theme = this.currentTheme;

        this.loadInitialData();
        this.render();
        this.attachEventListeners();
    }
    
    private async loadInitialData() {
        try {
            this.isLoading = true;
            this.render(); // Show loading state

            // Load dashboard stats
            this.dashboardStats = await apiService.getDashboardStats();
            
            // Load initial alerts and incidents
            const alertsResponse = await apiService.getAlerts(1, 50);
            const incidentsResponse = await apiService.getIncidents(1, 50);
            
            this.alerts = alertsResponse.alerts;
            this.incidents = incidentsResponse.incidents;
            
        } catch (error) {
            console.error('Failed to load data from backend:', error);
            // Keep empty datasets if backend is not available
            this.alerts = [];
            this.incidents = [];
        } finally {
            this.isLoading = false;
            this.render();
        }
    }

    private async loadAlerts(page: number = 1, filters: Record<string, any> = {}) {
        try {
            const response = await apiService.getAlerts(page, this.alertsState.itemsPerPage, filters);
            this.alerts = response.alerts;
            return response;
        } catch (error) {
            console.error('Failed to load alerts:', error);
            return null;
        }
    }

    private async loadIncidents(page: number = 1, filters: Record<string, any> = {}) {
        try {
            const response = await apiService.getIncidents(page, this.incidentsState.itemsPerPage, filters);
            this.incidents = response.incidents;
            return response;
        } catch (error) {
            console.error('Failed to load incidents:', error);
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

        const sidebar = renderSidebar(this.activePage);
        const header = renderHeader(this.activePage);
        let mainContent: HTMLElement;

        if (this.isLoading) {
            mainContent = this.renderLoadingState();
        } else {
            switch(this.activePage) {
                case 'dashboard':
                    mainContent = renderDashboard(this.dashboardStats, this.alerts);
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
                    mainContent = renderIncidentsPage(paginatedIncidents, processedIncidents.length, this.incidentsState);
                    break;
                }
                case 'analytics':
                    mainContent = renderPlaceholderPage('Network Analytics');
                    break;
                case 'rl_model':
                    mainContent = renderPlaceholderPage('RL Model Health & Explainability');
                    break;
                case 'reports':
                    mainContent = renderPlaceholderPage('Export Reports');
                    break;
                default:
                    mainContent = renderDashboard();
            }
        }

        this.appContainer.appendChild(sidebar);
        this.appContainer.appendChild(header);
        this.appContainer.appendChild(mainContent);

        // Initialize chart if on dashboard
        if (this.activePage === 'dashboard' && !this.isLoading) {
            this.initializeDashboardCharts();
        }
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
        // Sidebar navigation
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

            // Theme toggle
            if (target.closest('.theme-toggle')) {
                this.toggleTheme();
            }

            // Alerts page events
            if (this.activePage === 'alerts') {
                this.handleAlertsPageEvents(e);
            }

            // Incidents page events
            if (this.activePage === 'incidents') {
                this.handleIncidentsPageEvents(e);
            }
        });

        // Handle browser back/forward
        window.addEventListener('hashchange', () => {
            this.activePage = this.getInitialPage();
            this.render();
        });
    }

    private handleAlertsPageEvents(e: Event) {
        const target = e.target as HTMLElement;
        
        // Pagination
        if (target.closest('.pagination-btn')) {
            const btn = target.closest('.pagination-btn') as HTMLElement;
            const page = parseInt(btn.dataset.page || '1');
            if (page !== this.alertsState.currentPage) {
                this.alertsState.currentPage = page;
                this.loadAlerts(page, this.alertsState.filters).then(() => {
                    this.render();
                });
            }
        }

        // Filter changes
        if (target.closest('.filter-select')) {
            const select = target as HTMLSelectElement;
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

        // Search
        if (target.closest('.search-input')) {
            const input = target as HTMLInputElement;
            const searchTerm = input.value;
            this.alertsState.filters.search = searchTerm;
            this.alertsState.currentPage = 1;
            this.loadAlerts(1, this.alertsState.filters).then(() => {
                this.render();
            });
        }
    }

    private handleIncidentsPageEvents(e: Event) {
        const target = e.target as HTMLElement;
        
        // Pagination
        if (target.closest('.pagination-btn')) {
            const btn = target.closest('.pagination-btn') as HTMLElement;
            const page = parseInt(btn.dataset.page || '1');
            if (page !== this.incidentsState.currentPage) {
                this.incidentsState.currentPage = page;
                this.loadIncidents(page, this.incidentsState.filters).then(() => {
                    this.render();
                });
            }
        }

        // Filter changes
        if (target.closest('.filter-select')) {
            const select = target as HTMLSelectElement;
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

        // Search
        if (target.closest('.search-input')) {
            const input = target as HTMLInputElement;
            const searchTerm = input.value;
            this.incidentsState.filters.search = searchTerm;
            this.incidentsState.currentPage = 1;
            this.loadIncidents(1, this.incidentsState.filters).then(() => {
                this.render();
            });
        }
    }

    private toggleTheme() {
        this.currentTheme = this.currentTheme === 'light' ? 'dark' : 'light';
        localStorage.setItem('theme', this.currentTheme);
        document.body.dataset.theme = this.currentTheme;
        this.render();
    }
}

// Initialize the app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new App();
});
