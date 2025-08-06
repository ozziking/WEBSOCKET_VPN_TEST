#!/usr/bin/env python3
"""
TUN device management for WebSocket VPN
Handles TUN interface creation and packet processing
"""

import asyncio
import fcntl
import logging
import os
import socket
import struct
import threading
import time
from typing import Dict, Optional, Callable
import select

# TUN/TAP constants
TUNSETIFF = 0x400454ca
IFF_TUN = 0x0001
IFF_NO_PI = 0x1000

logger = logging.getLogger(__name__)


class TunDevice:
    """TUN device wrapper"""
    
    def __init__(self, interface_name: str = "tun0", mtu: int = 1500):
        self.interface_name = interface_name
        self.mtu = mtu
        self.fd = None
        self.is_open = False
        self.packet_handler: Optional[Callable] = None
        
    def create(self) -> bool:
        """Create TUN device"""
        try:
            # Open TUN device
            self.fd = os.open("/dev/net/tun", os.O_RDWR)
            
            # Configure TUN interface
            ifr = struct.pack("16sH", self.interface_name.encode(), IFF_TUN | IFF_NO_PI)
            fcntl.ioctl(self.fd, TUNSETIFF, ifr)
            
            # Set non-blocking mode
            fcntl.fcntl(self.fd, fcntl.F_SETFL, os.O_NONBLOCK)
            
            self.is_open = True
            logger.info(f"TUN device {self.interface_name} created successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create TUN device: {e}")
            return False
    
    def configure_interface(self, ip_address: str, netmask: str = "255.255.255.0"):
        """Configure TUN interface with IP address"""
        try:
            # Bring interface up
            os.system(f"ip link set {self.interface_name} up")
            
            # Set IP address
            os.system(f"ip addr add {ip_address}/{netmask} dev {self.interface_name}")
            
            # Set MTU
            os.system(f"ip link set {self.interface_name} mtu {self.mtu}")
            
            logger.info(f"TUN interface {self.interface_name} configured with IP {ip_address}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to configure TUN interface: {e}")
            return False
    
    def set_packet_handler(self, handler: Callable):
        """Set packet handler callback"""
        self.packet_handler = handler
    
    async def read_packets(self):
        """Read packets from TUN device"""
        while self.is_open:
            try:
                # Use select to check if data is available
                ready, _, _ = select.select([self.fd], [], [], 0.1)
                
                if ready:
                    packet = os.read(self.fd, self.mtu)
                    if packet and self.packet_handler:
                        await self.packet_handler(packet)
                else:
                    await asyncio.sleep(0.001)
                    
            except Exception as e:
                logger.error(f"Error reading from TUN device: {e}")
                await asyncio.sleep(0.1)
    
    def write_packet(self, packet: bytes) -> bool:
        """Write packet to TUN device"""
        try:
            if self.is_open:
                os.write(self.fd, packet)
                return True
        except Exception as e:
            logger.error(f"Error writing to TUN device: {e}")
        return False
    
    def close(self):
        """Close TUN device"""
        if self.fd:
            os.close(self.fd)
            self.fd = None
        self.is_open = False
        logger.info(f"TUN device {self.interface_name} closed")


class TunManager:
    """Manages TUN devices and packet processing"""
    
    def __init__(self):
        self.tun_devices: Dict[str, TunDevice] = {}
        self.running = False
        self.packet_processors: Dict[str, Callable] = {}
        
    async def create_tun_device(self, name: str, ip_address: str, 
                               netmask: str = "255.255.255.0", mtu: int = 1500) -> Optional[TunDevice]:
        """Create and configure a TUN device"""
        try:
            tun_device = TunDevice(name, mtu)
            
            if not tun_device.create():
                return None
            
            if not tun_device.configure_interface(ip_address, netmask):
                tun_device.close()
                return None
            
            self.tun_devices[name] = tun_device
            logger.info(f"TUN device {name} created and configured")
            
            return tun_device
            
        except Exception as e:
            logger.error(f"Failed to create TUN device {name}: {e}")
            return None
    
    def set_packet_processor(self, tun_name: str, processor: Callable):
        """Set packet processor for TUN device"""
        if tun_name in self.tun_devices:
            self.tun_devices[tun_name].set_packet_handler(processor)
            self.packet_processors[tun_name] = processor
    
    async def start_packet_processing(self):
        """Start packet processing for all TUN devices"""
        self.running = True
        
        # Start packet reading tasks for all TUN devices
        tasks = []
        for tun_device in self.tun_devices.values():
            task = asyncio.create_task(tun_device.read_packets())
            tasks.append(task)
        
        # Wait for all tasks to complete
        await asyncio.gather(*tasks, return_exceptions=True)
    
    def stop_packet_processing(self):
        """Stop packet processing"""
        self.running = False
        
        # Close all TUN devices
        for tun_device in self.tun_devices.values():
            tun_device.close()
        
        self.tun_devices.clear()
        self.packet_processors.clear()
    
    def get_tun_device(self, name: str) -> Optional[TunDevice]:
        """Get TUN device by name"""
        return self.tun_devices.get(name)
    
    def list_tun_devices(self) -> list:
        """List all TUN devices"""
        return list(self.tun_devices.keys())
    
    def write_packet(self, tun_name: str, packet: bytes) -> bool:
        """Write packet to specific TUN device"""
        tun_device = self.get_tun_device(tun_name)
        if tun_device:
            return tun_device.write_packet(packet)
        return False


