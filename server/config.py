#!/usr/bin/env python3
"""
Configuration management for WebSocket VPN Server
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class SSLConfig:
    enabled: bool
    cert: str
    key: str


@dataclass
class AuthConfig:
    enabled: bool
    tokens: List[str]
    rate_limit: Dict[str, int]


@dataclass
class LoggingConfig:
    level: str
    file: str
    max_size: str
    backup_count: int


@dataclass
class ServerConfig:
    host: str
    port: int
    ssl: SSLConfig
    auth: AuthConfig
    logging: LoggingConfig


@dataclass
class AppConfig:
    name: str
    version: str
    description: str


class Config:
    """Configuration manager for the WebSocket VPN server"""
    
    def __init__(self, config_path: str = "../config/settings.json"):
        self.config_path = Path(config_path)
        self.nodes_path = Path("../config/nodes.json")
        
        # Load configuration
        self._load_config()
        self._load_nodes()
    
    def _load_config(self):
        """Load main configuration file"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
            else:
                # Use default configuration
                config_data = self._get_default_config()
            
            # Parse configuration
            self.app = AppConfig(**config_data.get("app", {}))
            
            server_data = config_data.get("server", {})
            self.server = ServerConfig(
                host=server_data.get("host", "0.0.0.0"),
                port=server_data.get("port", 8080),
                ssl=SSLConfig(**server_data.get("ssl", {})),
                auth=AuthConfig(**server_data.get("auth", {})),
                logging=LoggingConfig(**server_data.get("logging", {}))
            )
            
            # Store other configurations
            self.client = config_data.get("client", {})
            self.tunnel = config_data.get("tunnel", {})
            self.proxy = config_data.get("proxy", {})
            self.monitoring = config_data.get("monitoring", {})
            
        except Exception as e:
            print(f"Error loading configuration: {e}")
            # Use default configuration
            self._load_default_config()
    
    def _load_nodes(self):
        """Load nodes configuration"""
        try:
            if self.nodes_path.exists():
                with open(self.nodes_path, 'r', encoding='utf-8') as f:
                    nodes_data = json.load(f)
                    self.nodes = nodes_data.get("nodes", [])
                    self.node_settings = nodes_data.get("settings", {})
            else:
                self.nodes = []
                self.node_settings = {}
        except Exception as e:
            print(f"Error loading nodes configuration: {e}")
            self.nodes = []
            self.node_settings = {}
    
    def _load_default_config(self):
        """Load default configuration"""
        self.app = AppConfig(
            name="WebSocket VPN",
            version="1.0.0",
            description="A WebSocket-based VPN solution"
        )
        
        self.server = ServerConfig(
            host="0.0.0.0",
            port=8080,
            ssl=SSLConfig(
                enabled=True,
                cert="certs/server.crt",
                key="certs/server.key"
            ),
            auth=AuthConfig(
                enabled=True,
                tokens=["your-secret-token-here"],
                rate_limit={"requests": 100, "window": 60}
            ),
            logging=LoggingConfig(
                level="INFO",
                file="logs/server.log",
                max_size="10MB",
                backup_count=5
            )
        )
        
        self.client = {
            "auto_reconnect": True,
            "reconnect_interval": 5000,
            "connection_timeout": 10000,
            "max_retries": 3,
            "heartbeat_interval": 30000
        }
        
        self.tunnel = {
            "buffer_size": 8192,
            "compression": True,
            "encryption": {
                "enabled": True,
                "algorithm": "AES-256-GCM"
            }
        }
        
        self.proxy = {
            "enabled": True,
            "port": 1080,
            "socks5": {"enabled": True, "port": 1080},
            "http": {"enabled": True, "port": 8080}
        }
        
        self.monitoring = {
            "enabled": True,
            "metrics": {
                "traffic": True,
                "latency": True,
                "errors": True
            },
            "dashboard": {
                "enabled": True,
                "port": 3001
            }
        }
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            "app": {
                "name": "WebSocket VPN",
                "version": "1.0.0",
                "description": "A WebSocket-based VPN solution"
            },
            "server": {
                "host": "0.0.0.0",
                "port": 8080,
                "ssl": {
                    "enabled": True,
                    "cert": "certs/server.crt",
                    "key": "certs/server.key"
                },
                "auth": {
                    "enabled": True,
                    "tokens": ["your-secret-token-here"],
                    "rate_limit": {
                        "requests": 100,
                        "window": 60
                    }
                },
                "logging": {
                    "level": "INFO",
                    "file": "logs/server.log",
                    "max_size": "10MB",
                    "backup_count": 5
                }
            },
            "client": {
                "auto_reconnect": True,
                "reconnect_interval": 5000,
                "connection_timeout": 10000,
                "max_retries": 3,
                "heartbeat_interval": 30000
            },
            "tunnel": {
                "buffer_size": 8192,
                "compression": True,
                "encryption": {
                    "enabled": True,
                    "algorithm": "AES-256-GCM"
                }
            },
            "proxy": {
                "enabled": True,
                "port": 1080,
                "socks5": {
                    "enabled": True,
                    "port": 1080
                },
                "http": {
                    "enabled": True,
                    "port": 8080
                }
            },
            "monitoring": {
                "enabled": True,
                "metrics": {
                    "traffic": True,
                    "latency": True,
                    "errors": True
                },
                "dashboard": {
                    "enabled": True,
                    "port": 3001
                }
            }
        }
    
    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get node configuration by ID"""
        for node in self.nodes:
            if node.get("id") == node_id:
                return node
        return None
    
    def get_available_nodes(self) -> List[Dict[str, Any]]:
        """Get list of available nodes"""
        return [node for node in self.nodes if node.get("enabled", True)]
    
    def get_nodes_by_location(self, location: str) -> List[Dict[str, Any]]:
        """Get nodes by location"""
        return [
            node for node in self.nodes 
            if node.get("location") == location and node.get("enabled", True)
        ]
    
    def get_primary_node(self) -> Optional[Dict[str, Any]]:
        """Get the primary node (highest priority)"""
        available_nodes = self.get_available_nodes()
        if not available_nodes:
            return None
        
        # Sort by priority (lower number = higher priority)
        available_nodes.sort(key=lambda x: x.get("priority", 999))
        return available_nodes[0]
    
    def save_config(self):
        """Save current configuration to file"""
        try:
            config_data = {
                "app": {
                    "name": self.app.name,
                    "version": self.app.version,
                    "description": self.app.description
                },
                "server": {
                    "host": self.server.host,
                    "port": self.server.port,
                    "ssl": {
                        "enabled": self.server.ssl.enabled,
                        "cert": self.server.ssl.cert,
                        "key": self.server.ssl.key
                    },
                    "auth": {
                        "enabled": self.server.auth.enabled,
                        "tokens": self.server.auth.tokens,
                        "rate_limit": self.server.auth.rate_limit
                    },
                    "logging": {
                        "level": self.server.logging.level,
                        "file": self.server.logging.file,
                        "max_size": self.server.logging.max_size,
                        "backup_count": self.server.logging.backup_count
                    }
                },
                "client": self.client,
                "tunnel": self.tunnel,
                "proxy": self.proxy,
                "monitoring": self.monitoring
            }
            
            # Ensure directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            print(f"Configuration saved to {self.config_path}")
            
        except Exception as e:
            print(f"Error saving configuration: {e}")
    
    def add_node(self, node_config: Dict[str, Any]):
        """Add a new node to configuration"""
        self.nodes.append(node_config)
        self._save_nodes()
    
    def remove_node(self, node_id: str):
        """Remove a node from configuration"""
        self.nodes = [node for node in self.nodes if node.get("id") != node_id]
        self._save_nodes()
    
    def update_node(self, node_id: str, node_config: Dict[str, Any]):
        """Update an existing node"""
        for i, node in enumerate(self.nodes):
            if node.get("id") == node_id:
                self.nodes[i] = node_config
                break
        self._save_nodes()
    
    def _save_nodes(self):
        """Save nodes configuration"""
        try:
            nodes_data = {
                "nodes": self.nodes,
                "settings": self.node_settings
            }
            
            # Ensure directory exists
            self.nodes_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.nodes_path, 'w', encoding='utf-8') as f:
                json.dump(nodes_data, f, indent=2, ensure_ascii=False)
            
            print(f"Nodes configuration saved to {self.nodes_path}")
            
        except Exception as e:
            print(f"Error saving nodes configuration: {e}")


# Global configuration instance
config = Config()