#!/usr/bin/env python3
"""
Monitoring and metrics collection for WebSocket VPN
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from prometheus_client import Counter, Gauge, Histogram, start_http_server
import psutil

logger = logging.getLogger(__name__)


@dataclass
class MetricsData:
    """Metrics data structure"""
    timestamp: float
    connections: int
    tunnels: int
    bytes_sent: int
    bytes_received: int
    errors: int
    latency: float
    cpu_usage: float
    memory_usage: float


class MetricsCollector:
    """Collects and manages metrics"""
    
    def __init__(self):
        self.metrics_history: List[MetricsData] = []
        self.max_history_size = 1000
        self.collection_interval = 30  # seconds
        
        # Prometheus metrics
        self.connections_gauge = Gauge('vpn_connections', 'Number of active connections')
        self.tunnels_gauge = Gauge('vpn_tunnels', 'Number of active tunnels')
        self.bytes_sent_counter = Counter('vpn_bytes_sent', 'Total bytes sent')
        self.bytes_received_counter = Counter('vpn_bytes_received', 'Total bytes received')
        self.errors_counter = Counter('vpn_errors', 'Total errors')
        self.latency_histogram = Histogram('vpn_latency', 'Connection latency')
        
        # System metrics
        self.cpu_gauge = Gauge('vpn_cpu_usage', 'CPU usage percentage')
        self.memory_gauge = Gauge('vpn_memory_usage', 'Memory usage percentage')
        
        # Internal counters
        self._total_bytes_sent = 0
        self._total_bytes_received = 0
        self._total_errors = 0
        self._connection_count = 0
        self._tunnel_count = 0
        
        # Performance tracking
        self._last_collection = time.time()
        self._performance_data = {
            "avg_latency": 0.0,
            "min_latency": float('inf'),
            "max_latency": 0.0,
            "latency_samples": []
        }
    
    async def start(self):
        """Start metrics collection"""
        try:
            # Start Prometheus metrics server
            from config import config
            if config.monitoring.get("enabled", True):
                dashboard_port = config.monitoring.get("dashboard", {}).get("port", 3001)
                start_http_server(dashboard_port)
                logger.info(f"Metrics dashboard started on port {dashboard_port}")
            
            # Start collection task
            asyncio.create_task(self._collect_metrics())
            logger.info("Metrics collection started")
            
        except Exception as e:
            logger.error(f"Failed to start metrics collection: {e}")
    
    async def stop(self):
        """Stop metrics collection"""
        logger.info("Stopping metrics collection")
    
    async def _collect_metrics(self):
        """Periodically collect metrics"""
        while True:
            try:
                await self._update_metrics()
                await asyncio.sleep(self.collection_interval)
            except Exception as e:
                logger.error(f"Error collecting metrics: {e}")
                await asyncio.sleep(5)
    
    async def _update_metrics(self):
        """Update current metrics"""
        current_time = time.time()
        
        # Get system metrics
        cpu_usage = psutil.cpu_percent(interval=1)
        memory_usage = psutil.virtual_memory().percent
        
        # Calculate latency (simplified)
        latency = self._calculate_latency()
        
        # Create metrics data
        metrics_data = MetricsData(
            timestamp=current_time,
            connections=self._connection_count,
            tunnels=self._tunnel_count,
            bytes_sent=self._total_bytes_sent,
            bytes_received=self._total_bytes_received,
            errors=self._total_errors,
            latency=latency,
            cpu_usage=cpu_usage,
            memory_usage=memory_usage
        )
        
        # Store metrics
        self.metrics_history.append(metrics_data)
        if len(self.metrics_history) > self.max_history_size:
            self.metrics_history.pop(0)
        
        # Update Prometheus metrics
        self.connections_gauge.set(self._connection_count)
        self.tunnels_gauge.set(self._tunnel_count)
        self.cpu_gauge.set(cpu_usage)
        self.memory_gauge.set(memory_usage)
        
        # Update performance tracking
        if latency > 0:
            self._performance_data["latency_samples"].append(latency)
            if len(self._performance_data["latency_samples"]) > 100:
                self._performance_data["latency_samples"].pop(0)
            
            self._performance_data["avg_latency"] = sum(self._performance_data["latency_samples"]) / len(self._performance_data["latency_samples"])
            self._performance_data["min_latency"] = min(self._performance_data["latency_samples"])
            self._performance_data["max_latency"] = max(self._performance_data["latency_samples"])
        
        self._last_collection = current_time
        
        logger.debug(f"Metrics updated: connections={self._connection_count}, tunnels={self._tunnel_count}")
    
    def _calculate_latency(self) -> float:
        """Calculate current latency (simplified implementation)"""
        # In a real implementation, this would measure actual network latency
        # For now, return a simulated value
        import random
        return random.uniform(10, 100)  # 10-100ms
    
    def increment_connections(self):
        """Increment connection count"""
        self._connection_count += 1
        self.connections_gauge.inc()
    
    def decrement_connections(self):
        """Decrement connection count"""
        self._connection_count = max(0, self._connection_count - 1)
        self.connections_gauge.dec()
    
    def record_traffic(self, bytes_count: int):
        """Record traffic data"""
        self._total_bytes_received += bytes_count
        self.bytes_received_counter.inc(bytes_count)
    
    def record_sent_traffic(self, bytes_count: int):
        """Record sent traffic data"""
        self._total_bytes_sent += bytes_count
        self.bytes_sent_counter.inc(bytes_count)
    
    def record_error(self):
        """Record an error"""
        self._total_errors += 1
        self.errors_counter.inc()
    
    def record_latency(self, latency_ms: float):
        """Record latency measurement"""
        self.latency_histogram.observe(latency_ms)
        
        # Update performance tracking
        self._performance_data["latency_samples"].append(latency_ms)
        if len(self._performance_data["latency_samples"]) > 100:
            self._performance_data["latency_samples"].pop(0)
    
    def set_tunnel_count(self, count: int):
        """Set tunnel count"""
        self._tunnel_count = count
        self.tunnels_gauge.set(count)
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        return {
            "connections": self._connection_count,
            "tunnels": self._tunnel_count,
            "bytes_sent": self._total_bytes_sent,
            "bytes_received": self._total_bytes_received,
            "errors": self._total_errors,
            "cpu_usage": psutil.cpu_percent(),
            "memory_usage": psutil.virtual_memory().percent,
            "performance": self._performance_data.copy()
        }
    
    def get_metrics_history(self, minutes: int = 60) -> List[MetricsData]:
        """Get metrics history for the specified time period"""
        cutoff_time = time.time() - (minutes * 60)
        return [
            metrics for metrics in self.metrics_history
            if metrics.timestamp >= cutoff_time
        ]
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary"""
        if not self._performance_data["latency_samples"]:
            return {
                "avg_latency": 0.0,
                "min_latency": 0.0,
                "max_latency": 0.0,
                "sample_count": 0
            }
        
        return {
            "avg_latency": self._performance_data["avg_latency"],
            "min_latency": self._performance_data["min_latency"],
            "max_latency": self._performance_data["max_latency"],
            "sample_count": len(self._performance_data["latency_samples"])
        }


