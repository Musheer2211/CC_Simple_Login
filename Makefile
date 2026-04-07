# OAuth 2.0 Server - Makefile for Linux/macOS

.PHONY: help install run dev test clean lint format docs server stop

PYTHON := python3
PIP := pip3
VENV := venv
PORT ?= 8000

help:
	@echo "╔════════════════════════════════════════════════════════════╗"
	@echo "║         OAuth 2.0 Server - Available Commands             ║"
	@echo "╚════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make install       Install dependencies in virtual environment"
	@echo "  make venv          Create Python virtual environment"
	@echo "  make clean         Remove virtual environment"
	@echo ""
	@echo "Running the Server:"
	@echo "  make run           Start server (full setup)"
	@echo "  make dev           Start dev server (quick)"
	@echo "  make server        Start server (already installed)"
	@echo "  make stop          Stop server (if running)"
	@echo ""
	@echo "Testing:"
	@echo "  make test          Run test suite"
	@echo "  make test-curl     Show curl testing examples"
	@echo ""
	@echo "Development:"
	@echo "  make lint          Check code syntax"
	@echo "  make format        Format code (if formatter available)"
	@echo ""
	@echo "Utilities:"
	@echo "  make db-clean      Delete database (fresh start)"
	@echo "  make db-info       Show database info"
	@echo "  make docs          Show documentation"
	@echo "  make version       Show Python version"
	@echo ""
	@echo "Examples:"
	@echo "  make run           # Start server normally"
	@echo "  make run PORT=9000 # Start on custom port"
	@echo "  make test          # Run tests"
	@echo ""

# ============================================================================
# Setup & Installation
# ============================================================================

install: venv
	@echo "Installing dependencies..."
	@$(VENV)/bin/pip install -q -r requirements.txt
	@echo "✓ Dependencies installed"
	@echo ""

venv:
	@if [ ! -d "$(VENV)" ]; then \
		echo "Creating virtual environment..."; \
		$(PYTHON) -m venv $(VENV); \
		echo "✓ Virtual environment created"; \
	else \
		echo "Virtual environment already exists"; \
	fi
	@echo ""

clean:
	@echo "Removing virtual environment..."
	@rm -rf $(VENV)
	@echo "✓ Virtual environment removed"
	@echo ""

clean-all: clean
	@echo "Removing database..."
	@rm -f users.db
	@echo "✓ Database removed"
	@echo ""

# ============================================================================
# Running the Server
# ============================================================================

run: install
	@echo "╔════════════════════════════════════════════════════════════╗"
	@echo "║         Starting OAuth 2.0 Server                         ║"
	@echo "╚════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "Server: http://localhost:$(PORT)"
	@echo "Press Ctrl+C to stop"
	@echo ""
	@. $(VENV)/bin/activate && $(PYTHON) app.py

dev: venv
	@echo "Starting dev server..."
	@. $(VENV)/bin/activate && $(PYTHON) app.py

server: venv
	@echo "Starting server..."
	@. $(VENV)/bin/activate && $(PYTHON) app.py

stop:
	@echo "Stopping server..."
	@lsof -ti:$(PORT) | xargs kill -9 2>/dev/null || echo "No process on port $(PORT)"
	@echo "✓ Server stopped"

# ============================================================================
# Testing
# ============================================================================

test: venv
	@echo "Running test suite..."
	@echo ""
	@. $(VENV)/bin/activate && $(PYTHON) test_oauth.py

test-curl:
	@echo "OAuth 2.0 - curl Testing Examples"
	@echo ""
	@bash curl_examples.sh

# ============================================================================
# Development
# ============================================================================

lint:
	@echo "Checking Python syntax..."
	@$(PYTHON) -m py_compile app.py example_oauth_client.py test_oauth.py
	@echo "✓ All files have valid syntax"
	@echo ""

format:
	@echo "Checking for code formatter..."
	@if command -v black > /dev/null; then \
		echo "Formatting with black..."; \
		black app.py example_oauth_client.py test_oauth.py; \
		echo "✓ Code formatted"; \
	elif command -v autopep8 > /dev/null; then \
		echo "Formatting with autopep8..."; \
		autopep8 --in-place app.py example_oauth_client.py test_oauth.py; \
		echo "✓ Code formatted"; \
	else \
		echo "Install formatter: pip install black"; \
	fi
	@echo ""

# ============================================================================
# Database Management
# ============================================================================

db-clean:
	@echo "Deleting database..."
	@rm -f users.db
	@echo "✓ Database deleted (will be recreated on next run)"
	@echo ""

db-info:
	@echo "Database Information:"
	@echo "File: users.db"
	@if [ -f "users.db" ]; then \
		echo "Size: $$(du -h users.db | cut -f1)"; \
		echo "Last modified: $$(stat -f '%Sm' users.db 2>/dev/null || stat -c '%y' users.db)"; \
		echo ""; \
		echo "Tables:"; \
		sqlite3 users.db ".schema" 2>/dev/null | grep "CREATE TABLE" || echo "  (no tables yet)"; \
	else \
		echo "Database not found (will be created on first run)"; \
	fi
	@echo ""

# ============================================================================
# Documentation
# ============================================================================

docs:
	@echo "📚 Documentation Files:"
	@echo ""
	@echo "Getting Started:"
	@echo "  • START_HERE.txt - Quick overview"
	@echo "  • QUICKSTART.md - 5-minute setup"
	@echo "  • LINUX_SETUP.md - Linux-specific setup"
	@echo ""
	@echo "Technical Reference:"
	@echo "  • README.md - Full API documentation"
	@echo "  • ARCHITECTURE.md - System design & flows"
	@echo "  • IMPLEMENTATION_SUMMARY.md - Feature overview"
	@echo "  • INDEX.md - Documentation index"
	@echo ""
	@echo "Examples:"
	@echo "  • example_oauth_client.py - Working client app"
	@echo "  • curl_examples.sh - curl testing scripts"
	@echo ""

# ============================================================================
# Utilities
# ============================================================================

version:
	@echo "Python version:"
	@$(PYTHON) --version
	@echo ""
	@echo "pip version:"
	@$(PIP) --version
	@echo ""

check-deps:
	@echo "Checking dependencies..."
	@$(PYTHON) -c "import flask; print('✓ Flask'); import werkzeug; print('✓ Werkzeug')" 2>/dev/null || echo "✗ Dependencies not installed (run 'make install')"

status:
	@echo "OAuth 2.0 Server Status:"
	@echo ""
	@echo "Python: $$($(PYTHON) --version)"
	@echo "Virtual Env: $$([ -d $(VENV) ] && echo 'Yes' || echo 'No')"
	@echo "Dependencies: $$($(PYTHON) -c 'import flask' 2>/dev/null && echo 'Installed' || echo 'Not installed')"
	@echo "Database: $$([ -f users.db ] && echo 'Exists' || echo 'Not created')"
	@echo "Port $(PORT): $$(lsof -i :$(PORT) > /dev/null 2>&1 && echo 'In use' || echo 'Available')"
	@echo ""

# ============================================================================
# Development Helpers
# ============================================================================

logs:
	@echo "Starting server with logging..."
	@. $(VENV)/bin/activate && $(PYTHON) -u app.py

shell:
	@echo "Starting Python shell with Flask app..."
	@. $(VENV)/bin/activate && $(PYTHON)

repl:
	@echo "Starting interactive OAuth client..."
	@. $(VENV)/bin/activate && $(PYTHON) -i example_oauth_client.py

# ============================================================================
# Quick Commands
# ============================================================================

quick: clean-all install run

fresh: clean-all install dev

quick-test: venv test

.DEFAULT_GOAL := help