class PacketProcessor:
    """Process network packets"""
    
    def __init__(self, websocket_tunnel):
        self.websocket_tunnel = websocket_tunnel
        self.packet_count = 0
        self.byte_count = 0
    
    async def process_packet(self, packet: bytes):
        """Process incoming packet from TUN device"""
        try:
            self.packet_count += 1
            self.byte_count += len(packet)
            
            # Parse IP header
            if len(packet) < 20:  # Minimum IP header size
                return
            
            # Extract IP version
            version = (packet[0] >> 4) & 0x0F
            
            if version == 4:
                await self._process_ipv4_packet(packet)
            elif version == 6:
                await self._process_ipv6_packet(packet)
            else:
                logger.warning(f"Unknown IP version: {version}")
                
        except Exception as e:
            logger.error(f"Error processing packet: {e}")
    
    async def _process_ipv4_packet(self, packet: bytes):
        """Process IPv4 packet"""
        try:
            # Extract IP header fields
            header_length = (packet[0] & 0x0F) * 4
            total_length = struct.unpack('!H', packet[2:4])[0]
            protocol = packet[9]
            src_ip = socket.inet_ntoa(packet[12:16])
            dst_ip = socket.inet_ntoa(packet[16:20])
            
            logger.debug(f"IPv4 packet: {src_ip} -> {dst_ip}, protocol: {protocol}")
            
            # Send packet through WebSocket tunnel
            if self.websocket_tunnel:
                await self.websocket_tunnel.send_packet(packet)
                
        except Exception as e:
            logger.error(f"Error processing IPv4 packet: {e}")
    
    async def _process_ipv6_packet(self, packet: bytes):
        """Process IPv6 packet"""
        try:
            # Extract IPv6 header fields
            src_ip = socket.inet_ntop(socket.AF_INET6, packet[8:24])
            dst_ip = socket.inet_ntop(socket.AF_INET6, packet[24:40])
            next_header = packet[6]
            
            logger.debug(f"IPv6 packet: {src_ip} -> {dst_ip}, next_header: {next_header}")
            
            # Send packet through WebSocket tunnel
            if self.websocket_tunnel:
                await self.websocket_tunnel.send_packet(packet)
                
        except Exception as e:
            logger.error(f"Error processing IPv6 packet: {e}")
    
    def inject_packet(self, packet: bytes):
        """Inject packet into TUN device"""
        try:
            # This would be called by the WebSocket tunnel when receiving packets
            # from the remote server
            if self.websocket_tunnel and self.websocket_tunnel.tun_device:
                return self.websocket_tunnel.tun_device.write_packet(packet)
        except Exception as e:
            logger.error(f"Error injecting packet: {e}")
        return False
    
    def get_stats(self) -> Dict[str, int]:
        """Get packet processing statistics"""
        return {
            "packet_count": self.packet_count,
            "byte_count": self.byte_count
        }


class RouteManager:
    """Manage network routing"""
    
    def __init__(self):
        self.original_routes = []
        self.vpn_routes = []
    
    def save_original_routes(self):
        """Save original routing table"""
        try:
            # Get current routing table
            result = os.popen("ip route show").read()
            self.original_routes = result.strip().split('\n')
            logger.info("Original routes saved")
        except Exception as e:
            logger.error(f"Failed to save original routes: {e}")
    
    def add_vpn_route(self, interface: str, gateway: str, destination: str = "default"):
        """Add VPN route"""
        try:
            if destination == "default":
                cmd = f"ip route add default via {gateway} dev {interface}"
            else:
                cmd = f"ip route add {destination} via {gateway} dev {interface}"
            
            os.system(cmd)
            self.vpn_routes.append((interface, gateway, destination))
            logger.info(f"Added VPN route: {cmd}")
            
        except Exception as e:
            logger.error(f"Failed to add VPN route: {e}")
    
    def remove_vpn_routes(self):
        """Remove all VPN routes"""
        try:
            for interface, gateway, destination in self.vpn_routes:
                if destination == "default":
                    cmd = f"ip route del default via {gateway} dev {interface}"
                else:
                    cmd = f"ip route del {destination} via {gateway} dev {interface}"
                
                os.system(cmd)
                logger.info(f"Removed VPN route: {cmd}")
            
            self.vpn_routes.clear()
            
        except Exception as e:
            logger.error(f"Failed to remove VPN routes: {e}")
    
    def restore_original_routes(self):
        """Restore original routing table"""
        try:
            # This is a simplified implementation
            # In a real implementation, you would need to carefully restore routes
            logger.info("Original routes restored")
        except Exception as e:
            logger.error(f"Failed to restore original routes: {e}")


class DnsManager:
    """Manage DNS configuration"""
    
    def __init__(self):
        self.original_dns = []
        self.vpn_dns = ["8.8.8.8", "8.8.4.4"]  # Google DNS
    
    def save_original_dns(self):
        """Save original DNS configuration"""
        try:
            # Read current DNS configuration
            with open("/etc/resolv.conf", "r") as f:
                self.original_dns = f.readlines()
            logger.info("Original DNS configuration saved")
        except Exception as e:
            logger.error(f"Failed to save original DNS: {e}")
    
    def set_vpn_dns(self):
        """Set VPN DNS servers"""
        try:
            # Backup original resolv.conf
            os.system("cp /etc/resolv.conf /etc/resolv.conf.backup")
            
            # Create new resolv.conf
            with open("/etc/resolv.conf", "w") as f:
                f.write("# VPN DNS Configuration\n")
                for dns in self.vpn_dns:
                    f.write(f"nameserver {dns}\n")
            
            logger.info("VPN DNS servers configured")
            
        except Exception as e:
            logger.error(f"Failed to set VPN DNS: {e}")
    
    def restore_original_dns(self):
        """Restore original DNS configuration"""
        try:
            # Restore original resolv.conf
            os.system("cp /etc/resolv.conf.backup /etc/resolv.conf")
            logger.info("Original DNS configuration restored")
        except Exception as e:
            logger.error(f"Failed to restore original DNS: {e}")