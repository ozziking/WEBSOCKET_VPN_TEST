#!/usr/bin/env python3
"""
Proxy management for WebSocket VPN
Handles SOCKS5 and HTTP proxy functionality
"""

import asyncio
import logging
import socket
import struct
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ProxyConnection:
    """Proxy connection state"""
    id: str
    client_socket: socket.socket
    remote_socket: Optional[socket.socket] = None
    protocol: str = "tcp"
    status: str = "connecting"


class ProxyManager:
    """Manages proxy connections"""
    
    def __init__(self):
        self.connections: Dict[str, ProxyConnection] = {}
        self.socks5_server = None
        self.http_server = None
        self._connection_id = 0
        
    async def start(self):
        """Start proxy servers"""
        try:
            from config import config
            
            if config.proxy.get("socks5", {}).get("enabled", False):
                await self._start_socks5_server()
            
            if config.proxy.get("http", {}).get("enabled", False):
                await self._start_http_server()
                
            logger.info("Proxy servers started")
            
        except Exception as e:
            logger.error(f"Failed to start proxy servers: {e}")
    
    async def stop(self):
        """Stop proxy servers"""
        try:
            # Close all connections
            for conn_id, connection in self.connections.items():
                await self._close_connection(conn_id)
            
            # Stop servers
            if self.socks5_server:
                self.socks5_server.close()
                await self.socks5_server.wait_closed()
            
            if self.http_server:
                self.http_server.close()
                await self.http_server.wait_closed()
                
            logger.info("Proxy servers stopped")
            
        except Exception as e:
            logger.error(f"Error stopping proxy servers: {e}")
    
    async def _start_socks5_server(self):
        """Start SOCKS5 proxy server"""
        from config import config
        
        port = config.proxy.get("socks5", {}).get("port", 1080)
        
        try:
            self.socks5_server = await asyncio.start_server(
                self._handle_socks5_connection,
                '127.0.0.1',
                port
            )
            
            logger.info(f"SOCKS5 proxy server started on port {port}")
            
        except Exception as e:
            logger.error(f"Failed to start SOCKS5 server: {e}")
    
    async def _start_http_server(self):
        """Start HTTP proxy server"""
        from config import config
        
        port = config.proxy.get("http", {}).get("port", 8080)
        
        try:
            self.http_server = await asyncio.start_server(
                self._handle_http_connection,
                '127.0.0.1',
                port
            )
            
            logger.info(f"HTTP proxy server started on port {port}")
            
        except Exception as e:
            logger.error(f"Failed to start HTTP server: {e}")
    
    async def _handle_socks5_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle SOCKS5 connection"""
        connection_id = f"socks5_{self._get_next_id()}"
        
        try:
            # SOCKS5 handshake
            version = await reader.read(1)
            if version != b'\x05':
                logger.warning("Invalid SOCKS5 version")
                return
            
            nmethods = await reader.read(1)
            methods = await reader.read(nmethods[0])
            
            # Send authentication method (no authentication)
            writer.write(b'\x05\x00')
            await writer.drain()
            
            # Get request
            version = await reader.read(1)
            cmd = await reader.read(1)
            rsv = await reader.read(1)
            atyp = await reader.read(1)
            
            if cmd != b'\x01':  # CONNECT command
                writer.write(b'\x05\x07\x00\x01\x00\x00\x00\x00\x00\x00')
                await writer.drain()
                return
            
            # Parse address
            if atyp == b'\x01':  # IPv4
                addr = await reader.read(4)
                port = await reader.read(2)
                target_addr = socket.inet_ntoa(addr)
                target_port = struct.unpack('>H', port)[0]
            elif atyp == b'\x03':  # Domain name
                length = await reader.read(1)
                domain = await reader.read(length[0])
                port = await reader.read(2)
                target_addr = domain.decode('utf-8')
                target_port = struct.unpack('>H', port)[0]
            else:
                writer.write(b'\x05\x08\x00\x01\x00\x00\x00\x00\x00\x00')
                await writer.drain()
                return
            
            # Create connection to target
            try:
                remote_reader, remote_writer = await asyncio.open_connection(target_addr, target_port)
                
                # Send success response
                writer.write(b'\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00')
                await writer.drain()
                
                # Create proxy connection
                connection = ProxyConnection(
                    id=connection_id,
                    client_socket=None,  # Not used in asyncio
                    protocol="tcp",
                    status="connected"
                )
                self.connections[connection_id] = connection
                
                # Start data forwarding
                await self._forward_data(connection_id, reader, writer, remote_reader, remote_writer)
                
            except Exception as e:
                logger.error(f"Failed to connect to target {target_addr}:{target_port}: {e}")
                writer.write(b'\x05\x04\x00\x01\x00\x00\x00\x00\x00\x00')
                await writer.drain()
                
        except Exception as e:
            logger.error(f"Error handling SOCKS5 connection: {e}")
        finally:
            await self._close_connection(connection_id)
    
    async def _handle_http_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle HTTP proxy connection"""
        connection_id = f"http_{self._get_next_id()}"
        
        try:
            # Read HTTP request line
            line = await reader.readline()
            if not line:
                return
            
            # Parse request
            parts = line.decode('utf-8').strip().split()
            if len(parts) < 3:
                return
            
            method, url, version = parts[0], parts[1], parts[2]
            
            if method == 'CONNECT':
                # Handle CONNECT method
                host, port = url.split(':', 1)
                port = int(port)
                
                try:
                    remote_reader, remote_writer = await asyncio.open_connection(host, port)
                    
                    # Send success response
                    writer.write(b'HTTP/1.1 200 Connection established\r\n\r\n')
                    await writer.drain()
                    
                    # Create proxy connection
                    connection = ProxyConnection(
                        id=connection_id,
                        client_socket=None,
                        protocol="http",
                        status="connected"
                    )
                    self.connections[connection_id] = connection
                    
                    # Start data forwarding
                    await self._forward_data(connection_id, reader, writer, remote_reader, remote_writer)
                    
                except Exception as e:
                    logger.error(f"Failed to connect to {host}:{port}: {e}")
                    writer.write(b'HTTP/1.1 502 Bad Gateway\r\n\r\n')
                    await writer.drain()
            else:
                # Handle GET/POST methods
                # This is a simplified implementation
                writer.write(b'HTTP/1.1 501 Not Implemented\r\n\r\n')
                await writer.drain()
                
        except Exception as e:
            logger.error(f"Error handling HTTP connection: {e}")
        finally:
            await self._close_connection(connection_id)
    
    async def _forward_data(self, connection_id: str, 
                          client_reader: asyncio.StreamReader, 
                          client_writer: asyncio.StreamWriter,
                          remote_reader: asyncio.StreamReader, 
                          remote_writer: asyncio.StreamWriter):
        """Forward data between client and remote"""
        try:
            # Create tasks for bidirectional forwarding
            client_to_remote = asyncio.create_task(
                self._forward_stream(client_reader, remote_writer, f"{connection_id}_client_to_remote")
            )
            remote_to_client = asyncio.create_task(
                self._forward_stream(remote_reader, client_writer, f"{connection_id}_remote_to_client")
            )
            
            # Wait for either direction to complete
            done, pending = await asyncio.wait(
                [client_to_remote, remote_to_client],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel remaining tasks
            for task in pending:
                task.cancel()
            
        except Exception as e:
            logger.error(f"Error in data forwarding for {connection_id}: {e}")
        finally:
            # Close connections
            client_writer.close()
            remote_writer.close()
            try:
                await client_writer.wait_closed()
                await remote_writer.wait_closed()
            except Exception:
                pass
    
    async def _forward_stream(self, reader: asyncio.StreamReader, 
                            writer: asyncio.StreamWriter, stream_id: str):
        """Forward data from reader to writer"""
        try:
            while True:
                data = await reader.read(8192)
                if not data:
                    break
                
                writer.write(data)
                await writer.drain()
                
        except Exception as e:
            logger.debug(f"Stream {stream_id} closed: {e}")
    
    async def _close_connection(self, connection_id: str):
        """Close a proxy connection"""
        if connection_id in self.connections:
            connection = self.connections[connection_id]
            connection.status = "closed"
            del self.connections[connection_id]
            logger.debug(f"Closed proxy connection {connection_id}")
    
    def _get_next_id(self) -> int:
        """Get next connection ID"""
        self._connection_id += 1
        return self._connection_id
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get proxy connection statistics"""
        return {
            "total_connections": len(self.connections),
            "active_connections": len([c for c in self.connections.values() if c.status == "connected"]),
            "connections_by_protocol": {
                "socks5": len([c for c in self.connections.values() if c.protocol == "socks5"]),
                "http": len([c for c in self.connections.values() if c.protocol == "http"])
            }
        }


class Socks5Protocol:
    """SOCKS5 protocol implementation"""
    
    @staticmethod
    async def handle_handshake(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> bool:
        """Handle SOCKS5 handshake"""
        try:
            # Read version and methods
            version = await reader.read(1)
            if version != b'\x05':
                return False
            
            nmethods = await reader.read(1)
            methods = await reader.read(nmethods[0])
            
            # Send response (no authentication)
            writer.write(b'\x05\x00')
            await writer.drain()
            
            return True
            
        except Exception as e:
            logger.error(f"SOCKS5 handshake failed: {e}")
            return False
    
    @staticmethod
    async def handle_request(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> Tuple[str, int]:
        """Handle SOCKS5 request and return target address and port"""
        try:
            # Read request
            version = await reader.read(1)
            cmd = await reader.read(1)
            rsv = await reader.read(1)
            atyp = await reader.read(1)
            
            if cmd != b'\x01':  # Only support CONNECT
                return None, None
            
            # Parse address
            if atyp == b'\x01':  # IPv4
                addr = await reader.read(4)
                port = await reader.read(2)
                target_addr = socket.inet_ntoa(addr)
                target_port = struct.unpack('>H', port)[0]
            elif atyp == b'\x03':  # Domain name
                length = await reader.read(1)
                domain = await reader.read(length[0])
                port = await reader.read(2)
                target_addr = domain.decode('utf-8')
                target_port = struct.unpack('>H', port)[0]
            else:
                return None, None
            
            return target_addr, target_port
            
        except Exception as e:
            logger.error(f"SOCKS5 request failed: {e}")
            return None, None


class HttpProxyProtocol:
    """HTTP proxy protocol implementation"""
    
    @staticmethod
    async def parse_request(reader: asyncio.StreamReader) -> Tuple[str, str, int]:
        """Parse HTTP proxy request"""
        try:
            line = await reader.readline()
            if not line:
                return None, None, None
            
            parts = line.decode('utf-8').strip().split()
            if len(parts) < 3:
                return None, None, None
            
            method, url, version = parts[0], parts[1], parts[2]
            
            if method == 'CONNECT':
                host, port = url.split(':', 1)
                return method, host, int(port)
            else:
                # Handle GET/POST requests
                from urllib.parse import urlparse
                parsed = urlparse(url)
                return method, parsed.hostname, parsed.port or 80
                
        except Exception as e:
            logger.error(f"HTTP request parsing failed: {e}")
            return None, None, None