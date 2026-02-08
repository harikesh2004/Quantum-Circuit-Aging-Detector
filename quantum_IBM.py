"""
Q-AgeNet v5.0: IBM Quantum Hardware Aging Detector
PRODUCTION-READY VERSION

Tested with:
- qiskit==1.0.2
- qiskit-ibm-runtime==0.21.0
- qiskit-aer==0.13.3 (optional, for local testing)

Author: Quantum Aging Research Team
"""

import numpy as np
import matplotlib.pyplot as plt
from qiskit import QuantumCircuit, transpile
from datetime import datetime
import json
import warnings
import time
from typing import Dict, List, Tuple, Optional

warnings.filterwarnings('ignore')

# Try importing IBM Runtime (REQUIRED)
try:
    from qiskit_ibm_runtime import QiskitRuntimeService, Session, SamplerV2 as Sampler
    IBM_RUNTIME_AVAILABLE = True
except ImportError:
    print("❌ ERROR: qiskit-ibm-runtime not found!")
    print("   Install: pip install qiskit-ibm-runtime==0.21.0")
    IBM_RUNTIME_AVAILABLE = False

# Try importing Aer simulator (OPTIONAL - for local testing only)
try:
    from qiskit_aer import AerSimulator
    AER_AVAILABLE = True
except ImportError:
    AER_AVAILABLE = False

# Try importing ruptures (OPTIONAL - for change-point detection)
try:
    import ruptures as rpt
    RUPTURES_AVAILABLE = True
except ImportError:
    print("⚠️  ruptures not available - using threshold-based detection only")
    RUPTURES_AVAILABLE = False


class IBMHardwareMonitor:
    """
    Interface for IBM Quantum hardware execution.
    Handles backend selection, job submission, and session management.
    """
    
    def __init__(self, backend_name: Optional[str] = None, use_simulator: bool = False):
        """
        Initialize IBM Quantum backend.
        
        Args:
            backend_name: Specific IBM backend (e.g., 'ibm_brisbane', 'ibm_kyoto')
                         If None, auto-selects least busy backend
            use_simulator: Use local Aer simulator (requires qiskit-aer)
        """
        self.use_simulator = use_simulator
        self.service = None
        self.backend = None
        self.session = None
        
        if use_simulator:
            # Local simulator mode
            if not AER_AVAILABLE:
                raise ImportError(
                    "qiskit-aer required for simulator mode.\n"
                    "Install: pip install qiskit-aer==0.13.3"
                )
            self.backend = AerSimulator()
            print("✓ Using local Aer simulator")
            
        else:
            # Real IBM hardware mode
            if not IBM_RUNTIME_AVAILABLE:
                raise ImportError(
                    "qiskit-ibm-runtime required for IBM hardware.\n"
                    "Install: pip install qiskit-ibm-runtime==0.21.0"
                )
            
            try:
                # Load saved credentials
                self.service = QiskitRuntimeService(channel='ibm_quantum')
                
                # Select backend
                if backend_name:
                    self.backend = self.service.backend(backend_name)
                    print(f"✓ Selected backend: {backend_name}")
                else:
                    # Auto-select least busy backend
                    print("🔍 Finding least busy backend...")
                    self.backend = self.service.least_busy(
                        min_num_qubits=3,
                        operational=True,
                        simulator=False
                    )
                    print(f"✓ Auto-selected: {self.backend.name}")
                
                # Display backend info
                status = self.backend.status()
                print(f"  Qubits: {self.backend.num_qubits}")
                print(f"  Pending jobs: {status.pending_jobs}")
                print(f"  Operational: {status.operational}")
                
            except Exception as e:
                print(f"❌ IBM connection failed: {e}")
                print("\n💡 TROUBLESHOOTING:")
                print("   1. Save credentials first:")
                print("      from qiskit_ibm_runtime import QiskitRuntimeService")
                print("      QiskitRuntimeService.save_account(channel='ibm_quantum', token='YOUR_TOKEN')")
                print("   2. Get token from: https://quantum.ibm.com/account")
                raise
    
    def execute_circuit(self, circuit: QuantumCircuit, shots: int = 2048) -> Dict:
        """
        Execute circuit on IBM hardware or simulator.
        
        Args:
            circuit: Quantum circuit to execute
            shots: Number of measurement shots
            
        Returns:
            Dictionary of measurement counts
        """
        if self.use_simulator:
            # Local simulation - simple execution
            result = self.backend.run(circuit, shots=shots).result()
            return result.get_counts()
        
        else:
            # IBM hardware execution with runtime primitives
            try:
                # Transpile for target hardware
                transpiled = transpile(
                    circuit, 
                    backend=self.backend, 
                    optimization_level=3
                )
                
                # Create or reuse session
                if self.session is None:
                    self.session = Session(backend=self.backend)
                
                # Execute with SamplerV2
                sampler = Sampler(session=self.session)
                job = sampler.run([transpiled], shots=shots)
                
                # Wait for result
                result = job.result()
                
                # Extract counts from PrimitiveResult
                pub_result = result[0]
                counts = pub_result.data.meas.get_counts()
                
                return counts
                
            except Exception as e:
                print(f"⚠️  Execution failed: {e}")
                raise
    
    def close_session(self):
        """Close IBM session to release resources."""
        if self.session:
            self.session.close()
            print("✓ IBM session closed")


