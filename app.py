"""
Q-AgeNet Web Dashboard - Flask Backend
Serves the quantum aging detector frontend and runs simulations via API.
"""
from flask import Flask, jsonify, request, send_from_directory, send_file
from flask_cors import CORS
import json
import os
import sys
import traceback

# Ensure quantum modules are importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__, static_folder='static')
CORS(app)


# --------------- Page Routes ---------------

@app.route('/')
def index():
    return send_file('index.html')


@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)


# --------------- API Routes ---------------

@app.route('/api/results')
def get_results():
    """Load the most recent pre-computed results JSON."""
    results_dir = os.path.dirname(os.path.abspath(__file__))
    json_files = sorted(
        [f for f in os.listdir(results_dir) if f.startswith('qagenet_results_') and f.endswith('.json')],
        reverse=True
    )
    if json_files:
        filepath = os.path.join(results_dir, json_files[0])
        with open(filepath, 'r') as f:
            data = json.load(f)
        return jsonify(data)
    return jsonify({'error': 'No results file found. Run a simulation first.'}), 404


@app.route('/api/results/list')
def list_results():
    """List all available result files."""
    results_dir = os.path.dirname(os.path.abspath(__file__))
    json_files = sorted(
        [f for f in os.listdir(results_dir) if f.startswith('qagenet_results_') and f.endswith('.json')],
        reverse=True
    )
    return jsonify({'files': json_files})


@app.route('/api/run', methods=['POST'])
def run_simulation():
    """Run a new quantum aging simulation."""
    try:
        # Verify qiskit_aer is importable before starting
        try:
            from qiskit_aer import AerSimulator as _test
        except ImportError as e:
            return jsonify({
                'error': f'Qiskit Aer not available: {e}. Run: pip install --upgrade qiskit-aer',
                'fix': 'pip install --upgrade qiskit-aer'
            }), 503

        config = request.get_json() or {}
        num_qubits = min(max(int(config.get('num_qubits', 3)), 2), 8)
        num_executions = min(max(int(config.get('num_executions', 150)), 10), 500)
        shots = min(max(int(config.get('shots', 2048)), 256), 8192)

        print(f"\n[API] Starting simulation: {num_qubits}q / {num_executions} exec / {shots} shots")

        from quantum_aging_detector_final import QAgeNet

        qagenet = QAgeNet(
            num_qubits=num_qubits,
            num_executions=num_executions,
            shots=shots,
            burn_in=20,
            smooth_window=5
        )

        aging_detected = qagenet.run_experiment()
        results = qagenet.analyze_results(aging_detected)

        # Ensure all values are JSON-serializable (convert numpy types)
        import numpy as np
        def convert(obj):
            if isinstance(obj, dict):
                return {k: convert(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [convert(v) for v in obj]
            elif isinstance(obj, (np.integer,)):
                return int(obj)
            elif isinstance(obj, (np.floating,)):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, np.bool_):
                return bool(obj)
            return obj

        results = convert(results)
        print(f"[API] Simulation complete. First aging: #{results.get('metrics', {}).get('first_aging_execution')}")
        return jsonify(results)

    except ImportError as e:
        traceback.print_exc()
        return jsonify({
            'error': f'Quantum libraries not available: {e}',
            'fix': 'pip install qiskit qiskit-aer'
        }), 503
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/api/health')
def health():
    """Health check endpoint."""
    qiskit_available = False
    qiskit_version = None
    aer_version = None
    error_msg = None
    try:
        import qiskit
        qiskit_version = qiskit.__version__
        from qiskit_aer import AerSimulator
        import qiskit_aer
        aer_version = qiskit_aer.__version__
        qiskit_available = True
    except ImportError as e:
        error_msg = str(e)
    except Exception as e:
        error_msg = str(e)
    return jsonify({
        'status': 'ok',
        'qiskit_available': qiskit_available,
        'qiskit_version': qiskit_version,
        'aer_version': aer_version,
        'error': error_msg,
        'mode': 'local'
    })


# --------------- Run ---------------

if __name__ == '__main__':
    print("\n" + "=" * 55)
    print("  ⚛  Q-AgeNet Web Dashboard")
    print("  → http://localhost:5000")
    print("=" * 55 + "\n")
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)
