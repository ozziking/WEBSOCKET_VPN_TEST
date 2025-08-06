#!/usr/bin/env python3
"""
Tunnel management for WebSocket VPN
Handles creation and management of VPN tunnels
"""

import asyncio
import base64
import json
import logging
import socket
import struct
import time
import uuid
from typing import Dict, Optional, Any
from dataclasses import dataclass
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


@dataclass
class Tunnel:
    """Tunnel configuration and state"""
    id: str
    client_id: str
    node_id: str
    protocol: str
    local_port: int
    remote_host: str
    remote_port: int
    created_at: float
    status: str = "created"
    bytes_sent: int = 0
    bytes_received: int = 0


class TunnelManager:
    """Manages VPN tunnels"""
    
    def __init__(self):
        self.tunnels: Dict[str, Tunnel] = {}
        self.encryption_key = self._generate_encryption_key()
        self.cipher = Fernet(self.encryption_key)
        self._next_port = 10000
        
    def _generate_encryption_key(self) -> bytes:
        """Generate encryption key for tunnel data"""
        # In production, this should be stored securely
        salt = b'websocket_vpn_salt'
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(b"websocket_vpn_secret"))
        return key
    
    def _get_next_port(self) -> int:
        """Get next available local port"""
        port = self._next_port
        self._next_port += 1
        if self._next_port > 20000:
            self._next_port = 10000
        return port
    
    async def create_tunnel(self, client_id: str, node_id: str, protocol: str = "tcp") -> Tunnel:
        """Create a new tunnel"""
        tunnel_id = str(uuid.uuid4())
        local_port = self._get_next_port()
        
        # Get node configuration
        from config import config
        node = config.get_node(node_id)
        if not node:
            raise ValueError(f"Node {node_id} not found")
        
        tunnel = Tunnel(
            id=tunnel_id,
            client_id=client_id,
            node_id=node_id,
            protocol=protocol,
            local_port=local_port,
            remote_host=node["host"],
            remote_port=node["port"],
            created_at=time.time()
        )
        
        self.tunnels[tunnel_id] = tunnel
        logger.info(f"Created tunnel {tunnel_id} for client {client_id} to node {node_id}")
        
        # Start tunnel processing
        asyncio.create_task(self._process_tunnel(tunnel))
        
        return tunnel
    
    async def close_tunnel(self, client_id: str):
        """Close tunnel for a client"""
        tunnels_to_close = [
            tunnel_id for tunnel_id, tunnel in self.tunnels.items()
            if tunnel.client_id == client_id
        ]
        
        for tunnel_id in tunnels_to_close:
            await self._close_tunnel(tunnel_id)
    
    async def _close_tunnel(self, tunnel_id: str):
        """Close a specific tunnel"""
        if tunnel_id in self.tunnels:
            tunnel = self.tunnels[tunnel_id]
            tunnel.status = "closed"
            del self.tunnels[tunnel_id]
            logger.info(f"Closed tunnel {tunnel_id}")
    
    async def forward_data(self, tunnel_id: str, payload: str):
        """Forward data through tunnel"""
        if tunnel_id not in self.tunnels:
            raise ValueError(f"Tunnel {tunnel_id} not found")
        
        tunnel = self.tunnels[tunnel_id]
        
        try:
            # Decode and decrypt payload
            encrypted_data = base64.b64decode(payload)
            decrypted_data = self.cipher.decrypt(encrypted_data)
            
            # Update tunnel statistics
            tunnel.bytes_received += len(decrypted_data)
            
            # Process the data (simplified - in real implementation, this would handle actual network traffic)
            await self._handle_tunnel_data(tunnel, decrypted_data)
            
        except Exception as e:
            logger.error(f"Error forwarding data through tunnel {tunnel_id}: {e}")
            raise
    
    async def _handle_tunnel_data(self, tunnel: Tunnel, data: bytes):
        """Handle tunnel data processing"""
        # This is a simplified implementation
        # In a real VPN, this would:
        # 1. Parse the data to determine destination
        # 2. Forward to the appropriate remote connection
        # 3. Handle responses and send back to client
        
        logger.debug(f"Processing {len(data)} bytes for tunnel {tunnel.id}")
        
        # Simulate processing delay
        await asyncio.sleep(0.001)
        
        # Update statistics
        tunnel.bytes_sent += len(data)
    
    async def _process_tunnel(self, tunnel: Tunnel):
        """Process tunnel data flow"""
        try:
            tunnel.status = "active"
            logger.info(f"Tunnel {tunnel.id} is now active")
            
            # Keep tunnel alive
            while tunnel.status == "active":
                await asyncio.sleep(1)
                
                # Check if tunnel should be closed
                if tunnel.id not in self.tunnels:
                    break
                
                # Send heartbeat
                await self._send_heartbeat(tunnel)
                
        except Exception as e:
            logger.error(f"Error processing tunnel {tunnel.id}: {e}")
            tunnel.status = "error"
        finally:
            await self._close_tunnel(tunnel.id)
    
    async def _send_heartbeat(self, tunnel: Tunnel):
        """Send heartbeat to keep tunnel alive"""
        heartbeat_data = {
            "type": "heartbeat",
            "tunnel_id": tunnel.id,
            "timestamp": time.time(),
            "stats": {
                "bytes_sent": tunnel.bytes_sent,
                "bytes_received": tunnel.bytes_received
            }
        }
        
        # In real implementation, this would be sent to the client
        logger.debug(f"Heartbeat for tunnel {tunnel.id}")
    
    def get_tunnel_stats(self, tunnel_id: str) -> Optional[Dict[str, Any]]:
        """Get tunnel statistics"""
        if tunnel_id not in self.tunnels:
            return None
        
        tunnel = self.tunnels[tunnel_id]
        return {
            "id": tunnel.id,
            "client_id": tunnel.client_id,
            "node_id": tunnel.node_id,
            "status": tunnel.status,
            "bytes_sent": tunnel.bytes_sent,
            "bytes_received": tunnel.bytes_received,
            "created_at": tunnel.created_at,
            "uptime": time.time() - tunnel.created_at
        }
    
    def get_all_tunnels(self) -> Dict[str, Dict[str, Any]]:
        """Get all tunnel statistics"""
        return {
            tunnel_id: self.get_tunnel_stats(tunnel_id)
            for tunnel_id in self.tunnels.keys()
        }
    
    def encrypt_data(self, data: bytes) -> str:
        """Encrypt data for transmission"""
        encrypted = self.cipher.encrypt(data)
        return base64.b64encode(encrypted).decode('utf-8')
    
    def decrypt_data(self, encrypted_data: str) -> bytes:
        """Decrypt received data"""
        encrypted_bytes = base64.b64decode(encrypted_data)
        return self.cipher.decrypt(encrypted_bytes)