class QAgeNetHardware:
    """
    Quantum Circuit Aging Detection System for IBM Hardware.
    
    Monitors circuit performance degradation through repeated executions.
    """
    
    def __init__(self, 
                 backend_name: Optional[str] = None,
                 use_simulator: bool = False,
                 num_qubits: int = 3,
                 num_executions: int = 30,
                 shots: int = 1024,
                 burn_in: int = 5,
                 smooth_window: int = 3,
                 execution_delay: float = 0.5):
        """
        Initialize aging detection system.
        
        Args:
            backend_name: IBM backend name (None = auto-select)
            use_simulator: Use local simulator (True) or real hardware (False)
            num_qubits: Number of qubits (3-5 recommended)
            num_executions: Number of repeated executions (20-50 for hardware)
            shots: Measurements per execution (1024-4096)
            burn_in: Initial executions to ignore
            smooth_window: CAI smoothing window
            execution_delay: Delay between executions (seconds)
        """
        self.num_qubits = num_qubits
        self.num_executions = num_executions
        self.shots = shots
        self.burn_in = burn_in
        self.smooth_window = smooth_window
        self.execution_delay = execution_delay
        
        # Initialize hardware
        self.hardware = IBMHardwareMonitor(backend_name, use_simulator)
        
        # Storage
        self.fidelities = []
        self.cai_values = []
        self.entropy_values = []
        self.execution_times = []
        self.cai_smoothed = []
        
        # Metadata
        self.backend_name = self.hardware.backend.name if self.hardware.backend else "Unknown"
        self.start_time = None
    
    def create_circuit(self) -> QuantumCircuit:
        """Create GHZ circuit for aging monitoring."""
        qc = QuantumCircuit(self.num_qubits, self.num_qubits)
        
        # GHZ state: |000...0⟩ + |111...1⟩
        qc.h(0)
        for i in range(self.num_qubits - 1):
            qc.cx(i, i + 1)
        
        qc.measure(range(self.num_qubits), range(self.num_qubits))
        return qc
    
    def calculate_fidelity(self, counts: Dict, expected_states: List[str]) -> float:
        """Calculate fidelity as probability of expected states."""
        total_prob = sum(counts.get(state, 0) for state in expected_states)
        return total_prob / self.shots
    
    def calculate_entropy(self, counts: Dict) -> float:
        """Calculate Shannon entropy."""
        probabilities = np.array(list(counts.values())) / self.shots
        probabilities = probabilities[probabilities > 0]
        return -np.sum(probabilities * np.log2(probabilities))
    
    def calculate_cai(self, current_fidelity: float, baseline_fidelity: float, 
                     execution_num: int, entropy: float) -> float:
        """Calculate Circuit Aging Index."""
        if baseline_fidelity == 0:
            return 0
        
        # Weighted components
        fidelity_decay = max(0, (1 - current_fidelity / baseline_fidelity)) * 100
        temporal_factor = (execution_num / self.num_executions) * 50
        entropy_factor = min(30, entropy * 10)
        fidelity_trend = abs(current_fidelity - baseline_fidelity) * 100
        
        cai = (0.4 * fidelity_decay + 
               0.25 * temporal_factor + 
               0.2 * entropy_factor + 
               0.15 * fidelity_trend)
        
        return cai
    
    def smooth_cai(self, cai_series: List[float]) -> np.ndarray:
        """Apply causal moving average smoothing."""
        cai_array = np.array(cai_series)
        smoothed = np.zeros_like(cai_array)
        
        for i in range(len(cai_array)):
            start_idx = max(0, i - self.smooth_window + 1)
            smoothed[i] = np.mean(cai_array[start_idx:i+1])
        
        return smoothed
    
    def detect_aging(self, cai_smoothed: np.ndarray) -> np.ndarray:
        """
        Detect aging using multiple methods.
        Priority: PELT > Threshold > Derivative
        """
        aging_detected = np.zeros(self.num_executions, dtype=bool)
        
        if len(cai_smoothed) <= self.burn_in:
            return aging_detected
        
        analysis_window = cai_smoothed[self.burn_in:]
        
        # Method 1: PELT change-point detection (if available)
        if RUPTURES_AVAILABLE:
            try:
                model = rpt.Pelt(model="rbf", min_size=3, jump=1).fit(analysis_window)
                penalty = 2.0 * np.std(analysis_window)
                change_points = model.predict(pen=penalty)
                
                if len(change_points) > 0 and change_points[0] < len(analysis_window):
                    cp_idx = self.burn_in + change_points[0]
                    aging_detected[cp_idx:] = True
                    return aging_detected
            except:
                pass
        
        # Method 2: Threshold-based detection
        baseline_mean = np.mean(cai_smoothed[:self.burn_in + 5])
        baseline_std = np.std(cai_smoothed[:self.burn_in + 5])
        threshold = baseline_mean + 2.5 * baseline_std
        
        consecutive = 0
        for i, val in enumerate(analysis_window):
            if val > threshold:
                consecutive += 1
                if consecutive >= 3:
                    aging_detected[self.burn_in + i - 2:] = True
                    return aging_detected
            else:
                consecutive = 0
        
        # Method 3: Derivative-based (acceleration detection)
        if len(analysis_window) > 10:
            derivatives = np.gradient(analysis_window)
            deriv_threshold = np.mean(derivatives[:5]) + 2.0 * np.std(derivatives[:5])
            
            for i, deriv in enumerate(derivatives):
                if deriv > deriv_threshold:
                    aging_detected[self.burn_in + i:] = True
                    return aging_detected
        
        return aging_detected
    
    def run_experiment(self) -> Tuple[np.ndarray, Dict]:
        """Execute hardware aging monitoring experiment."""
        print("\n" + "="*70)
        print("   Q-AGENET v5.0: IBM Quantum Hardware Aging Monitor")
        print("="*70)
        print(f"Backend: {self.backend_name}")
        print(f"Mode: {'Simulator' if self.hardware.use_simulator else 'Real Hardware'}")
        print(f"Config: {self.num_qubits}Q | {self.num_executions}x | {self.shots} shots")
        print("="*70)
        
        self.start_time = datetime.now()
        
        # Create circuit
        qc = self.create_circuit()
        print(f"\nCircuit: GHZ-{self.num_qubits}")
        print(f"  Gates: {len(qc.data)}")
        print(f"  Depth: {qc.depth()}")
        
        # Establish baseline
        print("\n🔬 Establishing baseline...")
        baseline_counts = self.hardware.execute_circuit(qc, self.shots)
        
        expected_states = ['0' * self.num_qubits, '1' * self.num_qubits]
        baseline_fidelity = self.calculate_fidelity(baseline_counts, expected_states)
        
        print(f"✓ Baseline fidelity: {baseline_fidelity:.4f}")
        print(f"  Top states: {dict(sorted(baseline_counts.items(), key=lambda x: x[1], reverse=True)[:3])}")
        
        if baseline_fidelity < 0.5:
            print("⚠️  Low baseline - normal for real hardware")
        
        # Run repeated executions
        print("\n" + "="*70)
        print("🚀 Starting monitoring sequence...")
        print("="*70)
        
        failed_count = 0
        
        for exec_num in range(self.num_executions):
            exec_start = time.time()
            
            try:
                # Execute
                counts = self.hardware.execute_circuit(qc, self.shots)
                
                # Calculate metrics
                fidelity = self.calculate_fidelity(counts, expected_states)
                entropy = self.calculate_entropy(counts)
                cai = self.calculate_cai(fidelity, baseline_fidelity, exec_num, entropy)
                exec_time = time.time() - exec_start
                
                # Store
                self.fidelities.append(fidelity)
                self.cai_values.append(cai)
                self.entropy_values.append(entropy)
                self.execution_times.append(exec_time)
                
                # Progress
                if (exec_num + 1) % 5 == 0 or exec_num == 0:
                    avg_time = np.mean(self.execution_times)
                    eta_min = (self.num_executions - exec_num - 1) * avg_time / 60
                    print(f"  [{exec_num + 1:3d}/{self.num_executions}] "
                          f"F={fidelity:.3f} | CAI={cai:5.1f} | "
                          f"T={exec_time:4.1f}s | ETA={eta_min:4.1f}m")
                
                # Delay
                if self.execution_delay > 0 and exec_num < self.num_executions - 1:
                    time.sleep(self.execution_delay)
                    
            except Exception as e:
                failed_count += 1
                print(f"  ⚠️  Execution {exec_num} failed: {e}")
                # Skip failed execution
                continue
        
        # Close session
        self.hardware.close_session()
        
        total_time = (datetime.now() - self.start_time).total_seconds() / 60
        
        print("\n" + "="*70)
        print(f"✓ Monitoring complete!")
        print(f"  Valid executions: {len(self.fidelities)}/{self.num_executions}")
        print(f"  Failed: {failed_count}")
        print(f"  Total time: {total_time:.1f} minutes")
        print("="*70)
        
        # Detection
        print("\n🔍 Analyzing aging patterns...")
        self.cai_smoothed = self.smooth_cai(self.cai_values)
        aging_detected = self.detect_aging(self.cai_smoothed)
        
        first_aging = np.where(aging_detected)[0][0] if np.sum(aging_detected) > 0 else None
        print(f"✓ Aging onset: Execution #{first_aging}")
        print(f"  Aged count: {np.sum(aging_detected)}/{len(self.fidelities)}")
        
        # Metadata
        metadata = {
            'backend': self.backend_name,
            'mode': 'simulator' if self.hardware.use_simulator else 'hardware',
            'start_time': self.start_time.isoformat(),
            'end_time': datetime.now().isoformat(),
            'total_runtime_minutes': total_time,
            'valid_executions': len(self.fidelities),
            'failed_executions': failed_count
        }
        
        return aging_detected, metadata
    
    def analyze_results(self, aging_detected: np.ndarray, metadata: Dict) -> Dict:
        """Analyze and export results."""
        print("\n" + "="*70)
        print("📊 ANALYSIS RESULTS")
        print("="*70)
        
        # Metrics
        first_aging = int(np.where(aging_detected)[0][0]) if np.sum(aging_detected) > 0 else None
        baseline_fid = float(self.fidelities[0])
        final_fid = float(self.fidelities[-1])
        mean_fid = float(np.mean(self.fidelities))
        std_fid = float(np.std(self.fidelities))
        drift = final_fid - baseline_fid
        
        print(f"\n🔧 Backend: {self.backend_name} ({metadata['mode']})")
        print(f"⏱️  Runtime: {metadata['total_runtime_minutes']:.1f} min")
        print(f"✅ Success: {metadata['valid_executions']}/{self.num_executions}")
        
        print(f"\n📈 Fidelity:")
        print(f"  Baseline: {baseline_fid:.4f}")
        print(f"  Final:    {final_fid:.4f}")
        print(f"  Mean±Std: {mean_fid:.4f} ± {std_fid:.4f}")
        print(f"  Drift:    {drift:+.4f}")
        
        print(f"\n🎯 Aging Detection:")
        print(f"  First point: #{first_aging}")
        print(f"  Total aged:  {np.sum(aging_detected)}")
        print(f"  Avg CAI:     {np.mean(self.cai_values):.2f}")
        
        # Export
        results = {
            'metadata': metadata,
            'configuration': {
                'num_qubits': self.num_qubits,
                'num_executions': self.num_executions,
                'shots': self.shots,
                'burn_in': self.burn_in
            },
            'metrics': {
                'baseline_fidelity': baseline_fid,
                'final_fidelity': final_fid,
                'mean_fidelity': mean_fid,
                'std_fidelity': std_fid,
                'fidelity_drift': drift,
                'first_aging_execution': first_aging,
                'avg_cai': float(np.mean(self.cai_values))
            },
            'time_series': {
                'fidelities': [float(f) for f in self.fidelities],
                'cai_smoothed': [float(c) for c in self.cai_smoothed],
                'entropy': [float(e) for e in self.entropy_values],
                'exec_times': [float(t) for t in self.execution_times]
            }
        }
        
        filename = f"qagenet_{self.backend_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n💾 Saved: {filename}")
        
        return results
    
    def visualize(self, aging_detected: np.ndarray):
        """Create visualization."""
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        exec_range = np.arange(len(self.fidelities))
        
        # Fidelity
        ax1 = axes[0, 0]
        ax1.plot(exec_range, self.fidelities, 'b-', lw=2, alpha=0.6, label='Fidelity')
        ax1.scatter(exec_range[aging_detected], np.array(self.fidelities)[aging_detected], 
                   c='red', s=50, alpha=0.7, marker='x', label='Aged', zorder=5)
        ax1.set_xlabel('Execution #')
        ax1.set_ylabel('Fidelity')
        ax1.set_title(f'Fidelity - {self.backend_name}', fontweight='bold')
        ax1.legend()
        ax1.grid(alpha=0.3)
        
        # CAI
        ax2 = axes[0, 1]
        ax2.plot(exec_range, self.cai_values, 'g-', lw=1, alpha=0.4, label='Raw')
        ax2.plot(exec_range, self.cai_smoothed, 'darkgreen', lw=2.5, label='Smoothed')
        if np.sum(aging_detected) > 0:
            cp = np.where(aging_detected)[0][0]
            ax2.axvline(cp, c='red', ls='--', lw=2, label='Change Point')
        ax2.set_xlabel('Execution #')
        ax2.set_ylabel('CAI')
        ax2.set_title('Circuit Aging Index', fontweight='bold')
        ax2.legend()
        ax2.grid(alpha=0.3)
        
        # Execution time
        ax3 = axes[1, 0]
        ax3.plot(exec_range, self.execution_times, 'purple', lw=2, alpha=0.7)
        ax3.axhline(np.mean(self.execution_times), c='red', ls='--', 
                   label=f'Mean: {np.mean(self.execution_times):.1f}s')
        ax3.set_xlabel('Execution #')
        ax3.set_ylabel('Time (s)')
        ax3.set_title('Execution Time', fontweight='bold')
        ax3.legend()
        ax3.grid(alpha=0.3)
        
        # Distribution
        ax4 = axes[1, 1]
        ax4.hist(self.fidelities, bins=15, alpha=0.7, color='skyblue', edgecolor='black')
        ax4.axvline(np.mean(self.fidelities), c='red', ls='--', lw=2, 
                   label=f'Mean: {np.mean(self.fidelities):.4f}')
        ax4.set_xlabel('Fidelity')
        ax4.set_ylabel('Count')
        ax4.set_title('Fidelity Distribution', fontweight='bold')
        ax4.legend()
        ax4.grid(alpha=0.3, axis='y')
        
        plt.tight_layout()
        filename = f"qagenet_{self.backend_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        plt.savefig(filename, dpi=150, bbox_inches='tight')
        print(f"📊 Plot: {filename}")
        plt.show()


