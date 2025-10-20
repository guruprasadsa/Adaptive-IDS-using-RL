import { NavItem, StatCardData, Alert, Incident } from './types';
import { DashboardStats, ModelMetrics } from './api';

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

const seedAlerts: Alert[] = [
    {
        id: 'alert-1',
        priority: 'critical',
        description: 'Potential ransomware encryption behaviour detected on finance workstation',
        source: '10.0.12.6',
        timestamp: new Date(Date.now() - 5 * 60_000).toISOString(),
        status: 'new',
        type: 'malware',
        confidence: 0.96,
    },
    {
        id: 'alert-2',
        priority: 'high',
        description: 'Unusual outbound connections towards rare ASN range',
        source: '10.0.31.44',
        timestamp: new Date(Date.now() - 15 * 60_000).toISOString(),
        status: 'investigating',
        type: 'network_anomaly',
        confidence: 0.88,
    },
    {
        id: 'alert-3',
        priority: 'high',
        description: 'Spike in failed authentication attempts detected on VPN gateway',
        source: '198.51.100.83',
        timestamp: new Date(Date.now() - 25 * 60_000).toISOString(),
        status: 'new',
        type: 'brute_force',
        confidence: 0.82,
    },
    {
        id: 'alert-4',
        priority: 'medium',
        description: 'Data transfer volume exceeded baseline for engineering subnet',
        source: '203.0.113.22',
        timestamp: new Date(Date.now() - 45 * 60_000).toISOString(),
        status: 'resolved',
        type: 'data_exfiltration',
        confidence: 0.74,
    },
];

const alertTypes = ['malware', 'network_anomaly', 'brute_force', 'data_exfiltration', 'command_control', 'policy_violation'];
const alertDescriptions = [
    'Suspicious lateral movement detected between production hosts',
    'Outbound DNS requests match known tunnelling behaviour',
    'Privileged account login from unusual geography',
    'Large volume of outbound SMTP traffic flagged by DLP policies',
    'Endpoint behavioural analytics flagged persistence technique',
    'High entropy payload observed over standard HTTP port',
];

const incidentSummaries = [
    'Multiple hosts generated coordinated brute-force and credential stuffing alerts against the perimeter VPN concentrator.',
    'Indicators of possible data staging followed by exfiltration through DNS were observed on analytics cluster nodes.',
    'Web application logs confirm SQL injection payloads exploited an outdated ORM layer resulting in lateral movement.',
    'Malware beaconing behaviour isolated to marketing workstations following successful phishing campaign.',
];

