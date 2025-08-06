#!/usr/bin/env python3
"""
Authentication management for WebSocket VPN
Handles client authentication and authorization
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
import jwt
from websockets.server import WebSocketServerProtocol

logger = logging.getLogger(__name__)


@dataclass
class AuthSession:
    """Authentication session"""
    client_id: str
    token: str
    created_at: float
    last_activity: float
    permissions: List[str]
    rate_limit_count: int = 0
    rate_limit_reset: float = 0


class AuthManager:
    """Manages client authentication and authorization"""
    
    def __init__(self):
        self.sessions: Dict[str, AuthSession] = {}
        self.valid_tokens: Set[str] = set()
        self.rate_limit_config = {
            "requests": 100,
            "window": 60  # seconds
        }
        self._load_tokens()
    
    def _load_tokens(self):
        """Load valid authentication tokens"""
        try:
            from config import config
            self.valid_tokens = set(config.server.auth.tokens)
            self.rate_limit_config = config.server.auth.rate_limit
            logger.info(f"Loaded {len(self.valid_tokens)} authentication tokens")
        except Exception as e:
            logger.error(f"Error loading authentication tokens: {e}")
            # Use default token for development
            self.valid_tokens = {"your-secret-token-here"}
    
    async def authenticate(self, websocket: WebSocketServerProtocol) -> bool:
        """Authenticate a WebSocket client"""
        try:
            # Extract client information
            client_ip = websocket.remote_address[0]
            client_port = websocket.remote_address[1]
            client_id = f"{client_ip}:{client_port}"
            
            # Check if client is already authenticated
            if client_id in self.sessions:
                session = self.sessions[client_id]
                if self._is_session_valid(session):
                    session.last_activity = time.time()
                    return True
                else:
                    # Remove expired session
                    del self.sessions[client_id]
            
            # Check rate limiting
            if not self._check_rate_limit(client_id):
                logger.warning(f"Rate limit exceeded for {client_id}")
                return False
            
            # Extract token from headers or query parameters
            token = await self._extract_token(websocket)
            if not token:
                logger.warning(f"No authentication token provided by {client_id}")
                return False
            
            # Validate token
            if not self._validate_token(token):
                logger.warning(f"Invalid authentication token from {client_id}")
                return False
            
            # Create session
            session = AuthSession(
                client_id=client_id,
                token=token,
                created_at=time.time(),
                last_activity=time.time(),
                permissions=["tunnel", "proxy", "read"]
            )
            
            self.sessions[client_id] = session
            logger.info(f"Client {client_id} authenticated successfully")
            
            return True
            
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False
    
    async def _extract_token(self, websocket: WebSocketServerProtocol) -> Optional[str]:
        """Extract authentication token from WebSocket connection"""
        try:
            # Check query parameters
            if websocket.path:
                import urllib.parse
                query = urllib.parse.urlparse(websocket.path).query
                params = urllib.parse.parse_qs(query)
                if 'token' in params:
                    return params['token'][0]
            
            # Check headers
            headers = websocket.request_headers
            if 'Authorization' in headers:
                auth_header = headers['Authorization']
                if auth_header.startswith('Bearer '):
                    return auth_header[7:]  # Remove 'Bearer ' prefix
            
            # Check for custom header
            if 'X-Auth-Token' in headers:
                return headers['X-Auth-Token']
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting token: {e}")
            return None
    
    def _validate_token(self, token: str) -> bool:
        """Validate authentication token"""
        return token in self.valid_tokens
    
    def _is_session_valid(self, session: AuthSession) -> bool:
        """Check if session is still valid"""
        current_time = time.time()
        
        # Check session timeout (24 hours)
        if current_time - session.created_at > 86400:
            return False
        
        # Check activity timeout (1 hour)
        if current_time - session.last_activity > 3600:
            return False
        
        return True
    
    def _check_rate_limit(self, client_id: str) -> bool:
        """Check rate limiting for client"""
        current_time = time.time()
        
        # Reset rate limit if window has passed
        if current_time > self.rate_limit_config["window"]:
            # Reset all rate limits
            for session in self.sessions.values():
                session.rate_limit_count = 0
                session.rate_limit_reset = current_time + self.rate_limit_config["window"]
        
        # Check if client has exceeded rate limit
        if client_id in self.sessions:
            session = self.sessions[client_id]
            if session.rate_limit_count >= self.rate_limit_config["requests"]:
                return False
            session.rate_limit_count += 1
        else:
            # New client, initialize rate limit
            session = AuthSession(
                client_id=client_id,
                token="",
                created_at=current_time,
                last_activity=current_time,
                permissions=[],
                rate_limit_count=1,
                rate_limit_reset=current_time + self.rate_limit_config["window"]
            )
            self.sessions[client_id] = session
        
        return True
    
    def authorize(self, client_id: str, permission: str) -> bool:
        """Check if client has specific permission"""
        if client_id not in self.sessions:
            return False
        
        session = self.sessions[client_id]
        if not self._is_session_valid(session):
            return False
        
        return permission in session.permissions
    
    def get_session(self, client_id: str) -> Optional[AuthSession]:
        """Get client session"""
        if client_id not in self.sessions:
            return None
        
        session = self.sessions[client_id]
        if not self._is_session_valid(session):
            del self.sessions[client_id]
            return None
        
        return session
    
    def revoke_session(self, client_id: str):
        """Revoke client session"""
        if client_id in self.sessions:
            del self.sessions[client_id]
            logger.info(f"Revoked session for {client_id}")
    
    def cleanup_expired_sessions(self):
        """Remove expired sessions"""
        current_time = time.time()
        expired_sessions = []
        
        for client_id, session in self.sessions.items():
            if not self._is_session_valid(session):
                expired_sessions.append(client_id)
        
        for client_id in expired_sessions:
            del self.sessions[client_id]
        
        if expired_sessions:
            logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
    
    def get_session_stats(self) -> Dict[str, any]:
        """Get authentication statistics"""
        current_time = time.time()
        active_sessions = 0
        expired_sessions = 0
        
        for session in self.sessions.values():
            if self._is_session_valid(session):
                active_sessions += 1
            else:
                expired_sessions += 1
        
        return {
            "total_sessions": len(self.sessions),
            "active_sessions": active_sessions,
            "expired_sessions": expired_sessions,
            "valid_tokens": len(self.valid_tokens)
        }
    
    async def start_cleanup_task(self):
        """Start periodic cleanup of expired sessions"""
        while True:
            await asyncio.sleep(300)  # Clean up every 5 minutes
            self.cleanup_expired_sessions()


class JWTManager:
    """JWT token management"""
    
    def __init__(self, secret_key: str = "your-secret-key"):
        self.secret_key = secret_key
        self.algorithm = "HS256"
    
    def create_token(self, payload: Dict[str, any], expires_in: int = 3600) -> str:
        """Create JWT token"""
        payload.update({
            "exp": time.time() + expires_in,
            "iat": time.time()
        })
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def verify_token(self, token: str) -> Optional[Dict[str, any]]:
        """Verify JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None
    
    def refresh_token(self, token: str, expires_in: int = 3600) -> Optional[str]:
        """Refresh JWT token"""
        payload = self.verify_token(token)
        if payload:
            # Remove expiration and issued at
            payload.pop("exp", None)
            payload.pop("iat", None)
            return self.create_token(payload, expires_in)
        return None


