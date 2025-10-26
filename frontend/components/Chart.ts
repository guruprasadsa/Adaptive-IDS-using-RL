import type { Chart } from 'chart.js';
import type { SSEMessage } from '../types';
import { getRealtimeClient } from '../utils/realtimeClient';

let trafficChartInstance: Chart | null = null;
let chartUpdateInterval: number | null = null;
let sseUnsubscribe: (() => void) | null = null;

interface TrafficDataPoint {
    timestamp: number;
    packets: number;
    bytes: number;
}

// Store last 30 data points (30 seconds of data)
const trafficHistory: TrafficDataPoint[] = [];
const MAX_HISTORY = 30;

// Track recent predictions/alerts for traffic calculation
let recentPredictionsCount = 0;
let lastPredictionTime = 0;

// Initialize with zero baseline data
const initializeTrafficHistory = () => {
    const now = Date.now();
    for (let i = MAX_HISTORY - 1; i >= 0; i--) {
        trafficHistory.push({
            timestamp: now - (i * 1000), // 1 second intervals
            packets: 0,
            bytes: 0
        });
    }
};

// Update traffic data from real predictions
const updateTrafficFromPrediction = (predictionData: any) => {
    const now = Date.now();
    
    // Count predictions in the last second
    if (now - lastPredictionTime < 1000) {
        recentPredictionsCount++;
    } else {
        recentPredictionsCount = 1;
        lastPredictionTime = now;
    }
    
    // Each prediction represents a network flow
    // Estimate packets and bytes from flow data if available
    const packets = predictionData?.packet_count || recentPredictionsCount * 10; // ~10 packets per flow
    const bytes = predictionData?.total_bytes || packets * 1000; // ~1KB per packet
    
    // Add to current second's data or create new point
    const lastPoint = trafficHistory[trafficHistory.length - 1];
    if (lastPoint && (now - lastPoint.timestamp) < 1000) {
        // Accumulate in current second
        lastPoint.packets += packets;
        lastPoint.bytes += bytes;
    } else {
        // New second - add new point
        trafficHistory.push({
            timestamp: now,
            packets: packets,
            bytes: bytes
        });
        
        // Keep only last MAX_HISTORY points
        if (trafficHistory.length > MAX_HISTORY) {
            trafficHistory.shift();
        }
    }
};

// Add data point for no activity (keeps chart flowing)
const addIdleDataPoint = () => {
    const now = Date.now();
    const lastPoint = trafficHistory[trafficHistory.length - 1];
    
    // Only add if last point is more than 1 second old
    if (!lastPoint || (now - lastPoint.timestamp) >= 1000) {
        trafficHistory.push({
            timestamp: now,
            packets: 0,
            bytes: 0
        });
        
        // Keep only last MAX_HISTORY points
        if (trafficHistory.length > MAX_HISTORY) {
            trafficHistory.shift();
        }
    }
};

export const createTrafficChart = () => {
    const ctx = (document.getElementById('trafficChart') as HTMLCanvasElement)?.getContext('2d');
    if (!ctx) return;

    // Initialize history if empty
    if (trafficHistory.length === 0) {
        initializeTrafficHistory();
    }

    if (trafficChartInstance) {
        trafficChartInstance.destroy();
    }
    
    const isDarkMode = document.body.dataset.theme === 'dark';
    const gridColor = isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';
    const textColor = isDarkMode ? '#f8fafc' : '#1e293b';

    // Generate labels (relative time)
    const labels = trafficHistory.map((_, i) => {
        const secondsAgo = MAX_HISTORY - i - 1;
        return `-${secondsAgo}s`;
    });
    
    // Convert packets/sec to data rate (Mbps estimate)
    // Assuming ~1KB per packet average
    const packetsPerSec = trafficHistory.map(d => d.packets);
    const mbpsData = trafficHistory.map(d => (d.bytes * 8) / (1024 * 1024)); // Convert bytes to Mbps

    trafficChartInstance = new (window as any).Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Packets/sec',
                    data: packetsPerSec,
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    fill: true,
                    tension: 0.4,
                    yAxisID: 'y',
                },
                {
                    label: 'Traffic (Mbps)',
                    data: mbpsData,
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    fill: true,
                    tension: 0.4,
                    yAxisID: 'y1',
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            animation: {
                duration: 300,
            },
            scales: {
                x: {
                    grid: { color: gridColor },
                    ticks: { color: textColor }
                },
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    beginAtZero: true,
                    grid: { color: gridColor },
                    ticks: { color: textColor },
                    title: {
                        display: true,
                        text: 'Packets/sec',
                        color: textColor
                    }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    beginAtZero: true,
                    grid: { 
                        drawOnChartArea: false,
                    },
                    ticks: { color: textColor },
                    title: {
                        display: true,
                        text: 'Mbps',
                        color: textColor
                    }
                }
            },
            plugins: {
                legend: {
                    position: 'top',
                    align: 'end',
                    labels: {
                        color: textColor,
                        boxWidth: 12,
                        padding: 20
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context: any) {
                            const value = context.parsed.y.toFixed(context.datasetIndex === 0 ? 0 : 2);
                            const unit = context.datasetIndex === 0 ? ' packets/s' : ' Mbps';
                            return `${context.dataset.label}: ${value}${unit}`;
                        }
                    }
                }
            }
        }
    });

    // Connect to real-time predictions
    connectToRealtimeData();
    
    // Start chart updates
    startTrafficUpdates();
};