export const generateMockData = (): { alerts: Alert[]; incidents: Incident[] } => {
    const now = Date.now();
    const priorities: Alert['priority'][] = ['critical', 'high', 'medium', 'low'];
    const statuses: Alert['status'][] = ['new', 'investigating', 'resolved', 'false_positive'];

    const alerts: Alert[] = seedAlerts.map((alert, index) => ({
        ...alert,
        id: `alert-${index + 1}`,
    }));

    const generatedAlerts = Array.from({ length: 40 }, (_, i) => {
        const priority = priorities[Math.floor(Math.random() * priorities.length)];
        const status = statuses[Math.floor(Math.random() * statuses.length)];
        const type = alertTypes[Math.floor(Math.random() * alertTypes.length)];
        const description = alertDescriptions[Math.floor(Math.random() * alertDescriptions.length)];
        const source = `10.${Math.floor(Math.random() * 200)}.${Math.floor(Math.random() * 200)}.${Math.floor(Math.random() * 200)}`;
        const timestamp = new Date(now - Math.random() * 72 * 60 * 60_000).toISOString();
        const confidence = Number((0.65 + Math.random() * 0.3).toFixed(2));

        return {
            id: `alert-${seedAlerts.length + i + 1}`,
            priority,
            description,
            source,
            timestamp,
            status,
            type,
            confidence,
        } satisfies Alert;
    });

    alerts.push(...generatedAlerts);
    alerts.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());

    const incidentOneAlertIds = alerts.slice(0, 4).map(alert => alert.id);
    const incidentTwoAlertIds = alerts.slice(4, 9).map(alert => alert.id);
    const incidentThreeAlertIds = alerts.slice(9, 14).map(alert => alert.id);
    const incidentFourAlertIds = alerts.slice(14, 18).map(alert => alert.id);

    const incidents: Incident[] = [
        {
            id: 'incident-1',
            title: 'Coordinated brute-force attack on VPN gateway',
            status: 'investigating',
            severity: 'high',
            assignedTo: 'SOC Tier 2',
            createdAt: new Date(now - 18 * 60 * 60_000).toISOString(),
            lastUpdatedAt: new Date(now - 2 * 60 * 60_000).toISOString(),
            relatedAlertIds: incidentOneAlertIds,
            summary: incidentSummaries[0],
            description: 'Analysts observed a surge in authentication failures originating from multiple remote networks targeting the VPN gateway. Rate limiting has been enabled while additional detections are deployed.',
            affectedSystems: 6,
            alertsCount: incidentOneAlertIds.length,
        },
        {
            id: 'incident-2',
            title: 'Potential data exfiltration via DNS tunnelling',
            status: 'open',
            severity: 'critical',
            assignedTo: 'Threat Hunter',
            createdAt: new Date(now - 36 * 60 * 60_000).toISOString(),
            lastUpdatedAt: new Date(now - 3 * 60 * 60_000).toISOString(),
            relatedAlertIds: incidentTwoAlertIds,
            summary: incidentSummaries[1],
            description: 'Endpoint telemetry indicates staged archives prior to a spike in DNS queries. Outbound firewall rules are being tightened while packet captures are reviewed.',
            affectedSystems: 3,
            alertsCount: incidentTwoAlertIds.length,
        },
        {
            id: 'incident-3',
            title: 'Web application compromise through SQL injection',
            status: 'contained',
            severity: 'high',
            assignedTo: 'AppSec',
            createdAt: new Date(now - 5 * 24 * 60 * 60_000).toISOString(),
            lastUpdatedAt: new Date(now - 24 * 60 * 60_000).toISOString(),
            relatedAlertIds: incidentThreeAlertIds,
            summary: incidentSummaries[2],
            description: 'The vulnerable endpoint has been isolated and patched. Logs are being reviewed to determine the scope of access and data exposure.',
            affectedSystems: 2,
            alertsCount: incidentThreeAlertIds.length,
        },
        {
            id: 'incident-4',
            title: 'Phishing-driven malware outbreak contained',
            status: 'resolved',
            severity: 'medium',
            assignedTo: 'SOC Tier 1',
            createdAt: new Date(now - 9 * 24 * 60 * 60_000).toISOString(),
            lastUpdatedAt: new Date(now - 6 * 24 * 60 * 60_000).toISOString(),
            relatedAlertIds: incidentFourAlertIds,
            summary: incidentSummaries[3],
            description: 'Affected hosts were rebuilt and credentials rotated. User awareness campaign initiated for impacted business unit.',
            affectedSystems: 5,
            alertsCount: incidentFourAlertIds.length,
        },
    ];

    return { alerts, incidents };
};

export const fallbackModelMetrics: ModelMetrics = {
    accuracy: 0.93,
    precision_macro: 0.87,
    recall_macro: 0.85,
    f1_macro: 0.86,
    roc_auc: 0.9,
    balanced_accuracy: 0.88,
    total_predictions: 12500,
    false_positives: 420,
    false_negatives: 310,
    true_positives: 6200,
    true_negatives: 5570,
};

export const buildFallbackDashboardStats = (alerts: Alert[], incidents: Incident[]): DashboardStats => {
    const criticalAlerts = alerts.filter(alert => alert.priority === 'critical');
    const openIncidents = incidents.filter(incident => incident.status === 'open' || incident.status === 'investigating');

    return {
        total_alerts: alerts.length,
        critical_alerts: criticalAlerts.length,
        open_incidents: openIncidents.length,
        total_incidents: incidents.length,
        model_metrics: fallbackModelMetrics,
        recent_alerts: alerts.slice(0, 5),
        recent_incidents: incidents.slice(0, 5),
    } satisfies DashboardStats;
};

