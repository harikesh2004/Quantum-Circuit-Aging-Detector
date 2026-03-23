# ⚛️ Q-AgeNet — Quantum Circuit Aging Detection System

A professional web dashboard for simulating and analyzing quantum circuit aging using Qiskit,
with ML-powered anomaly detection and interactive visualizations.

![Q-AgeNet Dashboard](https://img.shields.io/badge/Q--AgeNet-v4.0-00d4ff?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.12-3b82f6?style=for-the-badge)
![Qiskit](https://img.shields.io/badge/Qiskit-2.3-7c3aed?style=for-the-badge)

---

## 🚀 Quick Start (Local)

### 1. Activate the virtual environment
```bash
# Windows
qagenet_env\Scripts\activate

# macOS/Linux
source qagenet_env/bin/activate
```

### 2. Install web dependencies
```bash
pip install flask flask-cors
```

### 3. Run the dashboard
```bash
python app.py
```

### 4. Open in browser
Navigate to **http://localhost:5000**

The dashboard will automatically load pre-computed results. Click **"Run Simulation"** to execute
a fresh quantum aging experiment (requires Qiskit + qiskit-aer).
---

## 📊 Features

- **Interactive Charts** — Fidelity decay, CAI evolution, entropy growth, detection timeline
- **Real-time Metrics** — Animated counters for key performance indicators
- **Scatter Analysis** — CAI vs Fidelity correlation with execution-colored points
- **Success Criteria** — Automated pass/fail evaluation with score ring
- **Dark Quantum Theme** — Professional glassmorphism design with animated background
- **Responsive** — Works on desktop, tablet, and mobile
- **Dual Mode** — Local (Flask + Qiskit) or Static (Vercel deployment)

---

## 🏗️ Project Structure

```
QC-2/
├── index.html                         # Main dashboard page
├── app.py                             # Flask backend (local dev)
├── static/
│   ├── css/styles.css                 # Professional dark theme
│   └── js/app.js                      # Frontend logic + Chart.js
├── quantum_aging_detector.py          # Quantum model (v3.2 - ML)
├── quantum_aging_detector_final.py    # Quantum model (v4.0 - PELT)
├── qagenet_results_*.json             # Pre-computed simulation results
├── vercel.json                        # Vercel deployment config
├── .gitignore                         # Git ignore rules
└── README.md                          # This file
```

---

## 🔬 How It Works

1. **GHZ State Preparation** — Creates entangled 3-qubit GHZ state: |000⟩ + |111⟩
2. **Aging Simulation** — Progressive noise injection (depolarizing + thermal relaxation)
3. **Metrics Collection** — Fidelity, Circuit Aging Index (CAI), Shannon Entropy
4. **Change-Point Detection** — PELT algorithm detects aging onset
5. **Dashboard Visualization** — Interactive charts display all results

---

## 📜 License

MIT License — Built for quantum computing research.
