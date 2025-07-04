# ACI Maintenance Tool - Customer Quick Start 🚀

## For Windows Environments with ACI Fabric Access

### ⚡ Super Quick Start (5 minutes)

1. **Extract this package** to `C:\aci-maintenance-tool\`

2. **Run PowerShell as Administrator** and execute:
   ```powershell
   cd C:\aci-maintenance-tool
   .\setup-customer.ps1 -ApicIP "YOUR_APIC_IP" -Username "YOUR_USERNAME"
   ```

3. **Open VSCode** → **Docker Extension** → **Right-click `aci-maintenance-tool` container** → **"Attach Visual Studio Code"**

4. **In VSCode terminal**:
   ```bash
   cd /aci-tool
   cp customer-config/inventory ./inventory
   # Edit inventory file to update password and add switches
   ./aci_maintenance.sh check
   ```

5. **Ready!** Run your maintenance collection:
   ```bash
   ./aci_maintenance.sh before
   # Perform your maintenance...
   ./aci_maintenance.sh after
   ./aci_maintenance.sh compare
   ```

## 📁 What You Get

- **Ubuntu container** with all ACI tools pre-installed
- **VSCode integration** for easy file editing and terminal access
- **Persistent storage** - your data stays on Windows filesystem
- **Network connectivity** to your ACI fabric
- **APIC failover optimization** - ~70% faster data collection

## 🎯 Key Files

| File/Directory | Purpose |
|----------------|---------|
| `customer-config\inventory` | **Your ACI device configuration** |
| `aci_outputs\` | **Collection results** (before/after data) |
| `comparison_reports\` | **Analysis reports** (what changed) |
| `setup-customer.ps1` | **Automated setup script** |

## 🔧 Main Commands

```bash
# Test connectivity to your ACI fabric
./aci_maintenance.sh check

# Collect data before maintenance
./aci_maintenance.sh before

# Collect data after maintenance  
./aci_maintenance.sh after

# Generate change comparison report
./aci_maintenance.sh compare

# Full automated cycle (with prompts)
./aci_maintenance.sh full
```

## 💡 Pro Tips

- **Edit files in VSCode** - changes are immediately saved to Windows
- **Use integrated terminal** - runs inside the Ubuntu container
- **View results** - browse `aci_outputs\` and `comparison_reports\` directories
- **No installation needed** - everything runs in the container
- **Cleanup** - `docker-compose down` removes the container when done

## 📞 Need Help?

1. **Container issues**: `docker-compose logs`
2. **ACI connectivity**: Check network access and credentials in inventory file
3. **VSCode connection**: Ensure Docker Desktop is running

---

**Ready to streamline your ACI maintenance! 🎉**