def main():
    """
    Main execution function.
    
    QUICK START:
    1. Set use_simulator=True for testing (no IBM account needed)
    2. Set use_simulator=False for real hardware (requires IBM credentials)
    """
    
    print("\n" + "="*70)
    print("   Q-AGENET v5.0 - IBM Quantum Hardware Aging Monitor")
    print("="*70)
    
    # ========== CONFIGURATION ==========
    
    USE_SIMULATOR = True  # Change to False for real hardware
    BACKEND_NAME = None   # None = auto-select, or 'ibm_brisbane', 'ibm_kyoto', etc.
    
    # Hardware parameters (optimized for cost/time)
    NUM_QUBITS = 3
    NUM_EXECUTIONS = 30    # Increase to 50-100 for research
    SHOTS = 1024          # Increase to 2048-4096 for better statistics
    
    # ===================================
    
    try:
        qagenet = QAgeNetHardware(
            backend_name=BACKEND_NAME,
            use_simulator=USE_SIMULATOR,
            num_qubits=NUM_QUBITS,
            num_executions=NUM_EXECUTIONS,
            shots=SHOTS,
            burn_in=5,
            smooth_window=3,
            execution_delay=0.5
        )
        
        # Run experiment
        aging_detected, metadata = qagenet.run_experiment()
        
        # Analyze
        results = qagenet.analyze_results(aging_detected, metadata)
        
        # Visualize
        qagenet.visualize(aging_detected)
        
        print("\n" + "="*70)
        print("✅ EXPERIMENT COMPLETE")
        print("="*70)
        print(f"Backend: {qagenet.backend_name}")
        print(f"Runtime: {metadata['total_runtime_minutes']:.1f} min")
        print(f"Results saved successfully!")
        print("="*70 + "\n")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("\n💡 TROUBLESHOOTING:")
        print("   1. For simulator: pip install qiskit-aer==0.13.3")
        print("   2. For IBM hardware:")
        print("      - Save credentials:")
        print("        from qiskit_ibm_runtime import QiskitRuntimeService")
        print("        QiskitRuntimeService.save_account(channel='ibm_quantum', token='YOUR_TOKEN')")
        print("      - Get token: https://quantum.ibm.com/account")
        print("   3. Check package versions:")
        print("      pip install qiskit==1.0.2 qiskit-ibm-runtime==0.21.0")


if __name__ == "__main__":
    main()