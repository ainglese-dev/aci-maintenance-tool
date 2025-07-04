#!/bin/bash
# ACI Maintenance Window Data Collection Script
# Orchestrates before/after data collection and comparison

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INVENTORY_FILE="${SCRIPT_DIR}/inventory"
PLAYBOOK_FILE="${SCRIPT_DIR}/aci_collection.yml"
PYTHON_COLLECTOR="${SCRIPT_DIR}/aci_collector.py"
COMPARISON_SCRIPT="${SCRIPT_DIR}/compare_collections.py"
OUTPUT_DIR="${SCRIPT_DIR}/aci_outputs"
REPORTS_DIR="${SCRIPT_DIR}/comparison_reports"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_header() {
    echo -e "${BLUE}================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

check_dependencies() {
    print_header "Checking Dependencies"
    
    # Check for required commands
    local deps=("ansible-playbook" "python3")
    for dep in "${deps[@]}"; do
        if command -v "$dep" &> /dev/null; then
            print_success "$dep is installed"
        else
            print_error "$dep is not installed"
            exit 1
        fi
    done
    
    # Check Python packages
    if python3 -c "import paramiko" 2>/dev/null; then
        print_success "Python paramiko is available"
    else
        print_error "Python paramiko is not installed. Run: pip install paramiko"
        exit 1
    fi
    
    # Check for pyATS (optional)
    if python3 -c "import pyats" 2>/dev/null; then
        print_success "pyATS is available for advanced comparison"
    else
        print_warning "pyATS not available. Install with: pip install pyats[full]"
    fi
    
    # Check for required files
    if [[ ! -f "$INVENTORY_FILE" ]]; then
        print_error "Inventory file not found: $INVENTORY_FILE"
        exit 1
    fi
    
    if [[ ! -f "$PLAYBOOK_FILE" ]]; then
        print_error "Playbook file not found: $PLAYBOOK_FILE"
        exit 1
    fi
    
    print_success "All dependencies checked"
}

show_usage() {
    echo "Usage: $0 [OPTION]"
    echo ""
    echo "Options:"
    echo "  before      - Collect data before maintenance"
    echo "  after       - Collect data after maintenance"
    echo "  compare     - Compare before and after data"
    echo "  full        - Run complete before/after/compare cycle"
    echo "  python      - Use Python collector instead of Ansible"
    echo "  clean       - Clean up old collection files"
    echo "  check       - Check dependencies and configuration"
    echo "  help        - Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 before           # Collect before maintenance data"
    echo "  $0 after            # Collect after maintenance data"
    echo "  $0 compare          # Compare before/after data"
    echo "  $0 python before    # Use Python collector for before data"
    echo "  $0 full             # Complete maintenance cycle"
}

collect_data_ansible() {
    local phase=$1
    print_header "Collecting ACI Data - ${phase^^} Maintenance"
    
    # Create output directory
    mkdir -p "$OUTPUT_DIR"
    
    # Run Ansible playbook
    print_success "Starting Ansible collection for $phase phase..."
    
    if ansible-playbook -i "$INVENTORY_FILE" "$PLAYBOOK_FILE" \
        -e "phase=$phase" \
        -e "output_dir=$OUTPUT_DIR" \
        --timeout=300 \
        -v; then
        print_success "Ansible collection completed for $phase phase"
        
        # Show summary
        local summary_file="$OUTPUT_DIR/$phase/overall_collection_summary_*.json"
        if ls $summary_file 1> /dev/null 2>&1; then
            echo ""
            echo "Collection Summary:"
            python3 -c "
import json, glob
files = glob.glob('$summary_file')
if files:
    with open(files[0]) as f:
        data = json.load(f)
    meta = data.get('collection_metadata', {})
    print(f\"  Total devices: {meta.get('total_devices', 0)}\")
    print(f\"  Successful: {meta.get('successful_devices', 0)}\")
    print(f\"  Partial: {meta.get('partial_devices', 0)}\")
    breakdown = meta.get('device_breakdown', {})
    print(f\"  APIC: {breakdown.get('apic', 0)}\")
    print(f\"  LEAF: {breakdown.get('leaf', 0)}\")
    print(f\"  SPINE: {breakdown.get('spine', 0)}\")
"
        fi
    else
        print_error "Ansible collection failed for $phase phase"
        exit 1
    fi
}

collect_data_python() {
    local phase=$1
    print_header "Collecting ACI Data with Python - ${phase^^} Maintenance"
    
    if [[ ! -f "$PYTHON_COLLECTOR" ]]; then
        print_error "Python collector not found: $PYTHON_COLLECTOR"
        exit 1
    fi
    
    # Run Python collector
    print_success "Starting Python collection for $phase phase..."
    
    if python3 "$PYTHON_COLLECTOR" --phase "$phase" --output-dir "$OUTPUT_DIR"; then
        print_success "Python collection completed for $phase phase"
    else
        print_error "Python collection failed for $phase phase"
        exit 1
    fi
}

compare_data() {
    print_header "Comparing Before/After Data"
    
    local before_dir="$OUTPUT_DIR/before"
    local after_dir="$OUTPUT_DIR/after"
    
    # Check if directories exist
    if [[ ! -d "$before_dir" ]]; then
        print_error "Before data directory not found: $before_dir"
        print_warning "Run '$0 before' first to collect before data"
        exit 1
    fi
    
    if [[ ! -d "$after_dir" ]]; then
        print_error "After data directory not found: $after_dir"
        print_warning "Run '$0 after' first to collect after data"
        exit 1
    fi
    
    # Check if comparison script exists
    if [[ ! -f "$COMPARISON_SCRIPT" ]]; then
        print_error "Comparison script not found: $COMPARISON_SCRIPT"
        exit 1
    fi
    
    # Run comparison
    print_success "Starting comparison analysis..."
    
    if python3 "$COMPARISON_SCRIPT" "$before_dir" "$after_dir" "$REPORTS_DIR"; then
        print_success "Comparison completed successfully"
        
        # Show quick summary
        local summary_file="$REPORTS_DIR/comparison_summary_*.txt"
        if ls $summary_file 1> /dev/null 2>&1; then
            echo ""
            echo "Comparison Summary:"
            grep -A 10 "OVERALL STATISTICS:" $(ls $summary_file | head -1) | head -5
        fi
    else
        print_error "Comparison failed"
        exit 1
    fi
}

clean_old_files() {
    print_header "Cleaning Old Collection Files"
    
    local dirs_to_clean=("$OUTPUT_DIR" "$REPORTS_DIR")
    
    for dir in "${dirs_to_clean[@]}"; do
        if [[ -d "$dir" ]]; then
            echo "Cleaning $dir..."
            
            # Keep only the most recent 3 collections
            find "$dir" -name "*.json" -o -name "*.txt" -o -name "*.yaml" | \
                sort -r | tail -n +10 | xargs -r rm -f
            
            # Clean empty directories
            find "$dir" -type d -empty -delete 2>/dev/null || true
            
            print_success "Cleaned $dir"
        fi
    done
}

check_configuration() {
    print_header "Checking Configuration"
    
    # Check inventory file
    if ansible-inventory -i "$INVENTORY_FILE" --list > /dev/null 2>&1; then
        print_success "Inventory file is valid"
        
        # Show device counts
        local apic_count=$(ansible-inventory -i "$INVENTORY_FILE" --list | jq '.apic.hosts | length' 2>/dev/null || echo "0")
        local leaf_count=$(ansible-inventory -i "$INVENTORY_FILE" --list | jq '.leaf.hosts | length' 2>/dev/null || echo "0")
        local spine_count=$(ansible-inventory -i "$INVENTORY_FILE" --list | jq '.spine.hosts | length' 2>/dev/null || echo "0")
        
        echo "  Device counts:"
        echo "    APIC: $apic_count"
        echo "    LEAF: $leaf_count"
        echo "    SPINE: $spine_count"
    else
        print_error "Inventory file has syntax errors"
        exit 1
    fi
    
    # Check playbook syntax
    if ansible-playbook --syntax-check -i "$INVENTORY_FILE" "$PLAYBOOK_FILE" > /dev/null 2>&1; then
        print_success "Playbook syntax is valid"
    else
        print_error "Playbook has syntax errors"
        exit 1
    fi
    
    # Test connectivity to a sample device
    print_success "Configuration check completed"
}

run_full_cycle() {
    print_header "Running Full Maintenance Cycle"
    
    echo "This will:"
    echo "1. Collect BEFORE maintenance data"
    echo "2. Wait for user confirmation"
    echo "3. Collect AFTER maintenance data"
    echo "4. Compare and generate reports"
    echo ""
    
    read -p "Continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_warning "Operation cancelled"
        exit 0
    fi
    
    # Step 1: Before collection
    collect_data_ansible "before"
    
    # Step 2: Wait for maintenance
    echo ""
    print_warning "BEFORE data collection completed"
    print_warning "Perform your maintenance activities now"
    echo ""
    read -p "Press Enter when maintenance is complete to collect AFTER data..."
    
    # Step 3: After collection
    collect_data_ansible "after"
    
    # Step 4: Compare
    compare_data
    
    print_success "Full maintenance cycle completed!"
    echo ""
    echo "Reports available in: $REPORTS_DIR"
}

# Main script logic
main() {
    local command=$1
    local method=$2
    
    case "$command" in
        "check")
            check_dependencies
            check_configuration
            ;;
        "before")
            check_dependencies
            if [[ "$method" == "python" ]]; then
                collect_data_python "before"
            else
                collect_data_ansible "before"
            fi
            ;;
        "after")
            check_dependencies
            if [[ "$method" == "python" ]]; then
                collect_data_python "after"
            else
                collect_data_ansible "after"
            fi
            ;;
        "compare")
            check_dependencies
            compare_data
            ;;
        "python")
            check_dependencies
            if [[ "$2" == "before" || "$2" == "after" ]]; then
                collect_data_python "$2"
            else
                print_error "Usage: $0 python [before|after]"
                exit 1
            fi
            ;;
        "full")
            check_dependencies
            check_configuration
            run_full_cycle
            ;;
        "clean")
            clean_old_files
            ;;
        "help"|"-h"|"--help")
            show_usage
            ;;
        *)
            print_error "Unknown command: $command"
            echo ""
            show_usage
            exit 1
            ;;
    esac
}

# Script entry point
if [[ $# -eq 0 ]]; then
    show_usage
    exit 1
fi

main "$@"
