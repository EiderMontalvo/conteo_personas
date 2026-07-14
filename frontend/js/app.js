//app.js - Lógica principal del Dashboard BI - Conteo de Personas

const WS_URL = "ws://localhost:8000/ws/live";
const API_URL = "http://localhost:8000";
const MAX_CHART_POINTS = 30;

//Estado global por cámara
const cameraState = {};

//DOM 
const statusDot = document.querySelector('.dot');
const statusText = document.querySelector('.status-text');
const countInEl = document.getElementById('count-in');
const countOutEl = document.getElementById('count-out');
const countNetEl = document.getElementById('count-net');
const cameraSelect = document.getElementById('camera-select');
const ctx = document.getElementById('flowChart').getContext('2d');

//Chart.js 
Chart.defaults.color = '#94a3b8';
Chart.defaults.font.family = "'Outfit', sans-serif";

const chartData = {
    labels: [],
    datasets: [
        {
            label: 'Entradas',
            data: [],
            borderColor: '#10b981',
            backgroundColor: 'rgba(16, 185, 129, 0.08)',
            borderWidth: 2,
            tension: 0.4,
            fill: true,
            pointRadius: 3,
        },
        {
            label: 'Salidas',
            data: [],
            borderColor: '#ef4444',
            backgroundColor: 'rgba(239, 68, 68, 0.08)',
            borderWidth: 2,
            tension: 0.4,
            fill: true,
            pointRadius: 3,
        }
    ]
};

const flowChart = new Chart(ctx, {
    type: 'line',
    data: chartData,
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { position: 'top' },
            tooltip: {
                mode: 'index',
                intersect: false,
                backgroundColor: 'rgba(15, 23, 42, 0.95)',
                titleColor: '#f8fafc',
                bodyColor: '#e2e8f0',
                borderColor: 'rgba(255,255,255,0.1)',
                borderWidth: 1,
            }
        },
        scales: {
            y: {
                beginAtZero: true,
                ticks: { stepSize: 1, precision: 0 },
                grid: { color: 'rgba(255,255,255,0.05)' }
            },
            x: {
                grid: { display: false },
                ticks: { maxTicksLimit: 8, maxRotation: 45, minRotation: 45 }
            }
        },
        animation: { duration: 300 }
    }
});

//Cámaras 
let activeCameraId = null;

async function loadCameras() {
    try {
        const res = await fetch(`${API_URL}/api/cameras`);
        const cameras = await res.json();

        cameras.forEach(cam => {
            cameraState[cam.id] = { name: cam.name, in: 0, out: 0, history: [] };
            const opt = document.createElement('option');
            opt.value = cam.id;
            opt.textContent = `[${cam.id}] ${cam.name}`;
            cameraSelect.appendChild(opt);
        });

        if (cameras.length > 0) {
            activeCameraId = cameras[0].id;
            cameraSelect.value = activeCameraId;
            updateSubtitle();
        }
    } catch (e) {
        console.error('No se pudo cargar la lista de cámaras:', e);
    }
}

cameraSelect.addEventListener('change', () => {
    activeCameraId = parseInt(cameraSelect.value);
    refreshChartForCamera(activeCameraId);
    updateSubtitle();
});

function updateSubtitle() {
    if (activeCameraId !== null && cameraState[activeCameraId]) {
        document.getElementById('camera-subtitle').textContent =
            `Cámara activa: ${cameraState[activeCameraId].name} (192.168.1.10${activeCameraId})`;
    }
}

//WebSocket 
let ws;

function setStatus(online) {
    const color = online ? 'var(--in-color)' : 'var(--out-color)';
    statusDot.style.backgroundColor = color;
    statusText.style.color = color;
    statusText.textContent = online ? 'En línea (WebSocket)' : 'Desconectado. Reintentando...';
}

function connectWebSocket() {
    ws = new WebSocket(WS_URL);

    ws.onopen = () => { console.log('WS conectado'); setStatus(true); };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleIncomingData(data);
    };

    ws.onclose = () => {
        setStatus(false);
        setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = () => ws.close();
}

//Lógica de datos
function handleIncomingData(data) {
    const { camera_id, in_count, out_count, timestamp } = data;
    const camId = parseInt(camera_id);

    if (!cameraState[camId]) return;

    //Actualizar estado global de la cámara
    cameraState[camId].in = in_count;
    cameraState[camId].out = out_count;
    cameraState[camId].history.push({ timestamp, in_count, out_count });

    //Si es la cámara activa, actualizar UI
    if (camId === activeCameraId) {
        updateKPIs(in_count, out_count);
        appendChartPoint(timestamp, in_count, out_count);
    }
}

function updateKPIs(inC, outC) {
    countInEl.textContent = inC;
    countOutEl.textContent = outC;
    countNetEl.textContent = inC - outC;
}

function appendChartPoint(timestamp, inC, outC) {
    const label = new Date(timestamp).toLocaleTimeString([], {
        hour: '2-digit', minute: '2-digit', second: '2-digit'
    });
    chartData.labels.push(label);
    chartData.datasets[0].data.push(inC);
    chartData.datasets[1].data.push(outC);

    if (chartData.labels.length > MAX_CHART_POINTS) {
        chartData.labels.shift();
        chartData.datasets[0].data.shift();
        chartData.datasets[1].data.shift();
    }
    flowChart.update('none');
}

function refreshChartForCamera(camId) {
    //Limpiar gráfico y repintar con el historial en memoria de la cámara
    chartData.labels = [];
    chartData.datasets[0].data = [];
    chartData.datasets[1].data = [];

    const history = cameraState[camId]?.history || [];
    history.slice(-MAX_CHART_POINTS).forEach(({ timestamp, in_count, out_count }) => {
        appendChartPoint(timestamp, in_count, out_count);
    });

    if (cameraState[camId]) {
        updateKPIs(cameraState[camId].in, cameraState[camId].out);
    }
}

(async () => {
    await loadCameras();
    connectWebSocket();
})();
