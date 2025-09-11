import { Chart, LineController, LineElement, PointElement, LinearScale, Title, CategoryScale, Filler, Legend, Tooltip } from 'chart.js';

// Register required controllers and components (Chart.js v4 tree-shaking)
Chart.register(LineController, LineElement, PointElement, LinearScale, Title, CategoryScale, Filler, Legend, Tooltip);

let trafficChartInstance: Chart<'line'> | null = null;

export const createTrafficChart = (): void => {
    const canvas = document.getElementById('trafficChart') as HTMLCanvasElement | null;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    if (trafficChartInstance) {
        trafficChartInstance.destroy();
        trafficChartInstance = null;
    }

    const isDarkMode = document.body.dataset.theme === 'dark';
    const gridColor = isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';
    const textColor = isDarkMode ? '#f8fafc' : '#1e293b';

    const labels = Array.from({ length: 15 }, (_, i) => `-${14 - i}s`);
    const dataIn = Array.from({ length: 15 }, () => Math.random() * 800 + 100);
    const dataOut = Array.from({ length: 15 }, () => Math.random() * 500 + 50);

    trafficChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [
                {
                    label: 'Inbound (Mbps)',
                    data: dataIn,
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0,
                    borderWidth: 2,
                },
                {
                    label: 'Outbound (Mbps)',
                    data: dataOut,
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0,
                    borderWidth: 2,
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index' as const,
                intersect: false,
            },
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
                },
                tooltip: {
                    enabled: true
                },
                title: {
                    display: false,
                    text: ''
                }
            }
        }
    });
};