class TunnelProtocol:
    """Protocol handler for different tunnel types"""
    
    @staticmethod
    async def handle_tcp_tunnel(tunnel: Tunnel, data: bytes):
        """Handle TCP tunnel data"""
        # TCP tunnel implementation
        pass
    
    @staticmethod
    async def handle_udp_tunnel(tunnel: Tunnel, data: bytes):
        """Handle UDP tunnel data"""
        # UDP tunnel implementation
        pass
    
    @staticmethod
    async def handle_socks5_tunnel(tunnel: Tunnel, data: bytes):
        """Handle SOCKS5 tunnel data"""
        # SOCKS5 tunnel implementation
        pass


class TunnelHealthChecker:
    """Health checker for tunnels"""
    
    def __init__(self, tunnel_manager: TunnelManager):
        self.tunnel_manager = tunnel_manager
        self.health_check_interval = 30  # seconds
    
    async def start_health_checks(self):
        """Start periodic health checks"""
        while True:
            await asyncio.sleep(self.health_check_interval)
            await self._check_all_tunnels()
    
    async def _check_all_tunnels(self):
        """Check health of all active tunnels"""
        for tunnel_id, tunnel in self.tunnel_manager.tunnels.items():
            if tunnel.status == "active":
                await self._check_tunnel_health(tunnel)
    
    async def _check_tunnel_health(self, tunnel: Tunnel):
        """Check health of a specific tunnel"""
        try:
            # Check if tunnel is responsive
            # In real implementation, this would send a ping and wait for response
            logger.debug(f"Health check for tunnel {tunnel.id}")
            
        except Exception as e:
            logger.warning(f"Tunnel {tunnel.id} health check failed: {e}")
            # Mark tunnel as unhealthy
            tunnel.status = "unhealthy"