// Connect to realtime data stream
const connectToRealtimeData = () => {
    // Disconnect previous subscription if exists
    if (sseUnsubscribe) {
        sseUnsubscribe();
        sseUnsubscribe = null;
    }
    
    const realtimeClient = getRealtimeClient();
    
    // Connect to traffic.stats topic for real-time packet statistics
    console.log('[Chart] Connecting to traffic.stats stream for live packet data');
    realtimeClient.connect('traffic.stats');
    
    // Subscribe to SSE events
    sseUnsubscribe = realtimeClient.onEvent((message: SSEMessage) => {
        console.log('[Chart] SSE event received:', message.type, message);
        
        // Handle traffic statistics messages
        if (message.type === 'message' && message.data) {
            const stats = message.data;
            console.log('[Chart] Message data:', stats);
            
            // Check if this is a traffic stats message
            if ('packets' in stats && 'bytes' in stats && 'packets_per_second' in stats) {
                // Use the aggregated statistics directly
                const dataPoint: TrafficDataPoint = {
                    timestamp: Date.now(),
                    packets: stats.packets_per_second || 0,
                    bytes: stats.bytes_per_second || 0
                };
                
                // Add to history
                trafficHistory.push(dataPoint);
                if (trafficHistory.length > MAX_HISTORY) {
                    trafficHistory.shift();
                }
                
                console.log(`[Chart] Traffic stats added: ${stats.packets_per_second.toFixed(1)} pkt/s, ${stats.mbps.toFixed(2)} Mbps, history length: ${trafficHistory.length}`);
            } else {
                console.log('[Chart] Message is not traffic stats, keys:', Object.keys(stats));
            }
        }
        // Keep backward compatibility with prediction-based stats
        else if (message.type === 'prediction' && message.data) {
            console.log('[Chart] Prediction event:', message.data);
            updateTrafficFromPrediction(message.data);
        }
        // Alert events also indicate traffic
        else if (message.type === 'alert' && message.data) {
            console.log('[Chart] Alert event:', message.data);
            updateTrafficFromPrediction({ packets: 10, bytes: 10000 });
        }
        else {
            console.log('[Chart] Unhandled event type:', message.type);
        }
    });
};

// Start updating the chart with new data
const startTrafficUpdates = () => {
    // Clear any existing interval
    if (chartUpdateInterval) {
        clearInterval(chartUpdateInterval);
    }
    
    // Update chart every second
    chartUpdateInterval = window.setInterval(() => {
        // Add idle point if no recent activity
        addIdleDataPoint();
        
        // Update chart if it exists
        if (trafficChartInstance && trafficHistory.length > 0) {
            // Update labels
            trafficChartInstance.data.labels = trafficHistory.map((_, i) => {
                const secondsAgo = MAX_HISTORY - i - 1;
                return `-${secondsAgo}s`;
            });
            
            // Update data
            const packetsPerSec = trafficHistory.map(d => d.packets);
            const mbpsData = trafficHistory.map(d => (d.bytes * 8) / (1024 * 1024));
            
            trafficChartInstance.data.datasets[0].data = packetsPerSec;
            trafficChartInstance.data.datasets[1].data = mbpsData;
            
            // Refresh chart
            trafficChartInstance.update('none'); // Use 'none' mode for smoother updates
        }
    }, 1000); // Update every 1 second
};

// Stop chart updates (call when leaving dashboard)
export const stopTrafficUpdates = () => {
    if (chartUpdateInterval) {
        clearInterval(chartUpdateInterval);
        chartUpdateInterval = null;
    }
    
    // Unsubscribe from SSE
    if (sseUnsubscribe) {
        sseUnsubscribe();
        sseUnsubscribe = null;
    }
};

// Export for cleanup
export const destroyTrafficChart = () => {
    stopTrafficUpdates();
    if (trafficChartInstance) {
        trafficChartInstance.destroy();
        trafficChartInstance = null;
    }
    // Clear history for fresh start next time
    trafficHistory.length = 0;
};