class RateLimiter:
    """Rate limiting implementation"""
    
    def __init__(self, max_requests: int = 100, window: int = 60):
        self.max_requests = max_requests
        self.window = window
        self.requests: Dict[str, List[float]] = {}
    
    def is_allowed(self, client_id: str) -> bool:
        """Check if request is allowed"""
        current_time = time.time()
        
        if client_id not in self.requests:
            self.requests[client_id] = []
        
        # Remove old requests outside the window
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id]
            if current_time - req_time < self.window
        ]
        
        # Check if limit exceeded
        if len(self.requests[client_id]) >= self.max_requests:
            return False
        
        # Add current request
        self.requests[client_id].append(current_time)
        return True
    
    def get_remaining_requests(self, client_id: str) -> int:
        """Get remaining requests for client"""
        current_time = time.time()
        
        if client_id not in self.requests:
            return self.max_requests
        
        # Remove old requests
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id]
            if current_time - req_time < self.window
        ]
        
        return max(0, self.max_requests - len(self.requests[client_id]))
    
    def reset(self, client_id: str):
        """Reset rate limit for client"""
        if client_id in self.requests:
            del self.requests[client_id]
    
    def cleanup_expired(self):
        """Clean up expired rate limit entries"""
        current_time = time.time()
        expired_clients = []
        
        for client_id, requests in self.requests.items():
            # Remove old requests
            self.requests[client_id] = [
                req_time for req_time in requests
                if current_time - req_time < self.window
            ]
            
            # Remove client if no recent requests
            if not self.requests[client_id]:
                expired_clients.append(client_id)
        
        for client_id in expired_clients:
            del self.requests[client_id]