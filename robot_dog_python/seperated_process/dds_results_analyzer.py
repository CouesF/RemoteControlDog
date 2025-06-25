# dds_results_analyzer.py
"""
Analyzer for DDS latency test results - parses log files and generates
comprehensive performance reports.
"""

import os
import re
import json
import statistics
from datetime import datetime
import argparse
import glob

class DDSResultsAnalyzer:
    def __init__(self, results_dir="dds_latency_results"):
        self.results_dir = results_dir
        
    def parse_sender_log(self, log_file):
        """Parse sender log file and extract performance metrics"""
        if not os.path.exists(log_file):
            return None
            
        metrics = {
            "config": {},
            "transmission_times": [],
            "rtt_times": [],
            "messages_sent": 0,
            "responses_received": 0,
            "response_rate": 0.0
        }
        
        try:
            with open(log_file, 'r') as f:
                content = f.read()
            
            # Extract configuration
            config_match = re.search(r'Payload Size: (\d+)KB.*?Frequency: ([\d.]+)Hz.*?Duration: (\d+)s', content, re.DOTALL)
            if config_match:
                metrics["config"] = {
                    "payload_kb": int(config_match.group(1)),
                    "frequency_hz": float(config_match.group(2)),
                    "duration_s": int(config_match.group(3))
                }
            
            # Extract transmission times
            tx_times = re.findall(r'Tx Time: ([\d.]+)ms', content)
            metrics["transmission_times"] = [float(t) for t in tx_times]
            
            # Extract RTT times
            rtt_times = re.findall(r'RTT for seq \d+: ([\d.]+)ms', content)
            metrics["rtt_times"] = [float(t) for t in rtt_times]
            
            # Extract final statistics
            final_stats = re.search(r'Messages Sent: (\d+).*?Responses Received: (\d+).*?Response Rate: ([\d.]+)%', content, re.DOTALL)
            if final_stats:
                metrics["messages_sent"] = int(final_stats.group(1))
                metrics["responses_received"] = int(final_stats.group(2))
                metrics["response_rate"] = float(final_stats.group(3))
            
            return metrics
            
        except Exception as e:
            print(f"Error parsing sender log {log_file}: {e}")
            return None
    
    def parse_receiver_log(self, log_file):
        """Parse receiver log file and extract performance metrics"""
        if not os.path.exists(log_file):
            return None
            
        metrics = {
            "receive_times": [],
            "processing_times": [],
            "messages_received": 0,
            "responses_sent": 0,
            "lost_messages": 0,
            "checksum_errors": 0,
            "out_of_order": 0
        }
        
        try:
            with open(log_file, 'r') as f:
                content = f.read()
            
            # Extract receive and processing times
            process_matches = re.findall(r'Receive: ([\d.]+)ms.*?Process: ([\d.]+)ms', content)
            for receive_time, process_time in process_matches:
                metrics["receive_times"].append(float(receive_time))
                metrics["processing_times"].append(float(process_time))
            
            # Extract final statistics
            final_stats = re.search(
                r'Messages Received: (\d+).*?Responses Sent: (\d+).*?Lost Messages: (\d+).*?Out of Order Messages: (\d+).*?Checksum Errors: (\d+)',
                content, re.DOTALL
            )
            if final_stats:
                metrics["messages_received"] = int(final_stats.group(1))
                metrics["responses_sent"] = int(final_stats.group(2))
                metrics["lost_messages"] = int(final_stats.group(3))
                metrics["out_of_order"] = int(final_stats.group(4))
                metrics["checksum_errors"] = int(final_stats.group(5))
            
            return metrics
            
        except Exception as e:
            print(f"Error parsing receiver log {log_file}: {e}")
            return None
    
    def calculate_statistics(self, values):
        """Calculate comprehensive statistics for a list of values"""
        if not values:
            return {}
        
        sorted_values = sorted(values)
        n = len(sorted_values)
        
        return {
            "count": n,
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "min": min(values),
            "max": max(values),
            "std_dev": statistics.stdev(values) if n > 1 else 0,
            "p95": sorted_values[int(0.95 * n)] if n > 0 else 0,
            "p99": sorted_values[int(0.99 * n)] if n > 0 else 0,
            "p999": sorted_values[int(0.999 * n)] if n > 0 else 0
        }
    
    def analyze_test_pair(self, sender_log, receiver_log):
        """Analyze a sender/receiver log pair"""
        sender_metrics = self.parse_sender_log(sender_log)
        receiver_metrics = self.parse_receiver_log(receiver_log)
        
        if not sender_metrics or not receiver_metrics:
            return None
        
        analysis = {
            "config": sender_metrics["config"],
            "timestamp": datetime.now().isoformat(),
            "files": {
                "sender_log": sender_log,
                "receiver_log": receiver_log
            }
        }
        
        # Transmission time analysis
        if sender_metrics["transmission_times"]:
            analysis["transmission"] = self.calculate_statistics(sender_metrics["transmission_times"])
            analysis["transmission"]["description"] = "Time to publish message (sender-side)"
        
        # Forward path latency (send to receive)
        if receiver_metrics["receive_times"]:
            analysis["forward_latency"] = self.calculate_statistics(receiver_metrics["receive_times"])
            analysis["forward_latency"]["description"] = "Time from send to receive (one-way)"
        
        # Processing time analysis
        if receiver_metrics["processing_times"]:
            analysis["processing"] = self.calculate_statistics(receiver_metrics["processing_times"])
            analysis["processing"]["description"] = "Time to process and respond (receiver-side)"
        
        # Round-trip time analysis
        if sender_metrics["rtt_times"]:
            analysis["round_trip"] = self.calculate_statistics(sender_metrics["rtt_times"])
            analysis["round_trip"]["description"] = "Complete round-trip time"
        
        # Message reliability
        analysis["reliability"] = {
            "messages_sent": sender_metrics["messages_sent"],
            "messages_received": receiver_metrics["messages_received"],
            "responses_sent": receiver_metrics["responses_sent"],
            "responses_received": sender_metrics["responses_received"],
            "response_rate_percent": sender_metrics["response_rate"],
            "lost_messages": receiver_metrics["lost_messages"],
            "checksum_errors": receiver_metrics["checksum_errors"],
            "out_of_order_messages": receiver_metrics["out_of_order"]
        }
        
        # Calculate effective throughput
        if sender_metrics["config"]:
            config = sender_metrics["config"]
            total_data_kb = config["payload_kb"] * sender_metrics["messages_sent"]
            duration_s = config["duration_s"]
            analysis["throughput"] = {
                "total_data_kb": total_data_kb,
                "total_data_mb": total_data_kb / 1024,
                "duration_s": duration_s,
                "throughput_kbps": total_data_kb / duration_s,
                "throughput_mbps": (total_data_kb / 1024) / duration_s,
                "effective_frequency_hz": sender_metrics["messages_sent"] / duration_s
            }
        
        return analysis
    
    def generate_report(self, analysis):
        """Generate a human-readable report from analysis"""
        if not analysis:
            return "No analysis data available"
        
        config = analysis.get("config", {})
        reliability = analysis.get("reliability", {})
        throughput = analysis.get("throughput", {})
        
        report = []
        report.append("="*80)
        report.append("DDS LATENCY TEST ANALYSIS REPORT")
        report.append("="*80)
        
        # Configuration
        report.append(f"\nTEST CONFIGURATION:")
        report.append(f"  Payload Size: {config.get('payload_kb', 'N/A')}KB")
        report.append(f"  Target Frequency: {config.get('frequency_hz', 'N/A')}Hz")
        report.append(f"  Duration: {config.get('duration_s', 'N/A')}s")
        
        # Reliability
        report.append(f"\nMESSAGE RELIABILITY:")
        report.append(f"  Messages Sent: {reliability.get('messages_sent', 'N/A')}")
        report.append(f"  Messages Received: {reliability.get('messages_received', 'N/A')}")
        report.append(f"  Response Rate: {reliability.get('response_rate_percent', 'N/A'):.1f}%")
        report.append(f"  Lost Messages: {reliability.get('lost_messages', 'N/A')}")
        report.append(f"  Checksum Errors: {reliability.get('checksum_errors', 'N/A')}")
        report.append(f"  Out of Order: {reliability.get('out_of_order_messages', 'N/A')}")
        
        # Throughput
        if throughput:
            report.append(f"\nTHROUGHPUT:")
            report.append(f"  Total Data Transferred: {throughput.get('total_data_mb', 0):.1f}MB")
            report.append(f"  Average Throughput: {throughput.get('throughput_mbps', 0):.2f}Mbps")
            report.append(f"  Effective Frequency: {throughput.get('effective_frequency_hz', 0):.1f}Hz")
        
        # Latency metrics
        for metric_name, metric_key in [
            ("TRANSMISSION TIME", "transmission"),
            ("FORWARD LATENCY", "forward_latency"), 
            ("PROCESSING TIME", "processing"),
            ("ROUND-TRIP TIME", "round_trip")
        ]:
            if metric_key in analysis:
                stats = analysis[metric_key]
                report.append(f"\n{metric_name}:")
                report.append(f"  Description: {stats.get('description', '')}")
                report.append(f"  Average: {stats.get('mean', 0):.3f}ms")
                report.append(f"  Median: {stats.get('median', 0):.3f}ms") 
                report.append(f"  Min: {stats.get('min', 0):.3f}ms")
                report.append(f"  Max: {stats.get('max', 0):.3f}ms")
                report.append(f"  Std Dev: {stats.get('std_dev', 0):.3f}ms")
                report.append(f"  95th percentile: {stats.get('p95', 0):.3f}ms")
                report.append(f"  99th percentile: {stats.get('p99', 0):.3f}ms")
                report.append(f"  99.9th percentile: {stats.get('p999', 0):.3f}ms")
        
        report.append("="*80)
        return "\n".join(report)
    
    def find_log_pairs(self):
        """Find all sender/receiver log pairs in results directory"""
        if not os.path.exists(self.results_dir):
            return []
        
        sender_logs = glob.glob(os.path.join(self.results_dir, "sender_*.log"))
        pairs = []
        
        for sender_log in sender_logs:
            # Extract scenario and timestamp from sender log filename
            basename = os.path.basename(sender_log)
            if basename.startswith("sender_"):
                # Replace "sender_" with "receiver_" to find matching receiver log
                receiver_log = sender_log.replace("sender_", "receiver_")
                if os.path.exists(receiver_log):
                    pairs.append((sender_log, receiver_log))
                else:
                    print(f"Warning: No matching receiver log for {sender_log}")
        
        return pairs
    
    def analyze_all_tests(self):
        """Analyze all test pairs and generate reports"""
        pairs = self.find_log_pairs()
        
        if not pairs:
            print(f"No test log pairs found in {self.results_dir}")
            return
        
        results = []
        
        for sender_log, receiver_log in pairs:
            print(f"Analyzing: {os.path.basename(sender_log)}")
            
            analysis = self.analyze_test_pair(sender_log, receiver_log)
            if analysis:
                # Generate and save individual report
                report = self.generate_report(analysis)
                
                # Save report file
                report_filename = sender_log.replace("sender_", "report_").replace(".log", ".txt")
                with open(report_filename, 'w') as f:
                    f.write(report)
                
                print(f"Report saved: {report_filename}")
                results.append(analysis)
        
        # Generate summary report
        if results:
            self.generate_summary_report(results)
        
        return results
    
    def generate_summary_report(self, analyses):
        """Generate a summary report comparing all tests"""
        summary_file = os.path.join(self.results_dir, f"summary_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        
        with open(summary_file, 'w') as f:
            f.write("="*100 + "\n")
            f.write("DDS LATENCY TEST SUMMARY REPORT\n")
            f.write("="*100 + "\n\n")
            
            # Create comparison table
            f.write(f"{'Scenario':<20} {'Size(KB)':<8} {'Freq(Hz)':<8} {'Success%':<8} {'Avg RTT(ms)':<12} {'P95 RTT(ms)':<12} {'Throughput(Mbps)':<15}\n")
            f.write("-" * 100 + "\n")
            
            for analysis in analyses:
                config = analysis.get("config", {})
                reliability = analysis.get("reliability", {})
                throughput = analysis.get("throughput", {})
                rtt_stats = analysis.get("round_trip", {})
                
                scenario = os.path.basename(analysis.get("files", {}).get("sender_log", "")).replace("sender_", "").replace(".log", "")[:19]
                size_kb = config.get("payload_kb", 0)
                freq_hz = config.get("frequency_hz", 0)
                success_rate = reliability.get("response_rate_percent", 0)
                avg_rtt = rtt_stats.get("mean", 0)
                p95_rtt = rtt_stats.get("p95", 0)
                mbps = throughput.get("throughput_mbps", 0)
                
                f.write(f"{scenario:<20} {size_kb:<8} {freq_hz:<8.1f} {success_rate:<8.1f} {avg_rtt:<12.3f} {p95_rtt:<12.3f} {mbps:<15.2f}\n")
            
            f.write("\n" + "="*100 + "\n")
        
        print(f"Summary report saved: {summary_file}")

def main():
    parser = argparse.ArgumentParser(description='DDS Test Results Analyzer')
    parser.add_argument('--results-dir', default='dds_latency_results', 
                       help='Directory containing test results')
    parser.add_argument('--analyze-pair', nargs=2, metavar=('SENDER_LOG', 'RECEIVER_LOG'),
                       help='Analyze specific sender/receiver log pair')
    
    args = parser.parse_args()
    
    analyzer = DDSResultsAnalyzer(args.results_dir)
    
    if args.analyze_pair:
        sender_log, receiver_log = args.analyze_pair
        analysis = analyzer.analyze_test_pair(sender_log, receiver_log)
        if analysis:
            report = analyzer.generate_report(analysis)
            print(report)
        else:
            print("Failed to analyze the specified log pair")
    else:
        analyzer.analyze_all_tests()

if __name__ == "__main__":
    main()