class HealthChecker:
    """Health checking for the VPN service"""
    
    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics = metrics_collector
        self.health_status = "healthy"
        self.last_check = time.time()
        self.check_interval = 60  # seconds
    
    async def start_health_checks(self):
        """Start periodic health checks"""
        while True:
            await asyncio.sleep(self.check_interval)
            await self._perform_health_check()
    
    async def _perform_health_check(self):
        """Perform health check"""
        try:
            current_metrics = self.metrics.get_current_metrics()
            
            # Check CPU usage
            if current_metrics["cpu_usage"] > 90:
                self.health_status = "warning"
                logger.warning("High CPU usage detected")
            
            # Check memory usage
            if current_metrics["memory_usage"] > 90:
                self.health_status = "warning"
                logger.warning("High memory usage detected")
            
            # Check error rate
            total_requests = current_metrics["bytes_sent"] + current_metrics["bytes_received"]
            if total_requests > 0:
                error_rate = current_metrics["errors"] / total_requests
                if error_rate > 0.1:  # 10% error rate
                    self.health_status = "critical"
                    logger.error(f"High error rate detected: {error_rate:.2%}")
            
            # Check latency
            performance = current_metrics.get("performance", {})
            if performance.get("avg_latency", 0) > 1000:  # 1 second
                self.health_status = "warning"
                logger.warning("High latency detected")
            
            # Reset to healthy if no issues
            if self.health_status != "critical":
                self.health_status = "healthy"
            
            self.last_check = time.time()
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            self.health_status = "critical"
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get current health status"""
        return {
            "status": self.health_status,
            "last_check": self.last_check,
            "uptime": time.time() - self.last_check
        }


class AlertManager:
    """Manages alerts and notifications"""
    
    def __init__(self):
        self.alerts: List[Dict[str, Any]] = []
        self.alert_thresholds = {
            "cpu_usage": 80,
            "memory_usage": 80,
            "error_rate": 0.05,
            "latency": 500
        }
    
    def check_alerts(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check for alerts based on metrics"""
        new_alerts = []
        
        # CPU usage alert
        if metrics.get("cpu_usage", 0) > self.alert_thresholds["cpu_usage"]:
            new_alerts.append({
                "type": "cpu_usage",
                "level": "warning",
                "message": f"High CPU usage: {metrics['cpu_usage']:.1f}%",
                "timestamp": time.time()
            })
        
        # Memory usage alert
        if metrics.get("memory_usage", 0) > self.alert_thresholds["memory_usage"]:
            new_alerts.append({
                "type": "memory_usage",
                "level": "warning",
                "message": f"High memory usage: {metrics['memory_usage']:.1f}%",
                "timestamp": time.time()
            })
        
        # Error rate alert
        total_requests = metrics.get("bytes_sent", 0) + metrics.get("bytes_received", 0)
        if total_requests > 0:
            error_rate = metrics.get("errors", 0) / total_requests
            if error_rate > self.alert_thresholds["error_rate"]:
                new_alerts.append({
                    "type": "error_rate",
                    "level": "critical",
                    "message": f"High error rate: {error_rate:.2%}",
                    "timestamp": time.time()
                })
        
        # Latency alert
        performance = metrics.get("performance", {})
        if performance.get("avg_latency", 0) > self.alert_thresholds["latency"]:
            new_alerts.append({
                "type": "latency",
                "level": "warning",
                "message": f"High latency: {performance['avg_latency']:.1f}ms",
                "timestamp": time.time()
            })
        
        # Add new alerts
        self.alerts.extend(new_alerts)
        
        # Clean up old alerts (older than 24 hours)
        cutoff_time = time.time() - 86400
        self.alerts = [alert for alert in self.alerts if alert["timestamp"] > cutoff_time]
        
        return new_alerts
    
    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get active alerts"""
        return [alert for alert in self.alerts if alert["level"] in ["warning", "critical"]]
    
    def clear_alerts(self, alert_type: Optional[str] = None):
        """Clear alerts"""
        if alert_type:
            self.alerts = [alert for alert in self.alerts if alert["type"] != alert_type]
        else:
            self.alerts.clear()