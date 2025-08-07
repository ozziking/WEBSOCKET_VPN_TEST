#!/usr/bin/env python3
"""
WebSocket tunnel for TUN VPN
Handles packet tunneling through WebSocket connection
"""

import asyncio
import base64
import json
import logging
import struct
import time
from typing import Dict, Optional, Any
import websockets
from websockets.client import WebSocketClientProtocol

logger = logging.getLogger(__name__)


class WebSocketTunnel:
    """WebSocket tunnel for TUN VPN"""
    
    def __init__(self, server_url: str, auth_token: str, tun_device=None):
        self.server_url = server_url
        self.auth_token = auth_token
        self.tun_device = tun_device
        self.websocket: Optional[WebSocketClientProtocol] = None
        self.connected = False
        self.reconnect_interval = 5
        self.max_reconnect_attempts = 10
        self.reconnect_attempts = 0
        
        # Statistics
        self.packets_sent = 0
        self.packets_received = 0
        self.bytes_sent = 0
        self.bytes_received = 0
        self.connection_start_time = None
        
    async def connect(self) -> bool:
        """Connect to WebSocket server"""
        try:
            # Prepare connection headers
            headers = {
                "Authorization": f"Bearer {self.auth_token}",
                "X-Auth-Token": self.auth_token,
                "User-Agent": "WebSocket-TUN-VPN/1.0"
            }
            
            # Connect to WebSocket server
            self.websocket = await websockets.connect(
                self.server_url,
                extra_headers=headers,
                ping_interval=30,
                ping_timeout=10,
                close_timeout=10
            )
            
            self.connected = True
            self.connection_start_time = time.time()
            self.reconnect_attempts = 0
            
            logger.info(f"Connected to WebSocket server: {self.server_url}")
            
            # Start message handling
            asyncio.create_task(self._handle_messages())
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to WebSocket server: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from WebSocket server"""
        self.connected = False
        
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception as e:
                logger.error(f"Error closing WebSocket connection: {e}")
            finally:
                self.websocket = None
    
    async def send_packet(self, packet: bytes) -> bool:
        """Send packet through WebSocket tunnel"""
        try:
            if not self.connected or not self.websocket:
                return False
            
            # Encode packet as base64
            encoded_packet = base64.b64encode(packet).decode('utf-8')
            
            # Create message
            message = {
                "type": "tunnel_data",
                "payload": encoded_packet,
                "timestamp": time.time(),
                "size": len(packet)
            }
            
            # Send message
            await self.websocket.send(json.dumps(message))
            
            # Update statistics
            self.packets_sent += 1
            self.bytes_sent += len(packet)
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending packet: {e}")
            return False
    
    async def _handle_messages(self):
        """Handle incoming WebSocket messages"""
        try:
            async for message in self.websocket:
                await self._process_message(message)
                
        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket connection closed")
            self.connected = False
            await self._handle_reconnect()
            
        except Exception as e:
            logger.error(f"Error handling WebSocket messages: {e}")
            self.connected = False
            await self._handle_reconnect()
    
    async def _process_message(self, message: str):
        """Process incoming message"""
        try:
            data = json.loads(message)
            msg_type = data.get("type")
            
            if msg_type == "tunnel_data":
                await self._handle_tunnel_data(data)
            elif msg_type == "ping":
                await self._handle_ping(data)
            elif msg_type == "pong":
                await self._handle_pong(data)
            elif msg_type == "error":
                logger.error(f"Server error: {data.get('message')}")
            else:
                logger.warning(f"Unknown message type: {msg_type}")
                
        except json.JSONDecodeError:
            logger.error("Invalid JSON message received")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    async def _handle_tunnel_data(self, data: Dict[str, Any]):
        """Handle tunnel data from server"""
        try:
            payload = data.get("payload")
            if not payload:
                return
            
            # Decode packet
            packet = base64.b64decode(payload)
            
            # Inject packet into TUN device
            if self.tun_device:
                self.tun_device.write_packet(packet)
                
                # Update statistics
                self.packets_received += 1
                self.bytes_received += len(packet)
                
        except Exception as e:
            logger.error(f"Error handling tunnel data: {e}")
    
    async def _handle_ping(self, data: Dict[str, Any]):
        """Handle ping message"""
        try:
            response = {
                "type": "pong",
                "timestamp": data.get("timestamp"),
                "client_timestamp": time.time()
            }
            await self.websocket.send(json.dumps(response))
            
        except Exception as e:
            logger.error(f"Error handling ping: {e}")
    
    async def _handle_pong(self, data: Dict[str, Any]):
        """Handle pong message"""
        # Calculate latency
        server_timestamp = data.get("timestamp", 0)
        client_timestamp = data.get("client_timestamp", 0)
        latency = (time.time() - client_timestamp) * 1000  # Convert to milliseconds
        
        logger.debug(f"Ping latency: {latency:.2f}ms")
    
    async def _handle_reconnect(self):
        """Handle reconnection"""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error("Max reconnection attempts reached")
            return
        
        self.reconnect_attempts += 1
        logger.info(f"Attempting to reconnect (attempt {self.reconnect_attempts}/{self.max_reconnect_attempts})")
        
        await asyncio.sleep(self.reconnect_interval)
        
        if await self.connect():
            logger.info("Reconnection successful")
        else:
            # Schedule next reconnection attempt
            asyncio.create_task(self._handle_reconnect())
    
    async def send_heartbeat(self):
        """Send heartbeat to keep connection alive"""
        try:
            if self.connected and self.websocket:
                message = {
                    "type": "ping",
                    "timestamp": time.time(),
                    "stats": self.get_stats()
                }
                await self.websocket.send(json.dumps(message))
                
        except Exception as e:
            logger.error(f"Error sending heartbeat: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get tunnel statistics"""
        uptime = 0
        if self.connection_start_time:
            uptime = time.time() - self.connection_start_time
        
        return {
            "connected": self.connected,
            "uptime": uptime,
            "packets_sent": self.packets_sent,
            "packets_received": self.packets_received,
            "bytes_sent": self.bytes_sent,
            "bytes_received": self.bytes_received,
            "reconnect_attempts": self.reconnect_attempts
        }


