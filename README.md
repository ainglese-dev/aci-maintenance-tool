# ACI Maintenance Data Collection Tool

A comprehensive solution for collecting and comparing Cisco ACI network data before and after maintenance windows. Supports both Python and Ansible execution methods with advanced comparison capabilities using pyATS.

## 🔍 Overview

This tool is designed for Cisco ACI environments to:
- Collect comprehensive network data from APIC controllers, LEAF, and SPINE switches
- Support both before and after maintenance data collection
- Compare configurations and states to identify changes
- Generate detailed reports for troubleshooting purposes
- Handle large-scale deployments (4 APIC, 4 SPINES, 80+ LEAFs)

## 📋 Prerequisites

### System Requirements
- **Linux environment** (Ubuntu, CentOS, RHEL, Rocky)
- **Python 3.8+** 
- **Network connectivity** to ACI devices
- **SSH access** to APIC controllers and switches

> **Windows Users**: pyATS is not supported on Windows. Use **WSL2** or **Docker** for Windows compatibility.

### Network Requirements
- SSH access (port 22) to all ACI devices
- Proper authentication credentials (local or TACACS)

## 🚀 Installation

### Linux Installation

1. **Update System & Install Dependencies**
   ```bash
   # Ubuntu/Debian
   sudo apt update && sudo apt install python3 python3-pip python3-venv git -y

   # CentOS/RHEL/Rocky
   sudo yum install python3 python3-pip git -y
   ```

2. **Clone Repository & Setup Environment**
   ```bash
   git clone https://github.com/your-repo/aci-maintenance-tool.git
   cd aci-maintenance-tool
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install Dependencies**
   ```bash
   # Basic dependencies
   pip install paramiko ansible pyyaml

   # pyATS for advanced comparison
   pip install pyats[full]
   ```

4. **Make Scripts Executable**
   ```bash
   chmod +x aci_maintenance.sh *.py
   ```

5. **Verify Installation**
   ```bash
   ./aci_maintenance.sh check
   ```

### Windows (WSL2/Docker)

**Option A: WSL2**
```bash
# Install WSL2 Ubuntu, then follow Linux installation above
wsl --install -d Ubuntu
```

**Option B: Docker**
```bash
# Build container
docker build -t aci-tool .

# Run container
docker run -it -v $(pwd):/workspace aci-tool
```

## ⚙️ Configuration

### 1. Configure Inventory File

Edit the `inventory` file with your ACI device details:

```ini
[apic]
apic1 ansible_host=10.1.1.1 device_type=apic node_id=1
apic2 ansible_host=10.1.1.2 device_type=apic node_id=2

[spine]
spine1 ansible_host=10.1.1.10 device_type=spine node_id=101
spine2 ansible_host=10.1.1.11 device_type=spine node_id=102

[leaf]
leaf1 ansible_host=10.1.1.20 device_type=leaf node_id=201
leaf2 ansible_host=10.1.1.21 device_type=leaf node_id=202

[aci:children]
apic
spine
leaf

[aci:vars]
ansible_connection=ssh
ansible_user=admin
ansible_password=your_password
# For TACACS: ansible_user=domain\\username
```

### 2. Authentication Options

**Local Authentication:**
```ini
ansible_user=admin
ansible_password=your_local_password
```

**TACACS Authentication:**
```ini
ansible_user=domain\\tacacs_username
ansible_password=your_tacacs_password
```

**SSH Key Authentication:**
```ini
ansible_user=admin
ansible_ssh_private_key_file=~/.ssh/aci_key
```

## 🎯 Usage

### Quick Start

1. **Check Configuration**
   ```bash
   ./aci_maintenance.sh check
   ```

2. **Collect Before Maintenance Data**
   ```bash
   ./aci_maintenance.sh before
   ```

3. **Perform Maintenance** (manual step)

4. **Collect After Maintenance Data**
   ```bash
   ./aci_maintenance.sh after
   ```

5. **Compare Results**
   ```bash
   ./aci_maintenance.sh compare
   ```

### Alternative: Full Automated Cycle

```bash
# Runs before → manual confirmation → after → compare
./aci_maintenance.sh full
```

### Alternative: Direct Commands

```bash
# Using Ansible directly
ansible-playbook -i inventory aci_collection.yml -e "phase=before"

# Using Python directly
python3 aci_collector.py --phase before
```

## 📁 Output Structure

```
aci-maintenance-tool/
├── aci_outputs/
│   ├── before/                  # Before maintenance data
│   │   ├── apic1_apic_before_*.json
│   │   ├── leaf1_leaf_before_*.json
│   │   └── overall_collection_summary_*.json
│   └── after/                   # After maintenance data
└── comparison_reports/          # Comparison reports
    ├── comparison_summary_*.json
    ├── comparison_summary_*.txt
    └── detailed_comparison_*.json
```

## 🔧 Troubleshooting

### Common Issues

1. **SSH Connection Failures**
   ```bash
   # Test connectivity
   ssh admin@10.1.1.1
   ansible all -i inventory -m ping
   ```

2. **Authentication Errors**
   ```bash
   # Test with password prompt
   ansible all -i inventory -m ping --ask-pass
   ```

3. **Python Import Errors**
   ```bash
   # Check packages
   pip list | grep -E "(paramiko|ansible|pyats)"
   
   # Reinstall if needed
   pip install --upgrade paramiko ansible pyats[full]
   ```

4. **Permission Errors**
   ```bash
   chmod +x aci_maintenance.sh *.py
   ```

### Debug Mode

```bash
# Enable debug output
export DEBUG=1
./aci_maintenance.sh before

# Or run with verbose ansible
ansible-playbook -i inventory aci_collection.yml -e "phase=before" -vvv
```

## 📊 Examples

### Example 1: Lab Environment
```bash
# Quick lab test
./aci_maintenance.sh before
# Simulate changes...
./aci_maintenance.sh after
./aci_maintenance.sh compare
```

### Example 2: Specific Device Types
```bash
# Collect only APIC data
ansible-playbook -i inventory aci_collection.yml -e "phase=before" --limit apic

# Collect only leaf switches
ansible-playbook -i inventory aci_collection.yml -e "phase=before" --limit leaf
```

### Example 3: Custom Output Directory
```bash
python3 aci_collector.py --phase before --output-dir ./lab_test_01
```

## 🔒 Security Notes

- Use SSH keys when possible
- Store passwords in Ansible Vault: `ansible-vault encrypt_string 'password' --name 'ansible_password'`
- Limit file permissions: `chmod 600 inventory`

## 📞 Support

For issues:
1. Check the [Troubleshooting](#troubleshooting) section
2. Run with debug mode: `export DEBUG=1`
3. Review log files in the `logs/` directory

---

**Note**: This tool is designed for lab testing and development. Test thoroughly before production deployment.