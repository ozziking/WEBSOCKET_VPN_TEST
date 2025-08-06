#!/usr/bin/env python3
"""
WebSocket VPN Server
Main server implementation with WebSocket support
"""

import asyncio
import json
import logging
import os
import ssl
import sys
from pathlib import Path
from typing import Dict, List, Optional

import websockets
from websockets.server import WebSocketServerProtocol

from config import Config
from tunnel import TunnelManager
from proxy import ProxyManager
from auth import AuthManager
from monitoring import MetricsCollector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/server.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class WebSocketVPNServer:
    """Main WebSocket VPN Server"""
    
    def __init__(self):
        self.config = Config()
        self.tunnel_manager = TunnelManager()
        self.proxy_manager = ProxyManager()
        self.auth_manager = AuthManager()
        self.metrics = MetricsCollector()
        self.clients: Dict[str, WebSocketServerProtocol] = {}
        self.ssl_context = None
        
        # Load SSL context if enabled
        if self.config.server.ssl.enabled:
            self.ssl_context = self._create_ssl_context()
    
    def _create_ssl_context(self) -> ssl.SSLContext:
        """Create SSL context for secure connections"""
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        
        cert_path = Path(self.config.server.ssl.cert)
        key_path = Path(self.config.server.ssl.key)
        
        if cert_path.exists() and key_path.exists():
            ssl_context.load_cert_chain(cert_path, key_path)
            logger.info("SSL context created successfully")
        else:
            logger.warning("SSL certificates not found, using self-signed")
            # Generate self-signed certificate for development
            self._generate_self_signed_cert()
            ssl_context.load_cert_chain(cert_path, key_path)
        
        return ssl_context
    
    def _generate_self_signed_cert(self):
        """Generate self-signed certificate for development"""
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        import datetime
        
        # Create certs directory
        Path("certs").mkdir(exist_ok=True)
        
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        
        # Create certificate
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "CA"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "WebSocket VPN"),
            x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
        ])
        
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.datetime.utcnow()
        ).not_valid_after(
            datetime.datetime.utcnow() + datetime.timedelta(days=365)
        ).add_extension(
            x509.SubjectAlternativeName([x509.DNSName("localhost")]),
            critical=False,
        ).sign(private_key, hashes.SHA256())
        
        # Write certificate and key
        with open("certs/server.crt", "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        
        with open("certs/server.key", "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
        
        logger.info("Self-signed certificate generated")
    
    async def handle_client(self, websocket: WebSocketServerProtocol, path: str):
        """Handle incoming WebSocket client connections"""
        client_id = None
        
        try:
            # Extract client information
            client_ip = websocket.remote_address[0]
            client_port = websocket.remote_address[1]
            client_id = f"{client_ip}:{client_port}"
            
            logger.info(f"New client connection: {client_id}")
            
            # Authenticate client
            if not await self.auth_manager.authenticate(websocket):
                logger.warning(f"Authentication failed for {client_id}")
                await websocket.close(1008, "Authentication failed")
                return
            
            # Register client
            self.clients[client_id] = websocket
            self.metrics.increment_connections()
            
            logger.info(f"Client {client_id} authenticated successfully")
            
            # Send welcome message
            welcome_msg = {
                "type": "welcome",
                "client_id": client_id,
                "server_info": {
                    "version": self.config.app.version,
                    "nodes": self.config.get_available_nodes()
                }
            }
            await websocket.send(json.dumps(welcome_msg))
            
            # Handle client messages
            async for message in websocket:
                try:
                    await self.handle_message(client_id, message)
                except Exception as e:
                    logger.error(f"Error handling message from {client_id}: {e}")
                    error_msg = {
                        "type": "error",
                        "message": str(e)
                    }
                    await websocket.send(json.dumps(error_msg))
        
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client {client_id} disconnected")
        except Exception as e:
            logger.error(f"Error handling client {client_id}: {e}")
        finally:
            # Cleanup
            if client_id and client_id in self.clients:
                del self.clients[client_id]
                self.metrics.decrement_connections()
            
            # Close tunnel if exists
            if client_id:
                await self.tunnel_manager.close_tunnel(client_id)
    
    async def handle_message(self, client_id: str, message: str):
        """Handle incoming messages from clients"""
        try:
            data = json.loads(message)
            msg_type = data.get("type")
            
            if msg_type == "tunnel_request":
                await self.handle_tunnel_request(client_id, data)
            elif msg_type == "tunnel_data":
                await self.handle_tunnel_data(client_id, data)
            elif msg_type == "ping":
                await self.handle_ping(client_id, data)
            elif msg_type == "node_select":
                await self.handle_node_select(client_id, data)
            else:
                logger.warning(f"Unknown message type: {msg_type}")
        
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON from client {client_id}")
        except Exception as e:
            logger.error(f"Error processing message from {client_id}: {e}")
    
    async def handle_tunnel_request(self, client_id: str, data: dict):
        """Handle tunnel creation request"""
        node_id = data.get("node_id")
        protocol = data.get("protocol", "tcp")
        
        try:
            tunnel = await self.tunnel_manager.create_tunnel(client_id, node_id, protocol)
            
            response = {
                "type": "tunnel_created",
                "tunnel_id": tunnel.id,
                "local_port": tunnel.local_port,
                "node_id": node_id
            }
            
            await self.clients[client_id].send(json.dumps(response))
            logger.info(f"Tunnel created for {client_id} to node {node_id}")
            
        except Exception as e:
            error_msg = {
                "type": "tunnel_error",
                "message": str(e)
            }
            await self.clients[client_id].send(json.dumps(error_msg))
            logger.error(f"Failed to create tunnel for {client_id}: {e}")
    
    async def handle_tunnel_data(self, client_id: str, data: dict):
        """Handle tunnel data transfer"""
        tunnel_id = data.get("tunnel_id")
        payload = data.get("payload")
        
        try:
            await self.tunnel_manager.forward_data(tunnel_id, payload)
            self.metrics.record_traffic(len(payload))
        except Exception as e:
            logger.error(f"Error forwarding tunnel data: {e}")
    
    async def handle_ping(self, client_id: str, data: dict):
        """Handle ping messages for keep-alive"""
        response = {
            "type": "pong",
            "timestamp": data.get("timestamp")
        }
        await self.clients[client_id].send(json.dumps(response))
    
    async def handle_node_select(self, client_id: str, data: dict):
        """Handle node selection request"""
        node_id = data.get("node_id")
        
        try:
            node = self.config.get_node(node_id)
            if node and node.get("enabled", True):
                response = {
                    "type": "node_selected",
                    "node_id": node_id,
                    "node_info": node
                }
                await self.clients[client_id].send(json.dumps(response))
                logger.info(f"Client {client_id} selected node {node_id}")
            else:
                error_msg = {
                    "type": "node_error",
                    "message": f"Node {node_id} not available"
                }
                await self.clients[client_id].send(json.dumps(error_msg))
        except Exception as e:
            logger.error(f"Error selecting node for {client_id}: {e}")
    
    async def start_server(self):
        """Start the WebSocket server"""
        try:
            # Create logs directory
            Path("logs").mkdir(exist_ok=True)
            
            # Start proxy manager
            await self.proxy_manager.start()
            
            # Start metrics collection
            await self.metrics.start()
            
            # Start WebSocket server
            server = await websockets.serve(
                self.handle_client,
                self.config.server.host,
                self.config.server.port,
                ssl=self.ssl_context
            )
            
            logger.info(f"WebSocket VPN Server started on {self.config.server.host}:{self.config.server.port}")
            logger.info(f"SSL enabled: {self.config.server.ssl.enabled}")
            
            # Keep server running
            await server.wait_closed()
            
        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            sys.exit(1)
    
    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("Shutting down server...")
        
        # Close all client connections
        for client_id, websocket in self.clients.items():
            try:
                await websocket.close()
            except Exception as e:
                logger.error(f"Error closing client {client_id}: {e}")
        
        # Stop proxy manager
        await self.proxy_manager.stop()
        
        # Stop metrics collection
        await self.metrics.stop()
        
        logger.info("Server shutdown complete")


async def main():
    """Main entry point"""
    server = WebSocketVPNServer()
    
    try:
        await server.start_server()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        await server.shutdown()


if __name__ == "__main__":
    asyncio.run(main())