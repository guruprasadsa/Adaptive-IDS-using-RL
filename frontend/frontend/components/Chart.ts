import type { Chart } from 'chart.js';

let trafficChartInstance: Chart | null = null;

export const createTrafficChart = () => {
    const ctx = (document.getElementById('trafficChart') as HTMLCanvasElement)?.getContext('2d');
    if (!ctx) return;

    if (trafficChartInstance) {
        trafficChartInstance.destroy();
    }
    
    const isDarkMode = document.body.dataset.theme === 'dark';
    const gridColor = isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';
    const textColor = isDarkMode ? '#f8fafc' : '#1e293b';

    const labels = Array.from({ length: 15 }, (_, i) => `-${14 - i}s`);
    const dataIn = Array.from({ length: 15 }, () => Math.random() * 800 + 100);
    const dataOut = Array.from({ length: 15 }, () => Math.random() * 500 + 50);

    trafficChartInstance = new (window as any).Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Inbound (Mbps)',
                    data: dataIn,
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    fill: true,
                    tension: 0.4,
                },
                {
                    label: 'Outbound (Mbps)',
                    data: dataOut,
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    fill: true,
                    tension: 0.4,
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    grid: { color: gridColor },
                    ticks: { color: textColor }
                },
                y: {
                    beginAtZero: true,
                    grid: { color: gridColor },
                    ticks: { color: textColor }
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
                }
            }
        }
    });
};
