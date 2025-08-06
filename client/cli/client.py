#!/usr/bin/env python3
"""
WebSocket TUN VPN CLI Client
"""

import asyncio
import argparse
import json
import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Dict, Optional, Any

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.text import Text

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

from server.tun_manager import TunManager, RouteManager, DnsManager
from server.websocket_tunnel import WebSocketTunnel, TunnelManager
from server.config import Config

console = Console()
logger = logging.getLogger(__name__)


class VPNClient:
    """WebSocket TUN VPN Client"""
    
    def __init__(self, config_path: str = "../config/settings.json"):
        self.config = Config(config_path)
        self.tun_manager = TunManager()
        self.route_manager = RouteManager()
        self.dns_manager = DnsManager()
        self.tunnel_manager = TunnelManager()
        self.websocket_tunnel: Optional[WebSocketTunnel] = None
        self.packet_processor = None
        self.running = False
        
        # Load client configuration
        self.client_config = self.config.client
        
    async def start(self, node_id: Optional[str] = None):
        """Start VPN client"""
        try:
            console.print("[bold green]Starting WebSocket TUN VPN Client...[/bold green]")
            
            # Check if running as root (required for TUN device)
            if os.geteuid() != 0:
                console.print("[bold red]Error: This application requires root privileges to create TUN devices.[/bold red]")
                console.print("Please run with sudo: sudo python3 client.py")
                return False
            
            # Get node configuration
            if node_id:
                node = self.config.get_node(node_id)
                if not node:
                    console.print(f"[bold red]Error: Node {node_id} not found[/bold red]")
                    return False
            else:
                node = self.config.get_primary_node()
                if not node:
                    console.print("[bold red]Error: No available nodes found[/bold red]")
                    return False
            
            console.print(f"[bold blue]Connecting to node: {node['name']} ({node['host']})[/bold blue]")
            
            # Create TUN device
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Creating TUN device...", total=None)
                
                tun_device = await self.tun_manager.create_tun_device(
                    "tun0",
                    "10.0.0.2",
                    "255.255.255.0"
                )
                
                if not tun_device:
                    console.print("[bold red]Failed to create TUN device[/bold red]")
                    return False
                
                progress.update(task, description="TUN device created successfully")
            
            # Save original network configuration
            self.route_manager.save_original_routes()
            self.dns_manager.save_original_dns()
            
            # Create WebSocket tunnel
            server_url = f"{node['protocol']}://{node['host']}:{node['port']}"
            auth_token = self.config.server.auth.tokens[0]  # Use first token
            
            self.websocket_tunnel = WebSocketTunnel(server_url, auth_token, tun_device)
            
            # Connect to server
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Connecting to VPN server...", total=None)
                
                if not await self.websocket_tunnel.connect():
                    console.print("[bold red]Failed to connect to VPN server[/bold red]")
                    return False
                
                progress.update(task, description="Connected to VPN server")
            
            # Configure routing
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Configuring network routing...", total=None)
                
                # Add VPN route
                self.route_manager.add_vpn_route("tun0", "10.0.0.1")
                
                # Set VPN DNS
                self.dns_manager.set_vpn_dns()
                
                progress.update(task, description="Network routing configured")
            
            # Start packet processing
            from server.tun_manager import PacketProcessor
            self.packet_processor = PacketProcessor(self.websocket_tunnel)
            self.tun_manager.set_packet_processor("tun0", self.packet_processor.process_packet)
            
            # Start packet processing
            asyncio.create_task(self.tun_manager.start_packet_processing())
            
            self.running = True
            console.print("[bold green]VPN client started successfully![/bold green]")
            
            # Show status
            await self.show_status()
            
            # Start monitoring
            await self.start_monitoring()
            
            return True
            
        except Exception as e:
            console.print(f"[bold red]Error starting VPN client: {e}[/bold red]")
            return False
    
    async def stop(self):
        """Stop VPN client"""
        try:
            console.print("[bold yellow]Stopping VPN client...[/bold yellow]")
            
            self.running = False
            
            # Stop packet processing
            self.tun_manager.stop_packet_processing()
            
            # Disconnect WebSocket tunnel
            if self.websocket_tunnel:
                await self.websocket_tunnel.disconnect()
            
            # Restore network configuration
            self.route_manager.remove_vpn_routes()
            self.dns_manager.restore_original_dns()
            
            console.print("[bold green]VPN client stopped successfully![/bold green]")
            
        except Exception as e:
            console.print(f"[bold red]Error stopping VPN client: {e}[/bold red]")
    
    async def show_status(self):
        """Show VPN status"""
        if not self.running:
            console.print("[bold red]VPN client is not running[/bold red]")
            return
        
        # Create status table
        table = Table(title="VPN Status")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")
        
        # Connection status
        if self.websocket_tunnel and self.websocket_tunnel.connected:
            table.add_row("Status", "Connected")
            table.add_row("Server", f"{self.websocket_tunnel.server_url}")
            table.add_row("Uptime", f"{self.websocket_tunnel.get_stats()['uptime']:.1f}s")
        else:
            table.add_row("Status", "Disconnected")
        
        # TUN device status
        tun_device = self.tun_manager.get_tun_device("tun0")
        if tun_device and tun_device.is_open:
            table.add_row("TUN Device", "Active")
        else:
            table.add_row("TUN Device", "Inactive")
        
        # Statistics
        if self.packet_processor:
            stats = self.packet_processor.get_stats()
            table.add_row("Packets Processed", str(stats['packet_count']))
            table.add_row("Bytes Processed", f"{stats['byte_count']:,}")
        
        console.print(table)
    
    async def show_nodes(self):
        """Show available nodes"""
        nodes = self.config.get_available_nodes()
        
        if not nodes:
            console.print("[bold red]No available nodes found[/bold red]")
            return
        
        table = Table(title="Available Nodes")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Location", style="yellow")
        table.add_column("Host", style="blue")
        table.add_column("Priority", style="magenta")
        
        for node in nodes:
            table.add_row(
                node['id'],
                node['name'],
                f"{node['country']}, {node['city']}",
                node['host'],
                str(node['priority'])
            )
        
        console.print(table)
    
    async def test_connection(self):
        """Test VPN connection"""
        if not self.running:
            console.print("[bold red]VPN client is not running[/bold red]")
            return
        
        console.print("[bold blue]Testing VPN connection...[/bold blue]")
        
        # Test basic connectivity
        try:
            import subprocess
            result = subprocess.run(
                ["ping", "-c", "3", "8.8.8.8"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                console.print("[bold green]✓ Basic connectivity test passed[/bold green]")
            else:
                console.print("[bold red]✗ Basic connectivity test failed[/bold red]")
                
        except Exception as e:
            console.print(f"[bold red]Error testing connectivity: {e}[/bold red]")
        
        # Test DNS resolution
        try:
            result = subprocess.run(
                ["nslookup", "google.com"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                console.print("[bold green]✓ DNS resolution test passed[/bold green]")
            else:
                console.print("[bold red]✗ DNS resolution test failed[/bold red]")
                
        except Exception as e:
            console.print(f"[bold red]Error testing DNS: {e}[/bold red]")
    
    async def start_monitoring(self):
        """Start monitoring loop"""
        while self.running:
            try:
                await asyncio.sleep(30)  # Update every 30 seconds
                
                # Send heartbeat
                if self.websocket_tunnel:
                    await self.websocket_tunnel.send_heartbeat()
                
                # Show status periodically
                if self.running:
                    console.print("\n[dim]VPN Status Update:[/dim]")
                    await self.show_status()
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        console.print("\n[bold yellow]Received shutdown signal...[/bold yellow]")
        asyncio.create_task(self.stop())
        sys.exit(0)


@click.command()
@click.option('--node', '-n', help='Node ID to connect to')
@click.option('--list-nodes', '-l', is_flag=True, help='List available nodes')
@click.option('--status', '-s', is_flag=True, help='Show VPN status')
@click.option('--test', '-t', is_flag=True, help='Test VPN connection')
@click.option('--config', '-c', default='../config/settings.json', help='Configuration file path')
def main(node, list_nodes, status, test, config):
    """WebSocket TUN VPN Client"""
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create client
    client = VPNClient(config)
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, client.signal_handler)
    signal.signal(signal.SIGTERM, client.signal_handler)
    
    async def run():
        try:
            if list_nodes:
                await client.show_nodes()
                return
            
            if status:
                await client.show_status()
                return
            
            if test:
                await client.test_connection()
                return
            
            # Start VPN client
            if await client.start(node):
                # Keep running until interrupted
                while client.running:
                    await asyncio.sleep(1)
            else:
                console.print("[bold red]Failed to start VPN client[/bold red]")
                sys.exit(1)
                
        except KeyboardInterrupt:
            console.print("\n[bold yellow]Interrupted by user[/bold yellow]")
        except Exception as e:
            console.print(f"[bold red]Error: {e}[/bold red]")
            sys.exit(1)
        finally:
            await client.stop()
    
    # Run the client
    asyncio.run(run())


if __name__ == "__main__":
    main()