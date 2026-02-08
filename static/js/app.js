/**
 * Q-AgeNet Dashboard — Frontend Application
 * Quantum Circuit Aging Detection System
 */

// ─── Chart.js Global Config ────────────────────────
Chart.defaults.color = '#8b949e';
Chart.defaults.borderColor = 'rgba(48, 54, 61, 0.4)';
Chart.defaults.font.family = "'Inter', sans-serif";
Chart.defaults.font.size = 11;
Chart.defaults.animation.duration = 1200;
Chart.defaults.responsive = true;
Chart.defaults.maintainAspectRatio = false;

// ─── Main Dashboard Class ──────────────────────────
class QAgeNetDashboard {
    constructor() {
        this.charts = {};
        this.results = null;
        this.isLocal = false;
        this.init();
    }

    // ── Initialization ──
    async init() {
        this.bindEvents();
        await this.checkBackend();
        await this.loadResults();
    }

    bindEvents() {
        document.getElementById('runSimBtn').addEventListener('click', () => this.toggleConfig());
        document.getElementById('loadResultsBtn').addEventListener('click', () => this.loadResults());
        document.getElementById('closeConfigBtn')?.addEventListener('click', () => this.hideConfig());
        document.getElementById('startSimBtn')?.addEventListener('click', () => this.runSimulation());

        // Chart filter buttons
        document.querySelectorAll('.chart-ctrl-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.filterCharts(e.target.dataset.view, e.target));
        });
    }

    // ── Backend Check ──
    async checkBackend() {
        const statusDot = document.querySelector('.status-dot');
        const statusText = document.querySelector('.status-text');
        try {
            const res = await fetch('/api/health', { signal: AbortSignal.timeout(3000) });
            if (res.ok) {
                const data = await res.json();
                this.isLocal = true;
                this.qiskitReady = data.qiskit_available === true;
                statusDot.classList.remove('offline');
                statusDot.classList.add('online');
                if (this.qiskitReady) {
                    statusText.textContent = `Local — Qiskit ${data.qiskit_version || ''} + Aer ${data.aer_version || ''}`;
                } else {
                    statusText.textContent = 'Local (Qiskit Not Available)';
                    statusDot.classList.remove('online');
                    statusDot.classList.add('offline');
                }
                return;
            }
        } catch (e) { /* not available */ }
        this.isLocal = false;
        this.qiskitReady = false;
        statusDot.classList.remove('online');
        statusDot.classList.add('offline');
        statusText.textContent = 'Static Mode (No Server)';
    }

    // ── Load Results ──
    async loadResults() {
        this.setStatus('Loading results...');
        const paths = [
            '/api/results',
            '/qagenet_results_20260123_102857.json',
            'qagenet_results_20260123_102857.json'
        ];

        for (const path of paths) {
            try {
                const res = await fetch(path, { signal: AbortSignal.timeout(5000) });
                if (res.ok) {
                    const data = await res.json();
                    if (data && !data.error && data.time_series) {
                        this.results = data;
                        this.renderDashboard();
                        this.showToast('Results loaded successfully', 'success');
                        this.setStatus('Dashboard ready — Displaying analysis results');
                        return;
                    }
                }
            } catch (e) { continue; }
        }

        this.setStatus('No results found. Run a simulation or check your data files.');
        this.showToast('Could not load results. Run a simulation to generate data.', 'warning');
    }

    // ── Run Simulation ──
    async runSimulation() {
        // Re-check backend before running
        await this.checkBackend();

        if (!this.isLocal) {
            this.showToast('Flask server is not running. Start it with: python app.py', 'error');
            return;
        }

        if (!this.qiskitReady) {
            this.showToast('Qiskit is not available. Run: pip install --upgrade qiskit qiskit-aer', 'warning');
            return;
        }

        const config = {
            num_qubits: parseInt(document.getElementById('cfgQubits').value) || 3,
            num_executions: parseInt(document.getElementById('cfgExecutions').value) || 150,
            shots: parseInt(document.getElementById('cfgShots').value) || 2048
        };

        this.showLoading(true);
        this.simulateProgress();
        this.setStatus(`Running simulation: ${config.num_qubits}q / ${config.num_executions} executions...`);

        try {
            const res = await fetch('/api/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });

            const data = await res.json();

            if (!res.ok) {
                const errMsg = data.error || 'Simulation failed';
                const fix = data.fix ? `\nFix: ${data.fix}` : '';
                throw new Error(errMsg + fix);
            }

            this.results = data;
            this.showLoading(false);
            this.hideConfig();
            this.renderDashboard();
            this.showToast('Simulation completed successfully!', 'success');
            this.setStatus('New simulation results displayed');
        } catch (err) {
            this.showLoading(false);
            if (err.name === 'TypeError' && err.message.includes('fetch')) {
                this.showToast('Server connection lost. Is Flask still running?', 'error');
                this.setStatus('Connection lost — restart server with: python app.py');
            } else {
                this.showToast(`Error: ${err.message}`, 'error');
                this.setStatus('Simulation failed — see error details');
            }
        }
    }

    // ── Render Dashboard ──
    renderDashboard() {
        if (!this.results) return;
        this.renderStatusBar();
        this.renderMetrics();
        this.renderAllCharts();
        this.renderSummary();
    }

    renderStatusBar() {
        const cfg = this.results.configuration || {};
        const ts = this.results.timestamp || '';

        document.getElementById('tagQubits').innerHTML =
            `<i class="fas fa-atom"></i> ${cfg.num_qubits || '--'} Qubits`;
        document.getElementById('tagExecutions').innerHTML =
            `<i class="fas fa-redo"></i> ${cfg.num_executions || '--'} Executions`;
        document.getElementById('tagShots').innerHTML =
            `<i class="fas fa-bullseye"></i> ${cfg.shots || '--'} Shots`;

        let formattedTime = ts;
        if (ts && ts.length >= 8) {
            formattedTime = `${ts.slice(0,4)}-${ts.slice(4,6)}-${ts.slice(6,8)}`;
            if (ts.length >= 14) formattedTime += ` ${ts.slice(9,11)}:${ts.slice(11,13)}`;
        }
        document.getElementById('tagTimestamp').innerHTML =
            `<i class="fas fa-clock"></i> ${formattedTime}`;
    }

    renderMetrics() {
        const m = this.results.metrics;
        this.animateValue('metricBaseline', m.baseline_fidelity, 4);
        this.animateValue('metricFinal', m.final_fidelity, 4);
        this.animateValue('metricDecay', m.fidelity_decay_percent, 1, '%');
        this.animateValue('metricAccuracy', m.detection_accuracy, 1, '%');
        this.animateValue('metricFP', m.false_positive_rate, 1, '%');
        document.getElementById('metricOnset').textContent = `#${m.first_aging_execution ?? '--'}`;
    }

    animateValue(elementId, target, decimals = 2, suffix = '') {
        const el = document.getElementById(elementId);
        if (!el || target == null) return;

        const duration = 1500;
        const start = performance.now();
        const startVal = 0;

        const step = (now) => {
            const elapsed = now - start;
            const progress = Math.min(elapsed / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);        // easeOutCubic
            const current = startVal + (target - startVal) * eased;
            el.textContent = current.toFixed(decimals) + suffix;
            if (progress < 1) requestAnimationFrame(step);
        };
        requestAnimationFrame(step);
    }

    // ── Charts ──
    renderAllCharts() {
        // Destroy existing charts
        Object.values(this.charts).forEach(c => c.destroy());
        this.charts = {};

        const ts = this.results.time_series;
        const m = this.results.metrics;
        const numExec = ts.fidelities.length;
        const labels = Array.from({ length: numExec }, (_, i) => i);

        this.renderFidelityChart(labels, ts, m);
        this.renderCAIChart(labels, ts);
        this.renderEntropyChart(labels, ts);
        this.renderTimelineChart(labels, ts, m);
        this.renderCorrelationChart(ts);
        this.renderDistributionChart(ts);
    }

    createGradient(ctx, color1, color2, alpha1 = 0.4, alpha2 = 0) {
        const grad = ctx.createLinearGradient(0, 0, 0, ctx.canvas.height);
        grad.addColorStop(0, this.hexToRgba(color1, alpha1));
        grad.addColorStop(1, this.hexToRgba(color2, alpha2));
        return grad;
    }

    hexToRgba(hex, alpha) {
        const r = parseInt(hex.slice(1, 3), 16);
        const g = parseInt(hex.slice(3, 5), 16);
        const b = parseInt(hex.slice(5, 7), 16);
        return `rgba(${r},${g},${b},${alpha})`;
    }

    renderFidelityChart(labels, ts, m) {
        const ctx = document.getElementById('fidelityChart').getContext('2d');
        const agingStart = m.first_aging_execution || 72;

        // Split data into normal and aged segments
        const normalData = ts.fidelities.map((v, i) => i < agingStart ? v : null);
        const agedData = ts.fidelities.map((v, i) => i >= agingStart - 1 ? v : null);

        this.charts.fidelity = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [
                    {
                        label: 'Fidelity (Normal)',
                        data: normalData,
                        borderColor: '#10b981',
                        backgroundColor: this.createGradient(ctx, '#10b981', '#10b981', 0.15, 0),
                        borderWidth: 2,
                        fill: true,
                        pointRadius: 0,
                        pointHoverRadius: 4,
                        tension: 0.3,
                        spanGaps: false
                    },
                    {
                        label: 'Fidelity (Aged)',
                        data: agedData,
                        borderColor: '#ef4444',
                        backgroundColor: this.createGradient(ctx, '#ef4444', '#ef4444', 0.15, 0),
                        borderWidth: 2,
                        fill: true,
                        pointRadius: 0,
                        pointHoverRadius: 4,
                        tension: 0.3,
                        spanGaps: false
                    }
                ]
            },
            options: {
                plugins: {
                    legend: { position: 'top', labels: { boxWidth: 12, padding: 16 } },
                    tooltip: {
                        backgroundColor: 'rgba(13,17,23,0.95)',
                        borderColor: 'rgba(48,54,61,0.6)',
                        borderWidth: 1,
                        callbacks: {
                            title: (items) => `Execution #${items[0].label}`,
                            label: (item) => `${item.dataset.label}: ${item.raw?.toFixed(4) ?? '--'}`
                        }
                    },
                    annotation: undefined
                },
                scales: {
                    x: { title: { display: true, text: 'Execution Number' }, grid: { display: false } },
                    y: { title: { display: true, text: 'Fidelity' }, min: 0, max: 1.05 }
                }
            }
        });
    }

    renderCAIChart(labels, ts) {
        const ctx = document.getElementById('caiChart').getContext('2d');
        const caiData = ts.cai_smoothed || ts.cai_values || [];

        this.charts.cai = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [{
                    label: 'CAI (Smoothed)',
                    data: caiData,
                    borderColor: '#7c3aed',
                    backgroundColor: this.createGradient(ctx, '#7c3aed', '#7c3aed', 0.2, 0),
                    borderWidth: 2.5,
                    fill: true,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    tension: 0.4
                }]
            },
            options: {
                plugins: {
                    legend: { position: 'top', labels: { boxWidth: 12, padding: 16 } },
                    tooltip: {
                        backgroundColor: 'rgba(13,17,23,0.95)',
                        borderColor: 'rgba(48,54,61,0.6)',
                        borderWidth: 1,
                        callbacks: {
                            title: (items) => `Execution #${items[0].label}`,
                            label: (item) => `CAI: ${item.raw?.toFixed(2) ?? '--'}`
                        }
                    }
                },
                scales: {
                    x: { title: { display: true, text: 'Execution Number' }, grid: { display: false } },
                    y: { title: { display: true, text: 'Circuit Aging Index' } }
                }
            }
        });
    }

    renderEntropyChart(labels, ts) {
        const ctx = document.getElementById('entropyChart').getContext('2d');

        this.charts.entropy = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [{
                    label: 'Shannon Entropy',
                    data: ts.entropy_values,
                    borderColor: '#f59e0b',
                    backgroundColor: this.createGradient(ctx, '#f59e0b', '#f59e0b', 0.15, 0),
                    borderWidth: 2,
                    fill: true,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    tension: 0.3
                }]
            },
            options: {
                plugins: {
                    legend: { position: 'top', labels: { boxWidth: 12, padding: 16 } },
                    tooltip: {
                        backgroundColor: 'rgba(13,17,23,0.95)',
                        borderColor: 'rgba(48,54,61,0.6)',
                        borderWidth: 1,
                        callbacks: {
                            title: (items) => `Execution #${items[0].label}`,
                            label: (item) => `Entropy: ${item.raw?.toFixed(4) ?? '--'}`
                        }
                    }
                },
                scales: {
                    x: { title: { display: true, text: 'Execution Number' }, grid: { display: false } },
                    y: { title: { display: true, text: 'Shannon Entropy (bits)' } }
                }
            }
        });
    }

    renderTimelineChart(labels, ts, m) {
        const ctx = document.getElementById('timelineChart').getContext('2d');
        const agingStart = m.first_aging_execution || 72;

        // Build binary detection array from fidelity threshold
        const detection = ts.fidelities.map((f, i) => {
            if (i >= agingStart) return 1;
            return 0;
        });

        const colors = detection.map(d => d ? 'rgba(239, 68, 68, 0.7)' : 'rgba(16, 185, 129, 0.4)');

        this.charts.timeline = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label: 'Aging Status',
                    data: detection,
                    backgroundColor: colors,
                    borderWidth: 0,
                    barPercentage: 1.0,
                    categoryPercentage: 1.0
                }]
            },
            options: {
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            title: (items) => `Execution #${items[0].label}`,
                            label: (item) => item.raw === 1 ? '⚠ Aging Detected' : '✓ Normal'
                        }
                    }
                },
                scales: {
                    x: { title: { display: true, text: 'Execution Number' }, grid: { display: false } },
                    y: {
                        title: { display: true, text: 'Status' },
                        min: -0.1, max: 1.2,
                        ticks: {
                            callback: (v) => v === 0 ? 'Normal' : v === 1 ? 'Aged' : '',
                            stepSize: 1
                        }
                    }
                }
            }
        });
    }

    renderCorrelationChart(ts) {
        const ctx = document.getElementById('correlationChart').getContext('2d');
        const caiData = ts.cai_smoothed || ts.cai_values || [];
        const numExec = ts.fidelities.length;

        const data = ts.fidelities.map((f, i) => ({
            x: caiData[i] ?? 0,
            y: f
        }));

        // Color by execution number (early=cyan, late=red)
        const pointColors = data.map((_, i) => {
            const ratio = i / numExec;
            if (ratio < 0.4) return 'rgba(0, 212, 255, 0.7)';
            if (ratio < 0.7) return 'rgba(245, 158, 11, 0.7)';
            return 'rgba(239, 68, 68, 0.7)';
        });

        this.charts.correlation = new Chart(ctx, {
            type: 'scatter',
            data: {
                datasets: [{
                    label: 'CAI vs Fidelity',
                    data: data,
                    backgroundColor: pointColors,
                    borderColor: pointColors.map(c => c.replace('0.7', '1')),
                    borderWidth: 1,
                    pointRadius: 3.5,
                    pointHoverRadius: 6
                }]
            },
            options: {
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (item) => `CAI: ${item.raw.x.toFixed(2)} | Fidelity: ${item.raw.y.toFixed(4)}`
                        }
                    }
                },
                scales: {
                    x: { title: { display: true, text: 'Circuit Aging Index (CAI)' } },
                    y: { title: { display: true, text: 'Fidelity' }, min: 0, max: 1.05 }
                }
            }
        });
    }

    renderDistributionChart(ts) {
        const ctx = document.getElementById('distributionChart').getContext('2d');
        const fidelities = ts.fidelities;

        // Build histogram bins
        const binCount = 25;
        const min = Math.min(...fidelities);
        const max = Math.max(...fidelities);
        const binWidth = (max - min) / binCount;
        const bins = new Array(binCount).fill(0);
        const binLabels = [];

        for (let i = 0; i < binCount; i++) {
            const lo = min + i * binWidth;
            binLabels.push(lo.toFixed(3));
        }

        fidelities.forEach(f => {
            let idx = Math.floor((f - min) / binWidth);
            if (idx >= binCount) idx = binCount - 1;
            if (idx < 0) idx = 0;
            bins[idx]++;
        });

        // Color bins: high fidelity = green, low = red
        const binColors = binLabels.map(label => {
            const val = parseFloat(label);
            if (val >= 0.9) return 'rgba(16, 185, 129, 0.6)';
            if (val >= 0.7) return 'rgba(245, 158, 11, 0.6)';
            if (val >= 0.4) return 'rgba(239, 68, 68, 0.6)';
            return 'rgba(124, 58, 237, 0.6)';
        });

        this.charts.distribution = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: binLabels,
                datasets: [{
                    label: 'Count',
                    data: bins,
                    backgroundColor: binColors,
                    borderColor: binColors.map(c => c.replace('0.6', '0.9')),
                    borderWidth: 1,
                    borderRadius: 3
                }]
            },
            options: {
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            title: (items) => `Fidelity ≈ ${items[0].label}`,
                            label: (item) => `Count: ${item.raw}`
                        }
                    }
                },
                scales: {
                    x: {
                        title: { display: true, text: 'Fidelity' },
                        grid: { display: false },
                        ticks: { maxTicksLimit: 10 }
                    },
                    y: { title: { display: true, text: 'Frequency' } }
                }
            }
        });
    }

    // ── Summary ──
    renderSummary() {
        const m = this.results.metrics;
        const ts = this.results.time_series;
        const cai = ts.cai_smoothed || ts.cai_values || [];

        // Calculate additional metrics
        const avgCAI = cai.length > 0 ? cai.reduce((a, b) => a + b, 0) / cai.length : 0;
        const maxCAI = cai.length > 0 ? Math.max(...cai) : 0;
        const entropyStart = ts.entropy_values?.[0] ?? 0;
        const entropyEnd = ts.entropy_values?.[ts.entropy_values.length - 1] ?? 0;
        const preservation = m.baseline_fidelity > 0
            ? (m.final_fidelity / m.baseline_fidelity * 100) : 0;

        // Total aged executions
        const agingStart = m.first_aging_execution || 72;
        const totalAged = ts.fidelities.length - agingStart;

        // Criteria
        const criteria = {
            baseline: m.baseline_fidelity >= 0.85,
            decay: m.fidelity_decay_percent > 8,
            accuracy: m.detection_accuracy >= 70,
            fp: m.false_positive_rate < 30
        };
        const passCount = Object.values(criteria).filter(Boolean).length;
        const score = (passCount / 4) * 100;

        // Verdict
        const verdictIcon = document.getElementById('verdictIcon');
        const verdictDiv = document.querySelector('.verdict-icon');
        const verdictTitle = document.getElementById('verdictTitle');
        const verdictText = document.getElementById('verdictText');

        if (score >= 75) {
            verdictDiv.className = 'verdict-icon success';
            verdictIcon.className = 'fas fa-circle-check';
            verdictTitle.textContent = 'Research Goals Achieved';
            verdictText.textContent = 'Quantum circuit aging successfully modeled and detected with high accuracy.';
        } else if (score >= 50) {
            verdictDiv.className = 'verdict-icon warning';
            verdictIcon.className = 'fas fa-triangle-exclamation';
            verdictTitle.textContent = 'Partial Success';
            verdictText.textContent = 'Some metrics need improvement. Review the criteria below.';
        } else {
            verdictDiv.className = 'verdict-icon danger';
            verdictIcon.className = 'fas fa-circle-xmark';
            verdictTitle.textContent = 'Needs Improvement';
            verdictText.textContent = 'Significant issues detected. Parameter adjustments recommended.';
        }

        // Score ring animation
        const scoreCircle = document.getElementById('scoreCircle');
        const circumference = 2 * Math.PI * 52;  // r=52
        const offset = circumference - (score / 100) * circumference;
        setTimeout(() => {
            scoreCircle.style.strokeDashoffset = offset;
            scoreCircle.style.transition = 'stroke-dashoffset 1.5s ease-out';
        }, 300);
        document.getElementById('scoreValue').textContent = `${Math.round(score)}%`;

        // Criteria items
        this.setCriteria('critBaseline', criteria.baseline, m.baseline_fidelity?.toFixed(4));
        this.setCriteria('critDecay', criteria.decay, m.fidelity_decay_percent?.toFixed(1) + '%');
        this.setCriteria('critAccuracy', criteria.accuracy, m.detection_accuracy?.toFixed(1) + '%');
        this.setCriteria('critFP', criteria.fp, m.false_positive_rate?.toFixed(1) + '%');

        // Detail rows
        document.getElementById('detailEntropy').textContent =
            `${entropyStart.toFixed(3)} → ${entropyEnd.toFixed(3)}`;
        document.getElementById('detailCAI').textContent = avgCAI.toFixed(2);
        document.getElementById('detailCAIMax').textContent = maxCAI.toFixed(2);
        document.getElementById('detailAged').textContent =
            `${totalAged} / ${ts.fidelities.length}`;
        document.getElementById('detailPreservation').textContent =
            `${preservation.toFixed(1)}%`;
    }

    setCriteria(id, pass, value) {
        const el = document.getElementById(id);
        if (!el) return;
        el.textContent = value;

        const item = el.closest('.criteria-item');
        if (item) {
            item.classList.remove('pending', 'pass', 'fail');
            item.classList.add(pass ? 'pass' : 'fail');
            const icon = item.querySelector('i');
            if (icon) icon.className = pass ? 'fas fa-circle-check' : 'fas fa-circle-xmark';
        }
    }

    // ── Chart Filtering ──
    filterCharts(view, btn) {
        document.querySelectorAll('.chart-ctrl-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        document.querySelectorAll('.chart-card').forEach(card => {
            if (view === 'all') {
                card.style.display = '';
            } else {
                card.style.display = card.dataset.chart === view ? '' : 'none';
            }
        });
    }

    // ── Config Panel ──
    toggleConfig() {
        const panel = document.getElementById('configPanel');
        panel.style.display = panel.style.display === 'none' ? '' : 'none';
        if (panel.style.display !== 'none') {
            panel.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }

    hideConfig() {
        document.getElementById('configPanel').style.display = 'none';
    }

    // ── Loading ──
    showLoading(show) {
        const overlay = document.getElementById('loadingOverlay');
        if (show) {
            overlay.classList.add('active');
        } else {
            overlay.classList.remove('active');
            document.getElementById('progressFill').style.width = '0%';
        }
    }

    simulateProgress() {
        const fill = document.getElementById('progressFill');
        const statusEl = document.getElementById('loadingStatus');
        const steps = [
            { pct: 10, msg: 'Initializing quantum circuits...' },
            { pct: 25, msg: 'Building noise model...' },
            { pct: 40, msg: 'Running aging simulation...' },
            { pct: 60, msg: 'Processing execution results...' },
            { pct: 75, msg: 'Applying change-point detection...' },
            { pct: 88, msg: 'Computing final metrics...' },
            { pct: 95, msg: 'Generating analysis report...' }
        ];

        let i = 0;
        const interval = setInterval(() => {
            if (i >= steps.length) { clearInterval(interval); return; }
            fill.style.width = steps[i].pct + '%';
            statusEl.textContent = steps[i].msg;
            i++;
        }, 3500);
    }

    // ── Utilities ──
    setStatus(msg) {
        document.getElementById('statusMessage').textContent = msg;
    }

    showToast(message, type = 'info') {
        const container = document.getElementById('toastContainer');
        const icons = {
            success: 'fa-circle-check',
            error: 'fa-circle-xmark',
            warning: 'fa-triangle-exclamation',
            info: 'fa-circle-info'
        };

        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `<i class="fas ${icons[type]}"></i><span>${message}</span>`;
        container.appendChild(toast);

        setTimeout(() => {
            toast.classList.add('removing');
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }
}

// ─── Boot ──────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new QAgeNetDashboard();
});
