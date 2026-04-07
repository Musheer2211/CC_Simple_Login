#!/bin/bash

##############################################################################
# OAuth 2.0 Server - Complete VM Setup Script
# 
# Works on COMPLETELY NEW Linux VMs with NO prerequisites installed
# Detects OS and installs everything needed, then starts the server
# 
# Supported: Ubuntu, Debian, Fedora, CentOS, RHEL, Amazon Linux, Alpine
##############################################################################

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV_DIR="$SCRIPT_DIR/venv"
PORT="${PORT:-8000}"

##############################################################################
# Functions
##############################################################################

print_header() {
    echo -e "${BLUE}"
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║   OAuth 2.0 Server - Complete VM Setup Script             ║"
    echo "║   (Works on brand new Linux VMs)                          ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_section() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ${NC}  $1"
}

print_success() {
    echo -e "${GREEN}✓${NC}  $1"
}

print_error() {
    echo -e "${RED}✗${NC}  $1"
    exit 1
}

print_warning() {
    echo -e "${YELLOW}⚠${NC}  $1"
}

# Detect Linux distribution
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        VER=$VERSION_ID
    elif type lsb_release >/dev/null 2>&1; then
        OS=$(lsb_release -si)
        VER=$(lsb_release -sr)
    elif [ -f /etc/lsb-release ]; then
        . /etc/lsb-release
        OS=$(echo $DISTRIB_ID | tr '[:upper:]' '[:lower:]')
        VER=$DISTRIB_RELEASE
    else
        OS=$(uname -s)
        VER=$(uname -r)
    fi
    
    # Normalize OS names
    case "$OS" in
        ubuntu|debian)
            OS="debian"
            ;;
        fedora|rhel|centos|rocky|almalinux)
            OS="fedora"
            ;;
        amzn)
            OS="amazon"
            ;;
        alpine)
            OS="alpine"
            ;;
        *)
            OS="${OS,,}"
            ;;
    esac
    
    print_info "Detected: $OS (version: $VER)"
}

# Install dependencies based on OS
install_dependencies() {
    print_section "Installing System Dependencies"
    
    case "$OS" in
        debian)
            print_info "Installing for Debian/Ubuntu..."
            sudo apt-get update > /dev/null 2>&1
            sudo apt-get install -y python3 python3-pip python3-venv > /dev/null 2>&1
            print_success "Dependencies installed (apt)"
            ;;
        
        fedora)
            print_info "Installing for Fedora/RHEL/CentOS..."
            sudo dnf install -y python3 python3-pip > /dev/null 2>&1 || \
            sudo yum install -y python3 python3-pip > /dev/null 2>&1
            print_success "Dependencies installed (dnf/yum)"
            ;;
        
        amazon)
            print_info "Installing for Amazon Linux..."
            sudo yum install -y python3 python3-pip > /dev/null 2>&1
            print_success "Dependencies installed (yum)"
            ;;
        
        alpine)
            print_info "Installing for Alpine..."
            apk update > /dev/null 2>&1
            apk add --no-cache python3 py3-pip > /dev/null 2>&1
            print_success "Dependencies installed (apk)"
            ;;
        
        *)
            print_error "Unsupported OS: $OS"
            echo "  Please install Python 3 manually and run: ./run.sh"
            exit 1
            ;;
    esac
}

# Verify Python installation
verify_python() {
    print_section "Verifying Python Installation"
    
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 installation failed or not found in PATH"
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    print_success "Python $PYTHON_VERSION found"
    
    if ! command -v pip3 &> /dev/null; then
        print_error "pip3 not found - installation may have failed"
        exit 1
    fi
    
    print_success "pip3 found"
}

# Setup virtual environment
setup_venv() {
    print_section "Setting Up Virtual Environment"
    
    if [ ! -d "$VENV_DIR" ]; then
        print_info "Creating Python virtual environment..."
        python3 -m venv "$VENV_DIR"
        print_success "Virtual environment created"
    else
        print_info "Using existing virtual environment"
    fi
    
    print_info "Activating virtual environment..."
    source "$VENV_DIR/bin/activate"
    print_success "Virtual environment activated"
}

# Install Python packages
install_packages() {
    print_section "Installing Python Packages"
    
    if [ ! -f "$SCRIPT_DIR/requirements.txt" ]; then
        print_error "requirements.txt not found in $SCRIPT_DIR"
        exit 1
    fi
    
    print_info "Upgrading pip..."
    pip install --quiet --upgrade pip setuptools wheel
    
    print_info "Installing Flask and dependencies..."
    pip install --quiet -r "$SCRIPT_DIR/requirements.txt"
    print_success "All packages installed"
}

# Verify Flask installation
verify_flask() {
    print_section "Verifying Installation"
    
    python3 -c "import flask; from werkzeug.security import generate_password_hash" 2>/dev/null
    if [ $? -eq 0 ]; then
        print_success "Flask and all dependencies verified"
    else
        print_error "Flask verification failed"
        exit 1
    fi
}

# Check if running as root
check_root() {
    if [ "$EUID" -eq 0 ]; then
        print_warning "Running as root - this is not recommended"
        print_warning "The server will run with reduced privileges where possible"
    fi
}

##############################################################################
# Main Script
##############################################################################

main() {
    print_header
    
    # Check if we need sudo
    check_root
    
    # Detect OS
    print_section "Detecting Operating System"
    detect_os
    
    # Install system dependencies
    install_dependencies
    
    # Verify Python
    verify_python
    
    # Setup virtual environment
    setup_venv
    
    # Install Python packages
    install_packages
    
    # Verify everything works
    verify_flask
    
    # Display configuration
    print_section "Server Configuration"
    echo ""
    print_info "Host:        $PORT"
    print_info "Port:        $PORT"
    print_info "Database:    users.db"
    print_info "Working Dir: $SCRIPT_DIR"
    print_info "Python:      $(python3 --version 2>&1)"
    echo ""
    
    # Display next steps
    print_section "Setup Complete! Starting Server"
    echo ""
    print_success "All prerequisites installed"
    print_success "All dependencies configured"
    print_success "Server ready to start!"
    echo ""
    print_info "Access the server at:"
    print_info "  → http://localhost:$PORT"
    print_info "  → Register: http://localhost:$PORT/register"
    print_info "  → Login: http://localhost:$PORT/login"
    print_info "  → Admin: http://localhost:$PORT/admin/clients"
    echo ""
    print_info "Press Ctrl+C to stop the server"
    echo ""
    echo -e "${GREEN}Starting OAuth 2.0 Server...${NC}"
    echo ""
    
    # Start the server
    cd "$SCRIPT_DIR"
    python3 app.py
}

# Error handling
trap 'print_error "Setup failed. Please check the output above."' ERR

# Run main function
main "$@"
