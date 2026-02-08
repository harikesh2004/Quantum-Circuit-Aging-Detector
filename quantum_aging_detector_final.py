import numpy as np
import matplotlib.pyplot as plt
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, depolarizing_error, thermal_relaxation_error
from datetime import datetime
import json
import warnings
import ruptures as rpt

warnings.filterwarnings('ignore')


class CircuitAging:
    """
    Models quantum circuit aging through progressive noise accumulation.
    
    Simulates realistic hardware degradation with:
    - Linear aging in early executions
    - Accelerated degradation after threshold
    - T1/T2 coherence time decay
    """
    
    def __init__(self, base_depol_1q=0.001, base_depol_2q=0.008, 
                 t1=120000, t2=100000, gate_time=50):
        self.base_depol_1q = base_depol_1q
        self.base_depol_2q = base_depol_2q
        self.t1 = t1
        self.t2 = t2
        self.gate_time = gate_time
        self.aging_factor = 0.0
    
    def get_noise_model(self, execution_number):
        """Generate noise model with age-dependent degradation."""
        # Minimal early aging, accelerating after threshold
        if execution_number < 60:
            self.aging_factor = 1.0 + (execution_number / 1000) * 0.02
        else:
            age_beyond = execution_number - 60
            self.aging_factor = 1.0 + 0.0012 + (age_beyond / 90) * 0.20
        
        noise_model = NoiseModel()
        
        # Single-qubit depolarizing noise
        depol_1q = depolarizing_error(self.base_depol_1q * self.aging_factor, 1)
        
        # Two-qubit noise with super-linear aging (hardware fatigue)
        reuse_factor = 1 + (execution_number / 40) ** 2
        depol_2q = depolarizing_error(
            self.base_depol_2q * self.aging_factor * reuse_factor * 2.0, 2
        )
        
        # Thermal relaxation with T1/T2 decay
        if execution_number >= 60:
            age_factor = 1 + ((execution_number - 60) / 60) * 0.35
            aged_t1 = self.t1 / age_factor
            aged_t2 = self.t2 / age_factor
        else:
            aged_t1 = self.t1
            aged_t2 = self.t2
        
        thermal = thermal_relaxation_error(aged_t1, aged_t2, self.gate_time)
        combined_1q = depol_1q.compose(thermal)
        
        noise_model.add_all_qubit_quantum_error(combined_1q, ['rx', 'ry', 'rz', 'h'])
        noise_model.add_all_qubit_quantum_error(depol_2q, ['cx', 'cz'])
        
        return noise_model


