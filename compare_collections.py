#!/usr/bin/env python3
"""
ACI Before/After Comparison Script
Uses pyATS for advanced comparison capabilities
Generates detailed diff reports for troubleshooting
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
    from genie.testbed import load
    from pyats.utils.fileutils import FileUtils
    PYATS_AVAILABLE = True
except ImportError:
    PYATS_AVAILABLE = False
    print("pyATS not available. Install with: pip install pyats[full]")
    print("Falling back to basic comparison...")

class ACIComparator:
    """Compare ACI collections before and after maintenance"""
    
    def __init__(self, before_dir: str, after_dir: str):
        self.before_dir = Path(before_dir)
        self.after_dir = Path(after_dir)
        self.comparison_results = {}
        self.summary_stats = {
            "total_devices": 0,
            "devices_compared": 0,
            "devices_with_changes": 0,
            "devices_unchanged": 0,
            "devices_missing_after": 0,
            "new_devices_after": 0
        }
    
    def find_matching_files(self) -> Dict[str, Tuple[str, str]]:
        """Find matching before/after files for comparison"""
        before_files = glob.glob(str(self.before_dir / "*_before_*.json"))
        after_files = glob.glob(str(self.after_dir / "*_after_*.json"))
        
        # Extract device identifiers from filenames
        before_devices = {}
        after_devices = {}
        
        for file in before_files:
            filename = os.path.basename(file)
            # Extract device name from filename (assuming format: device_type_phase_timestamp.json)
            device_id = "_".join(filename.split("_")[:-2])  # Remove phase and timestamp
            before_devices[device_id] = file
        
        for file in after_files:
            filename = os.path.basename(file)
            device_id = "_".join(filename.split("_")[:-2])
            after_devices[device_id] = file
        
        # Find matching pairs
        matching_pairs = {}
        for device_id in before_devices:
            if device_id in after_devices:
                matching_pairs[device_id] = (before_devices[device_id], after_devices[device_id])
        
        return matching_pairs
    
    def load_device_data(self, filepath: str) -> Dict:
        """Load device data from JSON file"""
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading {filepath}: {e}")
            return {}
    
    def basic_comparison(self, before_data: Dict, after_data: Dict) -> Dict:
        """Basic comparison without pyATS"""
        comparison = {
            "metadata_changes": {},
            "command_changes": {},
            "summary": {
                "total_commands": 0,
                "commands_with_changes": 0,
                "commands_unchanged": 0,
                "new_commands": 0,
                "missing_commands": 0
            }
        }
        
        # Compare metadata
        before_meta = before_data.get("metadata", {})
        after_meta = after_data.get("metadata", {})
        
        for key in set(before_meta.keys()) | set(after_meta.keys()):
            before_val = before_meta.get(key, "NOT_PRESENT")
            after_val = after_meta.get(key, "NOT_PRESENT")
            
            if before_val != after_val:
                comparison["metadata_changes"][key] = {
                    "before": before_val,
                    "after": after_val
                }
        
        # Compare commands
        before_commands = before_data.get("commands", {})
        after_commands = after_data.get("commands", {})
        
        # Get all command lists
        before_cmd_lists = []
        after_cmd_lists = []
        
        for cmd_type, cmd_list in before_commands.items():
            if isinstance(cmd_list, list):
                before_cmd_lists.extend(cmd_list)
        
        for cmd_type, cmd_list in after_commands.items():
            if isinstance(cmd_list, list):
                after_cmd_lists.extend(cmd_list)
        
        # Create command dictionaries for comparison
        before_cmd_dict = {cmd.get("command", ""): cmd for cmd in before_cmd_lists}
        after_cmd_dict = {cmd.get("command", ""): cmd for cmd in after_cmd_lists}
        
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
                # Compare command outputs
                before_output = before_cmd.get("output", "")
                after_output = after_cmd.get("output", "")
                
                if before_output != after_output:
                    comparison["command_changes"][cmd] = {
                        "status": "CHANGED",
                        "before": before_cmd,
                        "after": after_cmd,
                        "output_changed": True
                    }
                    comparison["summary"]["commands_with_changes"] += 1
                else:
                    comparison["summary"]["commands_unchanged"] += 1
        
        return comparison
    
    def pyats_comparison(self, before_data: Dict, after_data: Dict) -> Dict:
        """Advanced comparison using pyATS Diff"""
        if not PYATS_AVAILABLE:
            return self.basic_comparison(before_data, after_data)
        
        try:
            # Use pyATS Diff for advanced comparison
            diff = Diff(before_data, after_data)
            diff_result = diff.diff()
            
            # Convert pyATS diff to our format
            comparison = {
                "pyats_diff": str(diff_result),
                "has_changes": len(diff_result) > 0,
                "change_count": len(diff_result),
                "detailed_changes": {}
            }
            
            # Add basic comparison as well
            basic_comp = self.basic_comparison(before_data, after_data)
            comparison.update(basic_comp)
            
            return comparison
            
        except Exception as e:
            print(f"pyATS comparison failed: {e}")
            return self.basic_comparison(before_data, after_data)
    
    def compare_all_devices(self) -> Dict:
        """Compare all matching devices"""
        print(f"Comparing ACI data:")
        print(f"  Before: {self.before_dir}")
        print(f"  After: {self.after_dir}")
        
        matching_files = self.find_matching_files()
        self.summary_stats["total_devices"] = len(matching_files)
        
        if not matching_files:
            print("No matching files found for comparison!")
            return {}
        
        print(f"Found {len(matching_files)} devices to compare")
        
        for device_id, (before_file, after_file) in matching_files.items():
            print(f"\nComparing {device_id}...")
            
            before_data = self.load_device_data(before_file)
            after_data = self.load_device_data(after_file)
            
            if not before_data or not after_data:
                print(f"  Skipping {device_id} - missing data")
                continue
            
            comparison = self.pyats_comparison(before_data, after_data)
            self.comparison_results[device_id] = comparison
            
            # Update summary stats
            self.summary_stats["devices_compared"] += 1
            
            if comparison.get("has_changes", False) or comparison.get("summary", {}).get("commands_with_changes", 0) > 0:
                self.summary_stats["devices_with_changes"] += 1
                print(f"  Changes detected in {device_id}")
            else:
                self.summary_stats["devices_unchanged"] += 1
                print(f"  No changes in {device_id}")
        
        return self.comparison_results
    
    def generate_reports(self, output_dir: str = "comparison_reports") -> List[str]:
        """Generate comparison reports"""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_files = []
        
        # Overall summary report
        summary_file = output_path / f"comparison_summary_{timestamp}.json"
        summary_report = {
            "comparison_metadata": {
                "timestamp": datetime.now().isoformat(),
                "before_directory": str(self.before_dir),
                "after_directory": str(self.after_dir),
                "pyats_available": PYATS_AVAILABLE
            },
            "summary_statistics": self.summary_stats,
            "device_summaries": {}
        }
        
        # Generate device summaries
        for device_id, comparison in self.comparison_results.items():
            device_summary = {
                "device_id": device_id,
                "has_changes": comparison.get("has_changes", False),
                "change_count": comparison.get("change_count", 0),
                "command_summary": comparison.get("summary", {}),
                "metadata_changes": len(comparison.get("metadata_changes", {})),
                "command_changes": len(comparison.get("command_changes", {}))
            }
            summary_report["device_summaries"][device_id] = device_summary
        
        with open(summary_file, 'w') as f:
            json.dump(summary_report, f, indent=2)
        report_files.append(str(summary_file))
        
        # Detailed comparison reports for devices with changes
        for device_id, comparison in self.comparison_results.items():
            if comparison.get("has_changes", False) or comparison.get("summary", {}).get("commands_with_changes", 0) > 0:
                device_report_file = output_path / f"detailed_comparison_{device_id}_{timestamp}.json"
                with open(device_report_file, 'w') as f:
                    json.dump(comparison, f, indent=2)
                report_files.append(str(device_report_file))
        
        # Human-readable summary
        readable_summary = output_path / f"comparison_summary_{timestamp}.txt"
        with open(readable_summary, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write("ACI MAINTENANCE WINDOW COMPARISON SUMMARY\n")
            f.write("=" * 80 + "\n")
            f.write(f"Comparison timestamp: {datetime.now().isoformat()}\n")
            f.write(f"Before directory: {self.before_dir}\n")
            f.write(f"After directory: {self.after_dir}\n")
            f.write(f"pyATS available: {PYATS_AVAILABLE}\n\n")
            
            f.write("OVERALL STATISTICS:\n")
            f.write(f"  Total devices found: {self.summary_stats['total_devices']}\n")
            f.write(f"  Devices compared: {self.summary_stats['devices_compared']}\n")
            f.write(f"  Devices with changes: {self.summary_stats['devices_with_changes']}\n")
            f.write(f"  Devices unchanged: {self.summary_stats['devices_unchanged']}\n\n")
            
            f.write("DEVICES WITH CHANGES:\n")
            for device_id, comparison in self.comparison_results.items():
                if comparison.get("has_changes", False) or comparison.get("summary", {}).get("commands_with_changes", 0) > 0:
                    f.write(f"  {device_id}:\n")
                    summary = comparison.get("summary", {})
                    f.write(f"    Commands with changes: {summary.get('commands_with_changes', 0)}\n")
                    f.write(f"    New commands: {summary.get('new_commands', 0)}\n")
                    f.write(f"    Missing commands: {summary.get('missing_commands', 0)}\n")
                    f.write(f"    Metadata changes: {len(comparison.get('metadata_changes', {}))}\n\n")
            
            f.write("DEVICES WITHOUT CHANGES:\n")
            for device_id, comparison in self.comparison_results.items():
                if not (comparison.get("has_changes", False) or comparison.get("summary", {}).get("commands_with_changes", 0) > 0):
                    f.write(f"  {device_id}\n")
        
        report_files.append(str(readable_summary))
        
        return report_files

def main():
    """Main comparison function"""
    if len(sys.argv) < 3:
        print("Usage: python compare_collections.py <before_dir> <after_dir> [output_dir]")
        print("Example: python compare_collections.py ./aci_outputs/before ./aci_outputs/after")
        sys.exit(1)
    
    before_dir = sys.argv[1]
    after_dir = sys.argv[2]
    output_dir = sys.argv[3] if len(sys.argv) > 3 else "comparison_reports"
    
    if not os.path.exists(before_dir):
        print(f"Before directory not found: {before_dir}")
        sys.exit(1)
    
    if not os.path.exists(after_dir):
        print(f"After directory not found: {after_dir}")
        sys.exit(1)
    
    # Create comparator and run comparison
    comparator = ACIComparator(before_dir, after_dir)
    results = comparator.compare_all_devices()
    
    if not results:
        print("No comparisons performed. Check directory contents and file naming.")
        sys.exit(1)
    
    # Generate reports
    print(f"\nGenerating comparison reports...")
    report_files = comparator.generate_reports(output_dir)
    
    print(f"\nComparison completed!")
    print(f"Reports saved to: {output_dir}")
    print(f"Generated files:")
    for file in report_files:
        print(f"  {file}")
    
    # Print quick summary
    print(f"\nQUICK SUMMARY:")
    print(f"  Devices compared: {comparator.summary_stats['devices_compared']}")
    print(f"  Devices with changes: {comparator.summary_stats['devices_with_changes']}")
    print(f"  Devices unchanged: {comparator.summary_stats['devices_unchanged']}")

if __name__ == "__main__":
    main()