class TunnelManager:
    """Manage multiple WebSocket tunnels"""
    
    def __init__(self):
        self.tunnels: Dict[str, WebSocketTunnel] = {}
        self.active_tunnel: Optional[WebSocketTunnel] = None
        
    async def create_tunnel(self, tunnel_id: str, server_url: str, 
                           auth_token: str, tun_device=None) -> WebSocketTunnel:
        """Create a new WebSocket tunnel"""
        tunnel = WebSocketTunnel(server_url, auth_token, tun_device)
        self.tunnels[tunnel_id] = tunnel
        
        # Connect to server
        if await tunnel.connect():
            if not self.active_tunnel:
                self.active_tunnel = tunnel
            logger.info(f"Tunnel {tunnel_id} created and connected")
        else:
            logger.error(f"Failed to connect tunnel {tunnel_id}")
        
        return tunnel
    
    async def switch_tunnel(self, tunnel_id: str) -> bool:
        """Switch to a different tunnel"""
        if tunnel_id not in self.tunnels:
            logger.error(f"Tunnel {tunnel_id} not found")
            return False
        
        # Disconnect current tunnel
        if self.active_tunnel:
            await self.active_tunnel.disconnect()
        
        # Switch to new tunnel
        self.active_tunnel = self.tunnels[tunnel_id]
        
        # Reconnect if needed
        if not self.active_tunnel.connected:
            await self.active_tunnel.connect()
        
        logger.info(f"Switched to tunnel {tunnel_id}")
        return True
    
    async def close_tunnel(self, tunnel_id: str):
        """Close a tunnel"""
        if tunnel_id in self.tunnels:
            tunnel = self.tunnels[tunnel_id]
            await tunnel.disconnect()
            del self.tunnels[tunnel_id]
            
            if self.active_tunnel == tunnel:
                self.active_tunnel = None
            
            logger.info(f"Tunnel {tunnel_id} closed")
    
    async def close_all_tunnels(self):
        """Close all tunnels"""
        for tunnel_id in list(self.tunnels.keys()):
            await self.close_tunnel(tunnel_id)
    
    def get_active_tunnel(self) -> Optional[WebSocketTunnel]:
        """Get active tunnel"""
        return self.active_tunnel
    
    def get_tunnel_stats(self) -> Dict[str, Any]:
        """Get statistics for all tunnels"""
        stats = {
            "total_tunnels": len(self.tunnels),
            "active_tunnel": None,
            "tunnels": {}
        }
        
        for tunnel_id, tunnel in self.tunnels.items():
            stats["tunnels"][tunnel_id] = tunnel.get_stats()
            if tunnel == self.active_tunnel:
                stats["active_tunnel"] = tunnel_id
        
        return stats


class PacketTunnel:
    """Tunnel packets between TUN device and WebSocket"""
    
    def __init__(self, tun_device, websocket_tunnel):
        self.tun_device = tun_device
        self.websocket_tunnel = websocket_tunnel
        self.running = False
        
    async def start(self):
        """Start packet tunneling"""
        self.running = True
        
        # Start packet reading from TUN device
        asyncio.create_task(self._tun_to_websocket())
        
        logger.info("Packet tunneling started")
    
    async def stop(self):
        """Stop packet tunneling"""
        self.running = False
        logger.info("Packet tunneling stopped")
    
    async def _tun_to_websocket(self):
        """Forward packets from TUN device to WebSocket"""
        while self.running:
            try:
                # This would read packets from TUN device
                # and send them through WebSocket tunnel
                await asyncio.sleep(0.001)  # Small delay to prevent busy waiting
                
            except Exception as e:
                logger.error(f"Error in TUN to WebSocket forwarding: {e}")
                await asyncio.sleep(0.1)
    
    async def websocket_to_tun(self, packet: bytes):
        """Forward packet from WebSocket to TUN device"""
        try:
            if self.tun_device and self.running:
                self.tun_device.write_packet(packet)
                
        except Exception as e:
            logger.error(f"Error in WebSocket to TUN forwarding: {e}")