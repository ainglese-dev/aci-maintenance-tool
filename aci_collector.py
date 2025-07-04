#!/usr/bin/env python3
"""
Cisco ACI Command Collector for Maintenance Window Troubleshooting
Supports before/after comparison with pyATS integration
Handles APIC and LEAF/SPINE devices at scale
"""

import paramiko
import json
import time
import yaml
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

# Try to import pyATS for comparison features
try:
    from pyats.topology import loader
    from pyats.contrib.creators.testbed import yaml_loader
    from genie.testbed import load
    from genie.conf import Genie
    PYATS_AVAILABLE = True
except ImportError:
    PYATS_AVAILABLE = False
    print("pyATS not available - install with: pip install pyats[full]")

class AuthenticationHandler:
    """Handle different authentication methods"""
    
    def __init__(self, auth_type: str = "local", username: str = None, 
                 password: str = None, tacacs_server: str = None):
        self.auth_type = auth_type  # "local" or "tacacs"
        self.username = username
        self.password = password
        self.tacacs_server = tacacs_server
    
    def get_credentials(self) -> Tuple[str, str]:
        """Get username and password based on auth type"""
        if self.auth_type == "tacacs":
            # For TACACS, you might need domain\\username format
            if self.tacacs_server:
                username = f"{self.tacacs_server}\\{self.username}"
            else:
                username = self.username
        else:
            username = self.username
        
        return username, self.password

class SSHConnection:
    """Enhanced SSH connection handler with timeout and retry"""
    
    def __init__(self, hostname: str, auth_handler: AuthenticationHandler, 
                 port: int = 22, timeout: int = 30):
        self.hostname = hostname
        self.auth_handler = auth_handler
        self.port = port
        self.timeout = timeout
        self.client = None
        self.connection_status = "disconnected"
    
    def connect(self) -> bool:
        """Establish SSH connection with retry logic"""
        username, password = self.auth_handler.get_credentials()
        
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Try connection with keepalive
            self.client.connect(
                hostname=self.hostname,
                username=username,
                password=password,
                port=self.port,
                timeout=self.timeout,
                allow_agent=False,
                look_for_keys=False
            )
            
            # Test connection
            transport = self.client.get_transport()
            transport.set_keepalive(60)
            
            self.connection_status = "connected"
            return True
            
        except paramiko.AuthenticationException:
            print(f"Authentication failed for {self.hostname}")
            self.connection_status = "auth_failed"
            return False
        except paramiko.SSHException as e:
            print(f"SSH connection failed to {self.hostname}: {e}")
            self.connection_status = "connection_failed"
            return False
        except Exception as e:
            print(f"Unexpected error connecting to {self.hostname}: {e}")
            self.connection_status = "error"
            return False
    
    def execute_command(self, command: str, timeout: int = 60) -> Dict:
        """Execute command with timeout and error handling"""
        if not self.client:
            return {"error": "No active connection", "output": "", "success": False}
        
        try:
            stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
            
            # Read outputs
            output = stdout.read().decode('utf-8', errors='ignore')
            error = stderr.read().decode('utf-8', errors='ignore')
            exit_code = stdout.channel.recv_exit_status()
            
            return {
                "output": output,
                "error": error,
                "exit_code": exit_code,
                "success": exit_code == 0,
                "command": command
            }
            
        except paramiko.SSHException as e:
            return {"error": f"SSH error: {e}", "output": "", "success": False}
        except Exception as e:
            return {"error": f"Command execution error: {e}", "output": "", "success": False}
    
    def close(self):
        """Close SSH connection"""
        if self.client:
            self.client.close()
            self.connection_status = "disconnected"

class NetworkDevice:
    """Base class for network devices"""
    
    def __init__(self, hostname: str, auth_handler: AuthenticationHandler, 
                 device_type: str, node_id: str = None):
        self.hostname = hostname
        self.auth_handler = auth_handler
        self.device_type = device_type
        self.node_id = node_id
        self.ssh = SSHConnection(hostname, auth_handler)
        self.results = {}
        self.collection_metadata = {
            "device_type": device_type,
            "hostname": hostname,
            "node_id": node_id,
            "start_time": None,
            "end_time": None,
            "total_commands": 0,
            "successful_commands": 0,
            "failed_commands": 0
        }
    
    def _execute_commands(self, commands: List[str], command_type: str = "generic") -> Dict:
        """Execute a list of commands and return results"""
        self.collection_metadata["start_time"] = datetime.now().isoformat()
        
        if not self.ssh.connect():
            return {"error": f"Connection failed to {self.hostname}", "commands": {}}
        
        results = {}
        
        try:
            for cmd in commands:
                print(f"  Executing: {cmd}")
                result = self.ssh.execute_command(cmd)
                
                results[cmd] = {
                    "command": cmd,
                    "output": result.get("output", ""),
                    "error": result.get("error", ""),
                    "success": result.get("success", False),
                    "exit_code": result.get("exit_code", -1),
                    "timestamp": datetime.now().isoformat(),
                    "device_type": self.device_type,
                    "command_type": command_type
                }
                
                if result.get("success", False):
                    self.collection_metadata["successful_commands"] += 1
                else:
                    self.collection_metadata["failed_commands"] += 1
                    if result.get("error"):
                        print(f"    Command failed: {result['error']}")
                
                self.collection_metadata["total_commands"] += 1
                time.sleep(0.5)  # Small delay between commands
                
        finally:
            self.ssh.close()
            self.collection_metadata["end_time"] = datetime.now().isoformat()
        
        return results

