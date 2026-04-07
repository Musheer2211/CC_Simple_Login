#!/bin/bash

##############################################################################
# OAuth 2.0 Server - Linux Startup Script
# 
# This script starts the OAuth 2.0 Authorization Server on Linux
# Checks dependencies, creates virtual environment, and runs the server
##############################################################################

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV_DIR="$SCRIPT_DIR/venv"
PORT="${PORT:-8000}"
HOST="${HOST:-0.0.0.0}"
PYTHON_VERSION_REQUIRED="3.6"

##############################################################################
# Functions
##############################################################################

print_header() {
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}  OAuth 2.0 Server - Linux Startup Script${BLUE}                    ${NC}${BLUE}║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_info() {
    echo -e "${BLUE}ℹ${NC}  $1"
}

print_success() {
    echo -e "${GREEN}✓${NC}  $1"
}

print_error() {
    echo -e "${RED}✗${NC}  $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC}  $1"
}

check_python() {
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed"
        echo "  Please install Python 3.6 or higher:"
        echo "  Ubuntu/Debian: sudo apt-get install python3 python3-pip python3-venv"
        echo "  Fedora/RHEL:   sudo dnf install python3 python3-pip"
        echo "  macOS:         brew install python3"
        exit 1
    fi
    
    print_success "Python 3 found"
}

check_pip() {
    if ! command -v pip3 &> /dev/null; then
        print_error "pip3 is not installed"
        echo "  Please install pip3:"
        echo "  Ubuntu/Debian: sudo apt-get install python3-pip"
        echo "  Fedora/RHEL:   sudo dnf install python3-pip"
        echo "  macOS:         brew install python3"
        exit 1
    fi
    
    print_success "pip3 found"
}

create_venv() {
    if [ ! -d "$VENV_DIR" ]; then
        print_info "Creating Python virtual environment..."
        python3 -m venv "$VENV_DIR"
        print_success "Virtual environment created"
    else
        print_info "Using existing virtual environment"
    fi
}

activate_venv() {
    print_info "Activating virtual environment..."
    source "$VENV_DIR/bin/activate"
    print_success "Virtual environment activated"
}

install_dependencies() {
    print_info "Installing Python dependencies..."
    
    # Upgrade pip first
    pip install --upgrade pip setuptools wheel > /dev/null 2>&1
    
    # Install requirements
    if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
        pip install -r "$SCRIPT_DIR/requirements.txt"
        print_success "Dependencies installed"
    else
        print_error "requirements.txt not found in $SCRIPT_DIR"
        exit 1
    fi
}

verify_flask() {
    print_info "Verifying Flask installation..."
    python3 -c "import flask; from flask import Flask" 2>/dev/null
    if [ $? -eq 0 ]; then
        print_success "Flask is properly installed"
    else
        print_error "Flask verification failed"
        exit 1
    fi
}

##############################################################################
# Main Script
##############################################################################

main() {
    print_header
    
    # Check prerequisites
    print_info "Checking prerequisites..."
    check_python
    check_pip
    echo ""
    
    # Setup virtual environment
    print_info "Setting up virtual environment..."
    create_venv
    activate_venv
    echo ""
    
    # Install dependencies
    print_info "Installing dependencies..."
    install_dependencies
    echo ""
    
    # Verify installation
    print_info "Verifying installation..."
    verify_flask
    echo ""
    
    # Display configuration
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}  Server Configuration${BLUE}                                 ${NC}${BLUE}║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    print_info "Server Host:      $HOST"
    print_info "Server Port:      $PORT"
    print_info "Database:         users.db"
    print_info "Working Dir:      $SCRIPT_DIR"
    echo ""
    
    # Display next steps
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}  Starting OAuth 2.0 Server${BLUE}                           ${NC}${BLUE}║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    print_info "Server will start on http://$HOST:$PORT"
    echo ""
    print_success "All checks passed! Starting server..."
    echo ""
    
    # Start the server
    cd "$SCRIPT_DIR"
    python3 app.py
}

# Run main function
main "$@"
