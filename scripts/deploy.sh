#!/bin/bash

# WebSocket TUN VPN Deployment Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================${NC}"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

# Check system requirements
check_system() {
    print_header "Checking System Requirements"
    
    # Check OS
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        print_status "Linux detected"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        print_status "macOS detected"
    else
        print_error "Unsupported operating system: $OSTYPE"
        exit 1
    fi
    
    # Check Python
    if command -v python3 &> /dev/null; then
        print_status "Python 3 found: $(python3 --version)"
    else
        print_error "Python 3 is required but not installed"
        exit 1
    fi
    
    # Check pip
    if command -v pip3 &> /dev/null; then
        print_status "pip3 found"
    else
        print_error "pip3 is required but not installed"
        exit 1
    fi
    
    # Check TUN module (Linux only)
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if lsmod | grep -q tun; then
            print_status "TUN module is loaded"
        else
            print_warning "TUN module not loaded, attempting to load..."
            modprobe tun
            if lsmod | grep -q tun; then
                print_status "TUN module loaded successfully"
            else
                print_error "Failed to load TUN module"
                exit 1
            fi
        fi
    fi
}

# Install system dependencies
install_system_deps() {
    print_header "Installing System Dependencies"
    
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Detect Linux distribution
        if command -v apt-get &> /dev/null; then
            print_status "Installing dependencies for Ubuntu/Debian"
            apt-get update
            apt-get install -y python3 python3-pip python3-venv build-essential libssl-dev libffi-dev
        elif command -v yum &> /dev/null; then
            print_status "Installing dependencies for CentOS/RHEL"
            yum install -y python3 python3-pip gcc openssl-devel libffi-devel
        else
            print_error "Unsupported Linux distribution"
            exit 1
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        print_status "Installing dependencies for macOS"
        if command -v brew &> /dev/null; then
            brew install python3 openssl
        else
            print_error "Homebrew is required for macOS installation"
            print_status "Install Homebrew: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
            exit 1
        fi
    fi
}

# Install Python dependencies
install_python_deps() {
    print_header "Installing Python Dependencies"
    
    # Create virtual environment
    if [[ ! -d "venv" ]]; then
        print_status "Creating virtual environment"
        python3 -m venv venv
    fi
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Upgrade pip
    pip install --upgrade pip
    
    # Install server dependencies
    print_status "Installing server dependencies"
    pip install -r server/requirements.txt
    
    # Install client dependencies
    print_status "Installing client dependencies"
    pip install -r client/cli/requirements.txt
    
    print_status "Python dependencies installed successfully"
}

# Setup configuration
setup_config() {
    print_header "Setting Up Configuration"
    
    # Create necessary directories
    mkdir -p logs certs config
    
    # Copy configuration files if they don't exist
    if [[ ! -f "config/settings.json" ]]; then
        print_status "Creating default settings.json"
        cp config/settings.json.example config/settings.json 2>/dev/null || echo "{}" > config/settings.json
    fi
    
    if [[ ! -f "config/nodes.json" ]]; then
        print_status "Creating default nodes.json"
        cp config/nodes.json.example config/nodes.json 2>/dev/null || echo '{"nodes": []}' > config/nodes.json
    fi
    
    print_status "Configuration setup completed"
}

# Generate SSL certificates
generate_ssl_certs() {
    print_header "Generating SSL Certificates"
    
    if [[ ! -f "certs/server.crt" ]] || [[ ! -f "certs/server.key" ]]; then
        print_status "Generating self-signed SSL certificates"
        
        # Create certs directory
        mkdir -p certs
        
        # Generate private key
        openssl genrsa -out certs/server.key 2048
        
        # Generate certificate
        openssl req -new -x509 -key certs/server.key -out certs/server.crt -days 365 -subj "/C=US/ST=CA/L=San Francisco/O=WebSocket VPN/CN=localhost"
        
        print_status "SSL certificates generated successfully"
    else
        print_status "SSL certificates already exist"
    fi
}

# Setup systemd service (Linux only)
setup_systemd() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        print_header "Setting Up Systemd Service"
        
        # Create service file
        cat > /etc/systemd/system/websocket-vpn.service << EOF
[Unit]
Description=WebSocket TUN VPN Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$(pwd)
ExecStart=$(pwd)/venv/bin/python server/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
        
        # Reload systemd
        systemctl daemon-reload
        
        # Enable service
        systemctl enable websocket-vpn.service
        
        print_status "Systemd service created and enabled"
    fi
}

# Start services
start_services() {
    print_header "Starting Services"
    
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Start systemd service
        systemctl start websocket-vpn.service
        print_status "VPN server started via systemd"
    else
        # Start manually
        print_status "Starting VPN server manually"
        source venv/bin/activate
        python server/main.py &
        echo $! > vpn_server.pid
    fi
    
    print_status "Services started successfully"
}

# Show status
show_status() {
    print_header "Service Status"
    
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        systemctl status websocket-vpn.service --no-pager
    else
        if [[ -f "vpn_server.pid" ]]; then
            PID=$(cat vpn_server.pid)
            if ps -p $PID > /dev/null; then
                print_status "VPN server is running (PID: $PID)"
            else
                print_error "VPN server is not running"
            fi
        else
            print_error "VPN server is not running"
        fi
    fi
}

# Stop services
stop_services() {
    print_header "Stopping Services"
    
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        systemctl stop websocket-vpn.service
        print_status "VPN server stopped"
    else
        if [[ -f "vpn_server.pid" ]]; then
            PID=$(cat vpn_server.pid)
            kill $PID 2>/dev/null || true
            rm -f vpn_server.pid
            print_status "VPN server stopped"
        fi
    fi
}

# Main deployment function
deploy() {
    print_header "WebSocket TUN VPN Deployment"
    
    check_root
    check_system
    install_system_deps
    install_python_deps
    setup_config
    generate_ssl_certs
    setup_systemd
    start_services
    show_status
    
    print_header "Deployment Completed Successfully!"
    print_status "VPN server is now running"
    print_status "Use 'sudo python3 client/cli/client.py' to start the client"
}

# Usage function
usage() {
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  deploy    - Full deployment (default)"
    echo "  install   - Install dependencies only"
    echo "  start     - Start services"
    echo "  stop      - Stop services"
    echo "  status    - Show service status"
    echo "  help      - Show this help message"
    echo ""
}

# Main script logic
case "${1:-deploy}" in
    deploy)
        deploy
        ;;
    install)
        check_root
        check_system
        install_system_deps
        install_python_deps
        setup_config
        generate_ssl_certs
        setup_systemd
        ;;
    start)
        check_root
        start_services
        show_status
        ;;
    stop)
        check_root
        stop_services
        ;;
    status)
        show_status
        ;;
    help)
        usage
        ;;
    *)
        print_error "Unknown command: $1"
        usage
        exit 1
        ;;
esac