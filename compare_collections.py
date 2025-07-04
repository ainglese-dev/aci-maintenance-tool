#!/usr/bin/env python3
"""
ACI Before/After Comparison Script (Optimized)
Handles both legacy and optimized data structures with APIC failover support
"""

import json
import os
import sys
import glob
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path

# Try to import pyATS components
try:
    from genie.utils.diff import Diff
    PYATS_AVAILABLE = True
except ImportError:
    PYATS_AVAILABLE = False
    print("pyATS not available. Install with: pip install pyats[full]")

class ACIComparator:
    """Compare ACI collections with optimization support"""
    
    def __init__(self, before_dir: str, after_dir: str):
        self.before_dir = Path(before_dir)
        self.after_dir = Path(after_dir)
        self.comparison_results = {}
        self.fabric_wide_comparison = {}
        self.summary_stats = {
            "total_devices": 0, "devices_compared": 0, "devices_with_changes": 0,
            "devices_unchanged": 0, "fabric_wide_changes": False, "optimization_detected": False
        }
    
    def find_fabric_wide_files(self) -> Tuple[Optional[str], Optional[str]]:
        """Find fabric-wide data files"""
        before_fabric = glob.glob(str(self.before_dir / "fabric_wide_data_before_*.json"))
        after_fabric = glob.glob(str(self.after_dir / "fabric_wide_data_after_*.json"))
        return (before_fabric[0] if before_fabric else None, 
                after_fabric[0] if after_fabric else None)
    
    def find_matching_files(self) -> Dict[str, Tuple[str, str]]:
        """Find matching device files"""
        # Try optimized patterns first
        before_files = glob.glob(str(self.before_dir / "*_specific_before_*.json"))
        after_files = glob.glob(str(self.after_dir / "*_specific_after_*.json"))
        
        # Fallback to legacy patterns
        if not before_files:
            before_files = [f for f in glob.glob(str(self.before_dir / "*_before_*.json")) 
                           if "fabric_wide_data" not in f]
        if not after_files:
            after_files = [f for f in glob.glob(str(self.after_dir / "*_after_*.json")) 
                          if "fabric_wide_data" not in f]
        
        # Extract device IDs
        before_devices = {}
        after_devices = {}
        
        for file in before_files:
            filename = os.path.basename(file)
            device_id = filename.split("_specific_")[0] if "_specific_" in filename else "_".join(filename.split("_")[:-2])
            before_devices[device_id] = file
        
        for file in after_files:
            filename = os.path.basename(file)
            device_id = filename.split("_specific_")[0] if "_specific_" in filename else "_".join(filename.split("_")[:-2])
            after_devices[device_id] = file
        
        return {device_id: (before_devices[device_id], after_devices[device_id]) 
                for device_id in before_devices if device_id in after_devices}
    
    def load_device_data(self, filepath: str) -> Dict:
        """Load device data from JSON file"""
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading {filepath}: {e}")
            return {}
    
    def extract_command_data(self, device_data: Dict) -> List[Dict]:
        """Extract command data from device structure"""
        commands = []
        
        # Handle optimized format
        if "fabric_wide_data" in device_data and "device_specific_data" in device_data:
            self.summary_stats["optimization_detected"] = True
            device_specific = device_data.get("device_specific_data", {})
            for device_info in device_specific.values():
                device_commands = device_info.get("commands", {})
                if isinstance(device_commands, dict):
                    for cmd_list in device_commands.values():
                        if isinstance(cmd_list, list):
                            commands.extend(cmd_list)
                elif isinstance(device_commands, list):
                    commands.extend(device_commands)
        
        # Handle legacy format or direct device data
        elif "commands" in device_data:
            device_commands = device_data["commands"]
            if isinstance(device_commands, dict):
                for cmd_list in device_commands.values():
                    if isinstance(cmd_list, list):
                        commands.extend(cmd_list)
            elif isinstance(device_commands, list):
                commands.extend(device_commands)
        
        return commands
    
    def basic_comparison(self, before_data: Dict, after_data: Dict) -> Dict:
        """Basic comparison without pyATS"""
        comparison = {
            "metadata_changes": {},
            "command_changes": {},
            "summary": {"total_commands": 0, "commands_with_changes": 0, "commands_unchanged": 0, "new_commands": 0, "missing_commands": 0}
        }
        
        # Compare metadata
        before_meta = before_data.get("metadata", {})
        after_meta = after_data.get("metadata", {})
        
        for key in set(before_meta.keys()) | set(after_meta.keys()):
            before_val = before_meta.get(key, "NOT_PRESENT")
            after_val = after_meta.get(key, "NOT_PRESENT")
            if before_val != after_val:
                comparison["metadata_changes"][key] = {"before": before_val, "after": after_val}
        
        # Compare commands
        before_cmd_list = self.extract_command_data(before_data)
        after_cmd_list = self.extract_command_data(after_data)
        
        before_cmd_dict = {cmd.get("command", ""): cmd for cmd in before_cmd_list}
        after_cmd_dict = {cmd.get("command", ""): cmd for cmd in after_cmd_list}
        
        all_commands = set(before_cmd_dict.keys()) | set(after_cmd_dict.keys())
        comparison["summary"]["total_commands"] = len(all_commands)
        
        for cmd in all_commands:
            before_cmd = before_cmd_dict.get(cmd, {})
            after_cmd = after_cmd_dict.get(cmd, {})
            
            if not before_cmd:
                comparison["command_changes"][cmd] = {"status": "NEW_COMMAND", "after": after_cmd}
                comparison["summary"]["new_commands"] += 1
            elif not after_cmd:
                comparison["command_changes"][cmd] = {"status": "MISSING_COMMAND", "before": before_cmd}
                comparison["summary"]["missing_commands"] += 1
            else:
                if before_cmd.get("output", "") != after_cmd.get("output", ""):
                    comparison["command_changes"][cmd] = {"status": "CHANGED", "before": before_cmd, "after": after_cmd, "output_changed": True}
                    comparison["summary"]["commands_with_changes"] += 1
                else:
                    comparison["summary"]["commands_unchanged"] += 1
        
        return comparison
    
    def pyats_comparison(self, before_data: Dict, after_data: Dict) -> Dict:
        """Advanced comparison using pyATS"""
        if not PYATS_AVAILABLE:
            return self.basic_comparison(before_data, after_data)
        
        try:
            diff = Diff(before_data, after_data)
            diff_result = diff.diff()
            comparison = {"pyats_diff": str(diff_result), "has_changes": len(diff_result) > 0, "change_count": len(diff_result)}
            comparison.update(self.basic_comparison(before_data, after_data))
            return comparison
        except Exception as e:
            print(f"pyATS comparison failed: {e}")
            return self.basic_comparison(before_data, after_data)
    
    def compare_fabric_wide_data(self, before_file: str, after_file: str) -> Dict:
        """Compare fabric-wide data"""
        print("Comparing fabric-wide data...")
        
        before_data = self.load_device_data(before_file)
        after_data = self.load_device_data(after_file)
        
        if not before_data or not after_data:
            return {"error": "Could not load fabric-wide data files"}
        
        before_meta = before_data.get("metadata", {})
        after_meta = after_data.get("metadata", {})
        
        source_comparison = {
            "before_source": before_meta.get("source_apic", "unknown"),
            "after_source": after_meta.get("source_apic", "unknown"),
            "source_changed": before_meta.get("source_apic") != after_meta.get("source_apic")
        }
        
        comparison = self.pyats_comparison(before_data, after_data)
        comparison["source_comparison"] = source_comparison
        comparison["data_type"] = "fabric_wide"
        
        return comparison
    
    def compare_all_devices(self) -> Dict:
        """Compare all devices with optimization support"""
        print(f"Comparing optimized ACI data:")
        print(f"  Before: {self.before_dir}")
        print(f"  After: {self.after_dir}")
        
        # Compare fabric-wide data if available
        before_fabric, after_fabric = self.find_fabric_wide_files()
        
        if before_fabric and after_fabric:
            print(f"\nComparing fabric-wide data...")
            self.fabric_wide_comparison = self.compare_fabric_wide_data(before_fabric, after_fabric)
            
            if (self.fabric_wide_comparison.get("has_changes", False) or 
                self.fabric_wide_comparison.get("summary", {}).get("commands_with_changes", 0) > 0):
                self.summary_stats["fabric_wide_changes"] = True
                print(f"✓ Fabric-wide changes detected")
            else:
                print(f"✓ No fabric-wide changes detected")
        
        # Compare device-specific data
        matching_files = self.find_matching_files()
        self.summary_stats["total_devices"] = len(matching_files)
        
        if not matching_files:
            print("No matching device files found!")
            return {"fabric_wide_comparison": self.fabric_wide_comparison}
        
        print(f"Found {len(matching_files)} devices to compare")
        
        for device_id, (before_file, after_file) in matching_files.items():
            print(f"Comparing {device_id}...")
            
            before_data = self.load_device_data(before_file)
            after_data = self.load_device_data(after_file)
            
            if not before_data or not after_data:
                continue
            
            comparison = self.pyats_comparison(before_data, after_data)
            comparison["data_type"] = "device_specific"
            self.comparison_results[device_id] = comparison
            
            self.summary_stats["devices_compared"] += 1
            
            if (comparison.get("has_changes", False) or 
                comparison.get("summary", {}).get("commands_with_changes", 0) > 0):
                self.summary_stats["devices_with_changes"] += 1
            else:
                self.summary_stats["devices_unchanged"] += 1
        
        return {"fabric_wide_comparison": self.fabric_wide_comparison, "device_comparisons": self.comparison_results}
    
    def generate_reports(self, output_dir: str = "comparison_reports") -> List[str]:
        """Generate comparison reports"""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_files = []
        
        # JSON summary report
        summary_file = output_path / f"comparison_summary_optimized_{timestamp}.json"
        summary_report = {
            "comparison_metadata": {
                "timestamp": datetime.now().isoformat(),
                "before_directory": str(self.before_dir),
                "after_directory": str(self.after_dir),
                "optimization_detected": self.summary_stats["optimization_detected"]
            },
            "summary_statistics": self.summary_stats,
            "fabric_wide_summary": {
                "has_changes": self.fabric_wide_comparison.get("has_changes", False),
                "source_comparison": self.fabric_wide_comparison.get("source_comparison", {})
            } if self.fabric_wide_comparison else {},
            "device_summaries": {
                device_id: {
                    "has_changes": comparison.get("has_changes", False),
                    "command_summary": comparison.get("summary", {})
                } for device_id, comparison in self.comparison_results.items()
            }
        }
        
        with open(summary_file, 'w') as f:
            json.dump(summary_report, f, indent=2)
        report_files.append(str(summary_file))
        
        # Text summary
        readable_summary = output_path / f"comparison_summary_{timestamp}.txt"
        with open(readable_summary, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write("ACI MAINTENANCE COMPARISON SUMMARY (OPTIMIZED)\n")
            f.write("=" * 80 + "\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            f.write(f"Optimization detected: {self.summary_stats['optimization_detected']}\n\n")
            
            f.write("STATISTICS:\n")
            f.write(f"  Devices compared: {self.summary_stats['devices_compared']}\n")
            f.write(f"  Devices with changes: {self.summary_stats['devices_with_changes']}\n")
            f.write(f"  Devices unchanged: {self.summary_stats['devices_unchanged']}\n")
            f.write(f"  Fabric-wide changes: {self.summary_stats['fabric_wide_changes']}\n\n")
            
            if self.fabric_wide_comparison:
                source_comp = self.fabric_wide_comparison.get("source_comparison", {})
                f.write("FABRIC-WIDE DATA:\n")
                f.write(f"  Before source: {source_comp.get('before_source', 'unknown')}\n")
                f.write(f"  After source: {source_comp.get('after_source', 'unknown')}\n")
                f.write(f"  Source changed: {source_comp.get('source_changed', False)}\n\n")
            
            f.write("DEVICES WITH CHANGES:\n")
            for device_id, comparison in self.comparison_results.items():
                if (comparison.get("has_changes", False) or 
                    comparison.get("summary", {}).get("commands_with_changes", 0) > 0):
                    summary = comparison.get("summary", {})
                    f.write(f"  {device_id}: {summary.get('commands_with_changes', 0)} changes\n")
        
        report_files.append(str(readable_summary))
        return report_files

def main():
    """Main comparison function"""
    if len(sys.argv) < 3:
        print("Usage: python compare_collections.py <before_dir> <after_dir> [output_dir]")
        sys.exit(1)
    
    before_dir = sys.argv[1]
    after_dir = sys.argv[2]
    output_dir = sys.argv[3] if len(sys.argv) > 3 else "comparison_reports"
    
    if not os.path.exists(before_dir) or not os.path.exists(after_dir):
        print("Before or after directory not found")
        sys.exit(1)
    
    comparator = ACIComparator(before_dir, after_dir)
    results = comparator.compare_all_devices()
    
    if not results:
        print("No comparisons performed")
        sys.exit(1)
    
    report_files = comparator.generate_reports(output_dir)
    
    print(f"\nComparison completed!")
    print(f"Reports: {', '.join(report_files)}")
    print(f"Devices compared: {comparator.summary_stats['devices_compared']}")
    print(f"Devices with changes: {comparator.summary_stats['devices_with_changes']}")

if __name__ == "__main__":
    main()
