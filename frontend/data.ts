import { NavItem, StatCardData } from './types';

export const navItems: NavItem[] = [
    { id: 'dashboard', label: 'Dashboard', icon: 'dashboard' },
    { id: 'alerts', label: 'Alerts', icon: 'notifications_active' },
    { id: 'incidents', label: 'Incidents', icon: 'emergency_home' },
    { id: 'analytics', label: 'Analytics', icon: 'analytics' },
    { id: 'rl_model', label: 'RL Model', icon: 'neurology' },
    { id: 'reports', label: 'Reports', icon: 'summarize' },
];

export const defaultStatCards: StatCardData[] = [
    { title: 'Active Alerts', value: '--', icon: 'shield_with_heart', colorClass: 'icon-orange' },
    { title: 'Critical Alerts', value: '--', icon: 'warning', colorClass: 'icon-blue' },
    { title: 'Open Incidents', value: '--', icon: 'report', colorClass: 'icon-purple' },
    { title: 'Model Accuracy', value: '--', icon: 'model_training', colorClass: 'icon-green' },
];
// Note: Demo data has been removed so the UI only displays real backend data.

