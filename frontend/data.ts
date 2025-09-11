import { NavItem, StatCardData, Alert, Incident } from './types';

export const navItems: NavItem[] = [
    { id: 'dashboard', label: 'Dashboard', icon: 'dashboard' },
    { id: 'alerts', label: 'Alerts', icon: 'notifications_active' },
    { id: 'incidents', label: 'Incidents', icon: 'emergency_home' },
    { id: 'analytics', label: 'Analytics', icon: 'analytics' },
    { id: 'rl_model', label: 'RL Model', icon: 'neurology' },
    { id: 'reports', label: 'Reports', icon: 'summarize' },
];

export const statCards: StatCardData[] = [
    { title: 'Active Alerts', value: '12', icon: 'shield_with_heart', colorClass: 'icon-orange' },
    { title: 'Open Incidents', value: '3', icon: 'report', colorClass: 'icon-purple' },
    { title: 'Traffic (24h)', value: '1.2 TB', icon: 'lan', colorClass: 'icon-blue' },
    { title: 'Model Accuracy', value: '99.2%', icon: 'model_training', colorClass: 'icon-green' },
];

const staticRecentAlerts: Alert[] = [
    { id: 'a1', priority: 'critical', description: 'Potential Ransomware Activity Detected', source: '192.168.1.102', timestamp: '2024-07-29T10:30:00Z', status: 'new', type: 'Malware Detection', confidence: 0.95 },
    { id: 'a2', priority: 'high', description: 'Anomalous Outbound Connection', source: '10.0.5.23', timestamp: '2024-07-29T10:27:00Z', status: 'new', type: 'Suspicious Network Activity', confidence: 0.87 },
    { id: 'a3', priority: 'high', description: 'SQL Injection Attempt', source: '203.0.113.45', timestamp: '2024-07-29T10:20:00Z', status: 'new', type: 'Unauthorized Access Attempt', confidence: 0.92 },
    { id: 'a4', priority: 'medium', description: 'Multiple Failed Login Attempts', source: '198.51.100.8', timestamp: '2024-07-29T10:05:00Z', status: 'investigating', type: 'Unauthorized Access Attempt', confidence: 0.78 },
];

export const recentAlerts: Alert[] = staticRecentAlerts;

export let allAlerts: Alert[] = [];
export let allIncidents: Incident[] = [];

export const generateMockData = () => {
    // Generate mock alerts
    const priorities: Alert['priority'][] = ['critical', 'high', 'medium', 'low'];
    const statuses: Alert['status'][] = ['new', 'investigating', 'resolved', 'false_positive'];
    const types = [
        'Suspicious Network Activity', 'Potential DDoS Attack', 'Unauthorized Access Attempt',
        'Malware Detection', 'Data Exfiltration Attempt'
    ];
    const descriptions = [
        'DDoS attack detected on web server', 'Malware signature found in file upload', 
        'Brute force login attempt on SSH', 'Unusual data exfiltration pattern',
        'Port scan from suspicious IP', 'Cross-site scripting attempt',
        'Command & Control server communication', 'Phishing link detected in email'
    ];
    
    const generatedAlerts = Array.from({length: 53}, (_, i) => {
        const priority = priorities[Math.floor(Math.random() * priorities.length)];
        const status = statuses[Math.floor(Math.random() * statuses.length)];
        const type = types[Math.floor(Math.random() * types.length)];
        const desc = descriptions[Math.floor(Math.random() * descriptions.length)];
        const sourceIp = `192.168.${Math.floor(Math.random() * 255)}.${Math.floor(Math.random() * 255)}`;
        const timestamp = new Date(Date.now() - Math.random() * 1000 * 60 * 60 * 24).toISOString();
        const confidence = Math.round(Math.random() * 40 + 60) / 100; // 0.6 to 1.0
        return { 
            id: `a${i+5}`, 
            priority, 
            status, 
            type,
            description: desc, 
            source: sourceIp, 
            timestamp,
            confidence
        };
    });
    
    allAlerts = [...staticRecentAlerts, ...generatedAlerts];
    
    // Generate mock incidents from alerts
    allIncidents = [
        { id: 'inc-1', title: 'Coordinated Brute-Force Attack on Core Servers', status: 'investigating', severity: 'critical', assignedTo: 'Admin', createdAt: new Date(Date.now() - 86400000 * 2).toISOString(), lastUpdatedAt: new Date(Date.now() - 3600000).toISOString(), relatedAlertIds: ['a5', 'a8', 'a12'], summary: 'Multiple SSH brute-force attempts from a network of IPs targeting production servers.', description: 'Investigation of suspicious activity', affectedSystems: 5, alertsCount: 12 },
        { id: 'inc-2', title: 'Potential Data Exfiltration via DNS Tunneling', status: 'open', severity: 'high', assignedTo: 'Analyst 1', createdAt: new Date(Date.now() - 86400000).toISOString(), lastUpdatedAt: new Date(Date.now() - 7200000).toISOString(), relatedAlertIds: ['a6', 'a10'], summary: 'Anomalous DNS query patterns suggest data is being exfiltrated from an internal host.', description: 'Investigation of malicious activity', affectedSystems: 2, alertsCount: 8 },
        { id: 'inc-3', title: 'Web Server Compromise via SQL Injection', status: 'resolved', severity: 'high', assignedTo: 'Admin', createdAt: new Date(Date.now() - 86400000 * 5).toISOString(), lastUpdatedAt: new Date(Date.now() - 86400000 * 3).toISOString(), relatedAlertIds: ['a7', 'a11', 'a15', 'a20'], summary: 'Web server was targeted with SQL injection, leading to unauthorized database access. The vulnerability has been patched.', description: 'Investigation of unauthorized activity', affectedSystems: 1, alertsCount: 15 },
        { id: 'inc-4', title: 'Malware Outbreak in Marketing Department', status: 'resolved', severity: 'medium', assignedTo: 'Analyst 2', createdAt: new Date(Date.now() - 86400000 * 10).toISOString(), lastUpdatedAt: new Date(Date.now() - 86400000 * 8).toISOString(), relatedAlertIds: ['a9', 'a14'], summary: 'Phishing email led to a malware infection on two marketing workstations. Affected machines have been reimaged.', description: 'Investigation of suspicious activity', affectedSystems: 2, alertsCount: 6 },
    ];

    return { alerts: allAlerts, incidents: allIncidents };
};