class QAgeNet:
    """
    Quantum Circuit Aging Detection System using change-point detection.
    
    Monitors quantum circuit performance degradation through:
    - Fidelity tracking
    - Circuit Aging Index (CAI) computation
    - Statistical change-point detection (PELT algorithm)
    """
    
    def __init__(self, num_qubits=3, num_executions=150, 
                 shots=2048, burn_in=20, smooth_window=5):
        self.num_qubits = num_qubits
        self.num_executions = num_executions
        self.shots = shots
        self.burn_in = burn_in
        self.smooth_window = smooth_window
        
        # Time series storage
        self.fidelities = []
        self.cai_values = []
        self.noise_levels = []
        self.entropy_values = []
        self.cai_smoothed = []
        
        self.aging_model = CircuitAging()
        
    def create_circuit(self, execution_num=0):
        """Create GHZ circuit with structural aging after threshold."""
        qc = QuantumCircuit(self.num_qubits, self.num_qubits)
        
        # Base GHZ state preparation
        qc.h(0)
        for i in range(self.num_qubits - 1):
            qc.cx(i, i + 1)
        
        # Structural degradation (gate inflation)
        if execution_num >= 60:
            extra_layers = (execution_num - 60) // 10
            for _ in range(extra_layers):
                qc.cx(0, 1)
                qc.cx(1, 2)
        
        qc.measure(range(self.num_qubits), range(self.num_qubits))
        return qc
    
    def calculate_fidelity(self, counts, expected_states):
        """Calculate fidelity as probability of measuring expected states."""
        total_prob = sum(counts.get(state, 0) for state in expected_states)
        return total_prob / self.shots
    
    def calculate_entropy(self, counts):
        """Calculate Shannon entropy of measurement distribution."""
        probabilities = np.array(list(counts.values())) / self.shots
        probabilities = probabilities[probabilities > 0]
        return -np.sum(probabilities * np.log2(probabilities))
    
    def calculate_cai(self, current_fidelity, baseline_fidelity, execution_num, entropy):
        """
        Calculate Circuit Aging Index (CAI).
        
        Weighted combination of:
        - Fidelity decay (40%)
        - Execution wear (25%)
        - Entropy increase (20%)
        - Fidelity trend (15%)
        """
        if baseline_fidelity == 0:
            return 0
        
        fidelity_decay = max(0, (1 - current_fidelity / baseline_fidelity)) * 100
        
        if execution_num < 60:
            execution_wear = (execution_num / 150) * 10
        else:
            execution_wear = 10 + ((execution_num - 60) / 90) * 40
        
        entropy_factor = min(30, entropy * 10)
        fidelity_trend = abs(current_fidelity - baseline_fidelity) * 100
        
        cai = (0.4 * fidelity_decay + 
               0.25 * execution_wear + 
               0.2 * entropy_factor + 
               0.15 * fidelity_trend)
        
        return cai
    
    def smooth_cai(self, cai_series):
        """Apply causal moving average to CAI (uses only past values)."""
        cai_array = np.array(cai_series)
        smoothed = np.zeros_like(cai_array)
        
        for i in range(len(cai_array)):
            start_idx = max(0, i - self.smooth_window + 1)
            smoothed[i] = np.mean(cai_array[start_idx:i+1])
        
        return smoothed
    
    def detect_aging_changepoint(self, cai_smoothed):
        """
        Detect aging using multi-method approach:
        1. PELT change-point detection (primary)
        2. Threshold-based detection (fallback)
        3. Derivative-based detection (acceleration)
        """
        aging_detected = np.zeros(self.num_executions, dtype=bool)
        
        if len(cai_smoothed) <= self.burn_in:
            return aging_detected
        
        analysis_window = cai_smoothed[self.burn_in:]
        
        # Method 1: PELT change-point detection
        try:
            model = rpt.Pelt(model="rbf", min_size=5, jump=1).fit(analysis_window)
            penalty_value = 1.0 * np.std(analysis_window)
            change_points = model.predict(pen=penalty_value)
            
            if len(change_points) > 0 and change_points[0] < len(analysis_window):
                aging_start_idx = self.burn_in + change_points[0]
                aging_detected[aging_start_idx:] = True
                return aging_detected
        except Exception:
            pass
        
        # Method 2: Threshold-based detection (gradual aging)
        baseline_cai = np.mean(cai_smoothed[:self.burn_in + 10])
        baseline_std = np.std(cai_smoothed[:self.burn_in + 10])
        threshold = baseline_cai + 2.0 * baseline_std
        
        consecutive_count = 0
        for i, cai_val in enumerate(analysis_window):
            if cai_val > threshold:
                consecutive_count += 1
                if consecutive_count >= 3:
                    aging_start_idx = self.burn_in + i - 2
                    aging_detected[aging_start_idx:] = True
                    return aging_detected
            else:
                consecutive_count = 0
        
        # Method 3: Derivative-based detection (acceleration)
        if len(analysis_window) > 10:
            derivatives = np.gradient(analysis_window)
            derivative_threshold = np.mean(derivatives[:10]) + 2.0 * np.std(derivatives[:10])
            
            for i, deriv in enumerate(derivatives):
                if deriv > derivative_threshold:
                    aging_start_idx = self.burn_in + i
                    aging_detected[aging_start_idx:] = True
                    return aging_detected
        
        return aging_detected
    
    def run_experiment(self):
        """Execute quantum circuit aging simulation."""
        print("\n" + "="*70)
        print("   Q-AGENET v4.0: Quantum Circuit Aging Detector")
        print("="*70)
        print(f"Configuration: {self.num_qubits} qubits | {self.num_executions} executions | "
              f"{self.shots} shots")
        print(f"Detection: Burn-in={self.burn_in} | Smoothing={self.smooth_window}")
        
        # Establish baseline (ideal GHZ state)
        qc_baseline = self.create_circuit(0)
        ideal_sim = AerSimulator()
        ideal_result = ideal_sim.run(qc_baseline, shots=self.shots).result()
        ideal_counts = ideal_result.get_counts()
        
        expected_states = ['000', '111']
        baseline_fidelity = self.calculate_fidelity(ideal_counts, expected_states)
        
        print(f"\nBaseline: Fidelity={baseline_fidelity:.4f} | "
              f"Gates={len(qc_baseline.data)} | Depth={qc_baseline.depth()}")
        
        if baseline_fidelity < 0.85:
            print(f"⚠️  WARNING: Low baseline fidelity ({baseline_fidelity:.4f})")
        
        # Run aging simulation
        print("\nRunning aging simulation...")
        
        for exec_num in range(self.num_executions):
            qc_aged = self.create_circuit(exec_num)
            noise_model = self.aging_model.get_noise_model(exec_num)
            noisy_sim = AerSimulator(noise_model=noise_model)
            
            result = noisy_sim.run(qc_aged, shots=self.shots).result()
            counts = result.get_counts()
            
            fidelity = self.calculate_fidelity(counts, expected_states)
            entropy = self.calculate_entropy(counts)
            cai = self.calculate_cai(fidelity, baseline_fidelity, exec_num, entropy)
            
            self.fidelities.append(fidelity)
            self.cai_values.append(cai)
            self.noise_levels.append(self.aging_model.aging_factor)
            self.entropy_values.append(entropy)
            
            if (exec_num + 1) % 50 == 0:
                print(f"  [{exec_num + 1}/{self.num_executions}] "
                      f"Fidelity={fidelity:.4f} | CAI={cai:.2f}")
        
        # Apply signal processing and detection
        self.cai_smoothed = self.smooth_cai(self.cai_values)
        aging_detected = self.detect_aging_changepoint(self.cai_smoothed)
        
        first_detection = np.where(aging_detected)[0][0] if np.sum(aging_detected) > 0 else None
        print(f"\n✓ Detection complete: Aging onset at execution #{first_detection}")
        print(f"  Total aged executions: {np.sum(aging_detected)}/{self.num_executions}")
        
        return aging_detected
    
    def analyze_results(self, aging_detected):
        """Analyze and export aging detection performance."""
        print("\n" + "="*70)
        print("RESULTS")
        print("="*70)
        
        # Calculate metrics
        aging_indices = np.where(aging_detected)[0]
        first_aging = int(aging_indices[0]) if len(aging_indices) > 0 else None
        total_aged = int(np.sum(aging_detected))
        
        baseline_fidelity = float(self.fidelities[0])
        final_fidelity = float(self.fidelities[-1])
        fidelity_decay = ((baseline_fidelity - final_fidelity) / baseline_fidelity) * 100
        
        # Detection accuracy (late-stage performance)
        expected_aging_start = 60
        late_stage_aged = np.sum(aging_detected[expected_aging_start:])
        late_stage_total = len(aging_detected[expected_aging_start:])
        detection_accuracy = (late_stage_aged / late_stage_total) * 100 if late_stage_total > 0 else 0
        
        # False positive rate (burn-in period)
        early_false_positives = np.sum(aging_detected[:self.burn_in])
        false_positive_rate = (early_false_positives / self.burn_in) * 100
        
        # Performance summary
        print(f"\n📊 Metrics:")
        print(f"  Fidelity: {baseline_fidelity:.4f} → {final_fidelity:.4f} ({fidelity_decay:.1f}% decay)")
        print(f"  CAI: {np.mean(self.cai_values):.2f} avg | {np.max(self.cai_values):.2f} max")
        print(f"  Entropy: {self.entropy_values[0]:.3f} → {self.entropy_values[-1]:.3f}")
        
        print(f"\n🔍 Detection:")
        print(f"  First aging point: Execution #{first_aging}")
        print(f"  Late-stage accuracy: {detection_accuracy:.1f}%")
        print(f"  False positive rate: {false_positive_rate:.1f}%")
        
        # Export results
        results = {
            'timestamp': datetime.now().strftime("%Y%m%d_%H%M%S"),
            'configuration': {
                'num_qubits': self.num_qubits,
                'num_executions': self.num_executions,
                'shots': self.shots,
                'burn_in': self.burn_in,
                'smooth_window': self.smooth_window
            },
            'metrics': {
                'baseline_fidelity': baseline_fidelity,
                'final_fidelity': final_fidelity,
                'fidelity_decay_percent': float(fidelity_decay),
                'detection_accuracy': float(detection_accuracy),
                'false_positive_rate': float(false_positive_rate),
                'first_aging_execution': first_aging
            },
            'time_series': {
                'fidelities': [float(f) for f in self.fidelities],
                'cai_smoothed': [float(c) for c in self.cai_smoothed],
                'entropy_values': [float(e) for e in self.entropy_values]
            }
        }
        
        filename = f"qagenet_results_{results['timestamp']}.json"
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n📁 Results exported: {filename}")
        
        return results
    
    def visualize_results(self, aging_detected):
        """Create publication-quality visualization."""
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        executions = np.arange(self.num_executions)
        
        # Plot 1: Fidelity evolution
        ax1 = axes[0, 0]
        ax1.plot(executions, self.fidelities, 'b-', linewidth=2, alpha=0.8, label='Fidelity')
        ax1.scatter(executions[aging_detected], np.array(self.fidelities)[aging_detected], 
                   color='red', s=50, alpha=0.7, label='Aging Detected', zorder=5, marker='x')
        ax1.axvline(x=60, color='orange', linestyle='--', alpha=0.5, label='Expected Onset')
        ax1.set_xlabel('Execution Number')
        ax1.set_ylabel('Fidelity')
        ax1.set_title('Fidelity Decay Over Time', fontweight='bold')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Plot 2: CAI evolution
        ax2 = axes[0, 1]
        ax2.plot(executions, self.cai_values, 'g-', linewidth=1, alpha=0.4, label='CAI (raw)')
        ax2.plot(executions, self.cai_smoothed, 'darkgreen', linewidth=2.5, label='CAI (smoothed)')
        if np.sum(aging_detected) > 0:
            first_cp = np.where(aging_detected)[0][0]
            ax2.axvline(x=first_cp, color='red', linestyle='--', linewidth=2, label='Detected CP')
        ax2.set_xlabel('Execution Number')
        ax2.set_ylabel('Circuit Aging Index')
        ax2.set_title('CAI Evolution', fontweight='bold')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # Plot 3: Aging timeline
        ax3 = axes[1, 0]
        aging_binary = aging_detected.astype(int)
        ax3.fill_between(executions, 0, aging_binary, alpha=0.6, color='coral', 
                        step='mid', label='Aging Detected')
        ax3.axvline(x=60, color='blue', linestyle='--', alpha=0.5, label='Expected Start')
        ax3.axvline(x=self.burn_in, color='green', linestyle='--', alpha=0.5, label='Burn-in End')
        ax3.set_xlabel('Execution Number')
        ax3.set_ylabel('Aging Status')
        ax3.set_title('Detection Timeline', fontweight='bold')
        ax3.set_ylim(-0.1, 1.1)
        ax3.set_yticks([0, 1])
        ax3.set_yticklabels(['Normal', 'Aged'])
        ax3.legend()
        ax3.grid(True, alpha=0.3)
        
        # Plot 4: CAI vs Fidelity correlation
        ax4 = axes[1, 1]
        scatter = ax4.scatter(self.cai_values, self.fidelities, alpha=0.6, 
                             c=executions, cmap='viridis', s=40, edgecolors='black', linewidth=0.5)
        ax4.set_xlabel('Circuit Aging Index')
        ax4.set_ylabel('Fidelity')
        ax4.set_title('CAI-Fidelity Correlation', fontweight='bold')
        plt.colorbar(scatter, ax=ax4, label='Execution #')
        ax4.grid(True, alpha=0.3)
        
        plt.tight_layout()
        filename = f"qagenet_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        plt.savefig(filename, dpi=150, bbox_inches='tight')
        print(f"📊 Visualization saved: {filename}")
        plt.show()


def main():
    """Main execution function."""
    qagenet = QAgeNet(
        num_qubits=3,
        num_executions=150,
        shots=2048,
        burn_in=20,
        smooth_window=5
    )
    
    aging_detected = qagenet.run_experiment()
    results = qagenet.analyze_results(aging_detected)
    qagenet.visualize_results(aging_detected)
    
    print("\n" + "="*70)
    print("Q-AGENET ANALYSIS COMPLETE")
    print("="*70)
    
    if results['metrics']['detection_accuracy'] >= 70:
        print("\n✅ SUCCESS: Research objectives achieved")
    else:
        print("\n⚠️  Review detection parameters")


if __name__ == "__main__":
    main()