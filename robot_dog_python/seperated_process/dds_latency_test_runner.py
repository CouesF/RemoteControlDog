# dds_latency_test_runner.py
"""
Convenient test runner for DDS latency tests with predefined scenarios
and automated result collection.
"""

import subprocess
import time
import os
import sys
import json
from datetime import datetime
import argparse

class DDSLatencyTestRunner:
    def __init__(self, network_interface="enP8p1s0"):
        self.network_interface = network_interface
        self.results_dir = "dds_latency_results"
        self.ensure_results_directory()
        
    def ensure_results_directory(self):
        """Create results directory if it doesn't exist"""
        if not os.path.exists(self.results_dir):
            os.makedirs(self.results_dir)
            print(f"Created results directory: {self.results_dir}")
    
    def run_test_scenario(self, payload_size_kb, frequency_hz, duration_seconds, scenario_name):
        """Run a single test scenario"""
        print(f"\n{'='*70}")
        print(f"RUNNING SCENARIO: {scenario_name}")
        print(f"Payload: {payload_size_kb}KB | Frequency: {frequency_hz}Hz | Duration: {duration_seconds}s")
        print(f"{'='*70}")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Start receiver in background
        print("Starting receiver...")
        receiver_log = f"{self.results_dir}/receiver_{scenario_name}_{timestamp}.log"
        receiver_process = subprocess.Popen([
            sys.executable, "dds_latency_test_receiver.py",
            "--interface", self.network_interface
        ], stdout=open(receiver_log, 'w'), stderr=subprocess.STDOUT)
        
        # Give receiver time to initialize
        time.sleep(3)
        
        try:
            # Run sender
            print("Starting sender...")
            sender_log = f"{self.results_dir}/sender_{scenario_name}_{timestamp}.log"
            sender_process = subprocess.Popen([
                sys.executable, "dds_latency_test_sender.py",
                "--interface", self.network_interface,
                "--size", str(payload_size_kb),
                "--frequency", str(frequency_hz),
                "--duration", str(duration_seconds)
            ], stdout=open(sender_log, 'w'), stderr=subprocess.STDOUT)
            
            # Wait for sender to complete
            sender_process.wait()
            print(f"Sender completed. Results in: {sender_log}")
            
        finally:
            # Stop receiver
            print("Stopping receiver...")
            receiver_process.terminate()
            try:
                receiver_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                receiver_process.kill()
            print(f"Receiver stopped. Results in: {receiver_log}")
        
        print(f"Scenario '{scenario_name}' completed!")
        return sender_log, receiver_log
    
    def run_predefined_scenarios(self):
        """Run a set of predefined test scenarios"""
        scenarios = [
            # Standard scenarios
            {"name": "500KB_20Hz", "size": 500, "freq": 20, "duration": 30},
            {"name": "100KB_50Hz", "size": 100, "freq": 50, "duration": 30},
            {"name": "1MB_10Hz", "size": 1000, "freq": 10, "duration": 30},
            
            # High frequency scenarios
            {"name": "250KB_40Hz", "size": 250, "freq": 40, "duration": 30},
            {"name": "50KB_100Hz", "size": 50, "freq": 100, "duration": 20},
            
            # Large payload scenarios
            {"name": "2MB_5Hz", "size": 2000, "freq": 5, "duration": 30},
            {"name": "5MB_2Hz", "size": 5000, "freq": 2, "duration": 30},
        ]
        
        print("Running predefined DDS latency test scenarios...")
        print(f"Network Interface: {self.network_interface}")
        print(f"Results will be saved to: {self.results_dir}/")
        
        results_summary = []
        
        for i, scenario in enumerate(scenarios, 1):
            print(f"\nProgress: {i}/{len(scenarios)} scenarios")
            
            try:
                sender_log, receiver_log = self.run_test_scenario(
                    payload_size_kb=scenario["size"],
                    frequency_hz=scenario["freq"],
                    duration_seconds=scenario["duration"],
                    scenario_name=scenario["name"]
                )
                
                results_summary.append({
                    "scenario": scenario["name"],
                    "config": scenario,
                    "sender_log": sender_log,
                    "receiver_log": receiver_log,
                    "status": "completed"
                })
                
            except Exception as e:
                print(f"Error in scenario {scenario['name']}: {e}")
                results_summary.append({
                    "scenario": scenario["name"],
                    "config": scenario,
                    "status": "failed",
                    "error": str(e)
                })
            
            # Brief pause between scenarios
            if i < len(scenarios):
                print("Pausing between scenarios...")
                time.sleep(5)
        
        # Save summary
        summary_file = f"{self.results_dir}/test_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(summary_file, 'w') as f:
            json.dump(results_summary, f, indent=2)
        
        print(f"\n{'='*70}")
        print("ALL SCENARIOS COMPLETED!")
        print(f"Summary saved to: {summary_file}")
        print(f"Individual logs in: {self.results_dir}/")
        print(f"{'='*70}")
        
        return results_summary
    
    def run_custom_scenario(self, payload_size_kb, frequency_hz, duration_seconds):
        """Run a custom test scenario"""
        scenario_name = f"custom_{payload_size_kb}KB_{frequency_hz}Hz"
        return self.run_test_scenario(payload_size_kb, frequency_hz, duration_seconds, scenario_name)

def main():
    parser = argparse.ArgumentParser(description='DDS Latency Test Runner')
    parser.add_argument('--interface', default='enP8p1s0', help='DDS network interface')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Predefined scenarios command
    predefined_parser = subparsers.add_parser('predefined', help='Run predefined test scenarios')
    
    # Custom scenario command
    custom_parser = subparsers.add_parser('custom', help='Run custom test scenario')
    custom_parser.add_argument('--size', type=int, required=True, help='Payload size in KB')
    custom_parser.add_argument('--frequency', type=float, required=True, help='Test frequency in Hz')
    custom_parser.add_argument('--duration', type=int, default=60, help='Test duration in seconds')
    
    # Single test command (interactive)
    single_parser = subparsers.add_parser('single', help='Run single interactive test')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    runner = DDSLatencyTestRunner(network_interface=args.interface)
    
    if args.command == 'predefined':
        runner.run_predefined_scenarios()
        
    elif args.command == 'custom':
        runner.run_custom_scenario(args.size, args.frequency, args.duration)
        
    elif args.command == 'single':
        # Interactive mode
        print("=== Interactive DDS Latency Test ===")
        try:
            size = int(input("Enter payload size in KB (e.g., 500): "))
            freq = float(input("Enter frequency in Hz (e.g., 20): "))
            duration = int(input("Enter duration in seconds (e.g., 60): "))
            
            runner.run_custom_scenario(size, freq, duration)
            
        except (ValueError, KeyboardInterrupt) as e:
            print(f"Invalid input or cancelled: {e}")

if __name__ == "__main__":
    main()