class APICDevice(NetworkDevice):
    """APIC Controller specific commands"""
    
    def __init__(self, hostname: str, auth_handler: AuthenticationHandler, node_id: str = None):
        super().__init__(hostname, auth_handler, "APIC", node_id)
    
    def get_apic_commands(self) -> List[str]:
        """Get comprehensive APIC-specific commands"""
        return [
            # Basic system info
            "show version",
            "show hostname",
            "show system uptime",
            
            # Cluster and controller info
            "controller",
            "acidiag fnvread",
            "acidiag avread",
            "acidiag verifyapic",
            
            # Fabric topology
            "show fabric topology",
            "show fabric inventory",
            "show fabric node-identity",
            
            # Endpoint and tenant info
            "show endpoint",
            "show tenant",
            "show bridge-domain",
            "show contract",
            
            # COOP database
            "show coop database",
            "show coop internal info repo brief",
            
            # Health and faults
            "show health",
            "show faults",
            "show eventlog",
            
            # Network policies
            "show vpc domain",
            "show port-channel summary",
            "show interface mgmt0",
            "show interface brief",
            
            # Certificate and security
            "show certificate",
            "show running-config security",
            
            # Licensing
            "show license",
            "show license usage"
        ]
    
    def collect_apic_data(self) -> Dict:
        """Collect comprehensive APIC data"""
        print(f"Collecting APIC data from {self.hostname}")
        commands = self.get_apic_commands()
        return self._execute_commands(commands, "apic_system")

class SwitchDevice(NetworkDevice):
    """LEAF and SPINE switch specific commands"""
    
    def __init__(self, hostname: str, auth_handler: AuthenticationHandler, 
                 switch_type: str, node_id: str = None):
        super().__init__(hostname, auth_handler, switch_type, node_id)
    
    def get_basic_nxos_commands(self) -> List[str]:
        """Get basic NX-OS commands for all switches"""
        return [
            # System information
            "show version",
            "show hostname",
            "show system uptime",
            "show system resources",
            
            # Interface information
            "show interface brief",
            "show interface status",
            "show interface description",
            
            # VPC and port-channel
            "show vpc",
            "show vpc brief",
            "show vpc consistency-parameters",
            "show port-channel summary",
            
            # VLAN information
            "show vlan brief",
            "show vlan extended",
            
            # Routing
            "show ip route summary",
            "show ip route vrf all",
            "show ip interface brief",
            
            # Hardware
            "show hardware",
            "show environment",
            "show processes cpu",
            "show processes memory"
        ]
    
    def get_endpoint_commands(self) -> List[str]:
        """Get endpoint and COOP table commands"""
        return [
            # Endpoint tables
            "show endpoint",
            "show system internal epm endpoint summary",
            "show system internal epm endpoint detail",
            
            # COOP related (for spines mainly)
            "show coop internal info repo brief",
            "show coop internal info repo ep summary",
            "show coop internal info repo ep detail",
            
            # Fabric forwarding
            "show isis dteps vrf overlay-1",
            "show isis adjacency vrf overlay-1",
            "show tunnel interface brief",
            
            # ARP and MAC tables
            "show ip arp",
            "show mac address-table",
            "show mac address-table dynamic",
            
            # VXLAN and overlay
            "show nve peers",
            "show nve vni",
            "show nve interface",
            
            # Hardware forwarding tables
            "show forwarding adjacency",
            "show forwarding route"
        ]
    
    def get_troubleshooting_commands(self) -> List[str]:
        """Get specific troubleshooting commands"""
        return [
            # Internal hardware tables
            "vsh_lc -c 'show system internal eltmc info vlan brief'",
            "show system internal epm vlan all",
            "show system internal forwarding l2 l2table",
            
            # Policy and contracts
            "show system internal policy-mgr stats",
            "show system internal aclmgr rules",
            
            # Fabric health
            "show system internal sysmgr service-state",
            "show logging logfile",
            
            # Performance counters
            "show interface counters",
            "show interface counters errors",
            "show interface counters detailed"
        ]
    
    def collect_switch_data(self) -> Dict:
        """Collect comprehensive switch data"""
        print(f"Collecting {self.switch_type} data from {self.hostname}")
        
        all_commands = (
            self.get_basic_nxos_commands() +
            self.get_endpoint_commands() +
            self.get_troubleshooting_commands()
        )
        
        return self._execute_commands(all_commands, f"{self.switch_type.lower()}_system")

