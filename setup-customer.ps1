# ACI Maintenance Tool - Customer Setup Script
# Run this script to set up the tool on customer Windows environment

param(
    [string]$ToolPath = "C:\aci-maintenance-tool",
    [string]$ApicIP = "",
    [string]$Username = "admin"
)

Write-Host "=== ACI Maintenance Tool - Customer Setup ===" -ForegroundColor Green

# Check prerequisites
Write-Host "Checking prerequisites..." -ForegroundColor Yellow

# Check Docker
try {
    docker --version | Out-Null
    Write-Host "✓ Docker is installed" -ForegroundColor Green
} catch {
    Write-Host "✗ Docker is not installed or not running" -ForegroundColor Red
    Write-Host "Please install Docker Desktop and ensure it's running" -ForegroundColor Red
    exit 1
}

# Check if tool directory exists
if (-not (Test-Path $ToolPath)) {
    Write-Host "✗ Tool directory not found: $ToolPath" -ForegroundColor Red
    Write-Host "Please extract the ACI tool package to $ToolPath" -ForegroundColor Red
    exit 1
}

Write-Host "✓ Tool directory found: $ToolPath" -ForegroundColor Green

# Navigate to tool directory
Set-Location $ToolPath

# Create required directories
Write-Host "Creating customer directories..." -ForegroundColor Yellow

$directories = @("customer-config", "ssh-keys", "aci_outputs", "comparison_reports")
foreach ($dir in $directories) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir | Out-Null
        Write-Host "✓ Created directory: $dir" -ForegroundColor Green
    } else {
        Write-Host "✓ Directory exists: $dir" -ForegroundColor Green
    }
}

# Create sample inventory if APIC IP provided
if ($ApicIP -ne "") {
    Write-Host "Creating sample inventory configuration..." -ForegroundColor Yellow
    
    $inventoryContent = @"
[apic]
apic1 ansible_host=$ApicIP device_type=apic node_id=1 apic_priority=1

[spine]
# Add your spine switches here
# spine1 ansible_host=10.1.1.10 device_type=spine node_id=101

[leaf]  
# Add your leaf switches here
# leaf1 ansible_host=10.1.1.20 device_type=leaf node_id=201

[aci:children]
apic
spine
leaf

[aci:vars]
ansible_connection=ssh
ansible_user=$Username
ansible_password=CHANGE_THIS_PASSWORD
ansible_ssh_common_args='-o StrictHostKeyChecking=no'
"@

    $inventoryContent | Out-File -FilePath "customer-config\inventory" -Encoding UTF8
    Write-Host "✓ Sample inventory created in customer-config\inventory" -ForegroundColor Green
    Write-Host "  Remember to update the password and add your switches!" -ForegroundColor Yellow
}

# Build and start container
Write-Host "Building and starting ACI tool container..." -ForegroundColor Yellow

try {
    # Build the container
    docker-compose build --quiet
    Write-Host "✓ Container built successfully" -ForegroundColor Green
    
    # Start the container
    docker-compose up -d
    Write-Host "✓ Container started successfully" -ForegroundColor Green
    
    # Wait a moment for container to be ready
    Start-Sleep -Seconds 3
    
    # Check container status
    $containerStatus = docker-compose ps --services --filter "status=running"
    if ($containerStatus -contains "aci-tool") {
        Write-Host "✓ ACI tool container is running" -ForegroundColor Green
    } else {
        Write-Host "⚠ Container may not be running properly" -ForegroundColor Yellow
    }
    
} catch {
    Write-Host "✗ Error building/starting container: $_" -ForegroundColor Red
    exit 1
}

# Instructions for VSCode connection
Write-Host ""
Write-Host "=== Next Steps ===" -ForegroundColor Green
Write-Host "1. Open VSCode" -ForegroundColor White
Write-Host "2. Install Docker extension if not already installed" -ForegroundColor White
Write-Host "3. Click Docker icon in left sidebar" -ForegroundColor White
Write-Host "4. Find 'aci-maintenance-tool' container" -ForegroundColor White
Write-Host "5. Right-click → 'Attach Visual Studio Code'" -ForegroundColor White
Write-Host "6. In VSCode terminal, run: cd /aci-tool && ./aci_maintenance.sh check" -ForegroundColor White
Write-Host ""

if ($ApicIP -ne "") {
    Write-Host "=== Configuration Reminder ===" -ForegroundColor Yellow
    Write-Host "Edit customer-config\inventory and update:" -ForegroundColor White
    Write-Host "- ansible_password (currently set to 'CHANGE_THIS_PASSWORD')" -ForegroundColor White
    Write-Host "- Add your spine and leaf switch IP addresses" -ForegroundColor White
    Write-Host ""
}

Write-Host "=== Quick Test Commands ===" -ForegroundColor Green
Write-Host "Once connected to container via VSCode:" -ForegroundColor White
Write-Host "  cp customer-config/inventory ./inventory" -ForegroundColor Cyan
Write-Host "  ./aci_maintenance.sh check" -ForegroundColor Cyan
Write-Host "  ansible all -i inventory -m ping" -ForegroundColor Cyan
Write-Host ""

Write-Host "Setup complete! 🚀" -ForegroundColor Green