class ACICollector:
    """Main collector class with parallel execution and comparison features"""
    
    def __init__(self, max_workers: int = 10):
        self.devices = []
        self.results = {}
        self.max_workers = max_workers
        self.collection_start_time = None
        self.collection_end_time = None
    
    def add_device(self, device: NetworkDevice):
        """Add device to collection list"""
        self.devices.append(device)
    
    def add_devices_from_inventory(self, inventory_file: str):
        """Add devices from Ansible inventory file"""
        try:
            with open(inventory_file, 'r') as f:
                inventory = yaml.safe_load(f)
            
            # Parse inventory and add devices
            # This is a simplified parser - adjust based on your inventory format
            for group_name, group_data in inventory.items():
                if isinstance(group_data, dict) and 'hosts' in group_data:
                    for host_name, host_data in group_data['hosts'].items():
                        hostname = host_data.get('ansible_host', host_name)
                        username = host_data.get('ansible_user', 'admin')
                        password = host_data.get('ansible_password', 'password')
                        device_type = host_data.get('device_type', 'unknown')
                        node_id = host_data.get('node_id', None)
                        
                        auth_handler = AuthenticationHandler("local", username, password)
                        
                        if device_type.lower() == 'apic':
                            device = APICDevice(hostname, auth_handler, node_id)
                        else:
                            device = SwitchDevice(hostname, auth_handler, device_type.upper(), node_id)
                        
                        self.add_device(device)
                        
        except Exception as e:
            print(f"Error loading inventory: {e}")
    
    def collect_device_data(self, device: NetworkDevice) -> Tuple[str, Dict]:
        """Collect data from a single device"""
        try:
            if isinstance(device, APICDevice):
                data = device.collect_apic_data()
            elif isinstance(device, SwitchDevice):
                data = device.collect_switch_data()
            else:
                data = {"error": "Unknown device type"}
            
            return device.hostname, {
                "device_type": device.device_type,
                "hostname": device.hostname,
                "node_id": device.node_id,
                "collection_metadata": device.collection_metadata,
                "commands": data
            }
            
        except Exception as e:
            return device.hostname, {
                "error": f"Collection failed: {e}",
                "device_type": device.device_type,
                "hostname": device.hostname
            }
    
    def collect_all_parallel(self) -> Dict:
        """Collect data from all devices in parallel"""
        self.collection_start_time = datetime.now()
        print(f"Starting parallel collection from {len(self.devices)} devices...")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_device = {
                executor.submit(self.collect_device_data, device): device 
                for device in self.devices
            }
            
            # Collect results as they complete
            completed = 0
            for future in as_completed(future_to_device):
                device = future_to_device[future]
                try:
                    hostname, result = future.result()
                    self.results[hostname] = result
                    completed += 1
                    print(f"Completed {completed}/{len(self.devices)}: {hostname}")
                    
                except Exception as e:
                    print(f"Device {device.hostname} failed: {e}")
                    self.results[device.hostname] = {
                        "error": f"Collection failed: {e}",
                        "device_type": device.device_type,
                        "hostname": device.hostname
                    }
                    completed += 1
        
        self.collection_end_time = datetime.now()
        return self.results
    
    def save_results(self, filename_prefix: str = "aci_collection", 
                    output_format: str = "both") -> List[str]:
        """Save results in specified format(s)"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        saved_files = []
        
        # Add collection metadata
        collection_metadata = {
            "collection_start_time": self.collection_start_time.isoformat() if self.collection_start_time else None,
            "collection_end_time": self.collection_end_time.isoformat() if self.collection_end_time else None,
            "total_devices": len(self.devices),
            "successful_devices": len([r for r in self.results.values() if "error" not in r or not r["error"]]),
            "failed_devices": len([r for r in self.results.values() if "error" in r and r["error"]]),
            "collection_duration": str(self.collection_end_time - self.collection_start_time) if self.collection_start_time and self.collection_end_time else None
        }
        
        final_results = {
            "metadata": collection_metadata,
            "devices": self.results
        }
        
        if output_format in ["json", "both"]:
            json_filename = f"{filename_prefix}_{timestamp}.json"
            with open(json_filename, 'w') as f:
                json.dump(final_results, f, indent=2)
            saved_files.append(json_filename)
            print(f"JSON results saved to {json_filename}")
        
        if output_format in ["yaml", "both"]:
            yaml_filename = f"{filename_prefix}_{timestamp}.yaml"
            with open(yaml_filename, 'w') as f:
                yaml.dump(final_results, f, default_flow_style=False)
            saved_files.append(yaml_filename)
            print(f"YAML results saved to {yaml_filename}")
        
        return saved_files
    
    def print_summary(self):
        """Print detailed collection summary"""
        print("\n" + "="*70)
        print("ACI COLLECTION SUMMARY")
        print("="*70)
        
        # Overall statistics
        total_devices = len(self.results)
        successful_devices = len([r for r in self.results.values() if "error" not in r or not r["error"]])
        failed_devices = total_devices - successful_devices
        
        print(f"Total devices: {total_devices}")
        print(f"Successful: {successful_devices}")
        print(f"Failed: {failed_devices}")
        
        if self.collection_start_time and self.collection_end_time:
            duration = self.collection_end_time - self.collection_start_time
            print(f"Collection duration: {duration}")
        
        # Device breakdown
        device_types = {}
        for hostname, data in self.results.items():
            device_type = data.get("device_type", "unknown")
            if device_type not in device_types:
                device_types[device_type] = {"total": 0, "successful": 0, "failed": 0}
            
            device_types[device_type]["total"] += 1
            if "error" in data and data["error"]:
                device_types[device_type]["failed"] += 1
            else:
                device_types[device_type]["successful"] += 1
        
        print(f"\nDevice Type Breakdown:")
        for device_type, stats in device_types.items():
            print(f"  {device_type}: {stats['successful']}/{stats['total']} successful")
        
        # Failed devices details
        if failed_devices > 0:
            print(f"\nFailed Devices:")
            for hostname, data in self.results.items():
                if "error" in data and data["error"]:
                    print(f"  {hostname}: {data['error']}")

# Example usage and configuration
if __name__ == "__main__":
    # Configuration
    AUTH_TYPE = "local"  # or "tacacs"
    USERNAME = "admin"
    PASSWORD = "your_password"
    TACACS_SERVER = None  # Set if using TACACS
    
    # Initialize collector
    collector = ACICollector(max_workers=8)  # Adjust based on your network capacity
    
    # Create authentication handler
    auth_handler = AuthenticationHandler(AUTH_TYPE, USERNAME, PASSWORD, TACACS_SERVER)
    
    # Add devices manually (replace with your actual IPs and node IDs)
    apic_devices = [
        ("10.1.1.1", "apic1", "1"),
        ("10.1.1.2", "apic2", "2"),
        ("10.1.1.3", "apic3", "3"),
        ("10.1.1.4", "apic4", "4")
    ]
    
    spine_devices = [
        ("10.1.1.10", "spine1", "101"),
        ("10.1.1.11", "spine2", "102"),
        ("10.1.1.12", "spine3", "103"),
        ("10.1.1.13", "spine4", "104")
    ]
    
    # Add a sample of leaf devices (you would add all 80)
    leaf_devices = [
        ("10.1.1.20", "leaf1", "201"),
        ("10.1.1.21", "leaf2", "202"),
        # ... add your remaining 78 leaf devices
    ]
    
    # Add APIC devices
    for ip, hostname, node_id in apic_devices:
        device = APICDevice(ip, auth_handler, node_id)
        collector.add_device(device)
    
    # Add Spine devices
    for ip, hostname, node_id in spine_devices:
        device = SwitchDevice(ip, auth_handler, "SPINE", node_id)
        collector.add_device(device)
    
    # Add Leaf devices
    for ip, hostname, node_id in leaf_devices:
        device = SwitchDevice(ip, auth_handler, "LEAF", node_id)
        collector.add_device(device)
    
    # Alternative: Load from inventory file
    # collector.add_devices_from_inventory("inventory.yaml")
    
    # Collect data
    print("Starting ACI data collection...")
    results = collector.collect_all_parallel()
    
    # Save results with timestamp for before/after comparison
    maintenance_phase = "before"  # or "after"
    saved_files = collector.save_results(
        filename_prefix=f"aci_collection_{maintenance_phase}",
        output_format="both"
    )
    
    # Print summary
    collector.print_summary()
    
    print(f"\nCollection completed. Files saved: {', '.join(saved_files)}")
    
    if PYATS_AVAILABLE:
        print("\npyATS is available for advanced comparison features.")
        print("Use compare_collections.py to compare before/after results.")
    else:
        print("\nInstall pyATS for advanced comparison features:")
        print("pip install pyats[full]")
