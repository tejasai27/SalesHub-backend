"""
Rate limiting utilities for the sales chatbot.
Provides per-user rate limiting to prevent API abuse.
"""
import time
from functools import wraps
from flask import request, jsonify
from collections import defaultdict
import threading


class RateLimiter:
    """
    In-memory rate limiter with per-user tracking.
    
    Supports:
    - Per-minute rate limiting
    - Per-day rate limiting
    - Thread-safe operations
    """
    
    def __init__(self, requests_per_minute=20, requests_per_day=500):
        self.requests_per_minute = requests_per_minute
        self.requests_per_day = requests_per_day
        
        # Store request timestamps per user
        # Format: {user_id: [timestamp1, timestamp2, ...]}
        self.minute_requests = defaultdict(list)
        self.day_requests = defaultdict(list)
        
        # Lock for thread-safe operations
        self.lock = threading.Lock()
    
    def _clean_old_requests(self, user_id, current_time):
        """Remove expired request timestamps."""
        minute_ago = current_time - 60
        day_ago = current_time - 86400  # 24 hours in seconds
        
        # Clean minute requests
        self.minute_requests[user_id] = [
            ts for ts in self.minute_requests[user_id] 
            if ts > minute_ago
        ]
        
        # Clean day requests
        self.day_requests[user_id] = [
            ts for ts in self.day_requests[user_id] 
            if ts > day_ago
        ]
    
    def check_rate_limit(self, user_id):
        """
        Check if a user has exceeded their rate limit.
        
        Args:
            user_id (str): The user's identifier
            
        Returns:
            tuple: (is_allowed, error_message or None, retry_after_seconds or None)
        """
        current_time = time.time()
        
        with self.lock:
            self._clean_old_requests(user_id, current_time)
            
            minute_count = len(self.minute_requests[user_id])
            day_count = len(self.day_requests[user_id])
            
            # Check minute limit
            if minute_count >= self.requests_per_minute:
                oldest_request = min(self.minute_requests[user_id])
                retry_after = int(60 - (current_time - oldest_request)) + 1
                return (
                    False, 
                    f"Rate limit exceeded. Maximum {self.requests_per_minute} requests per minute.",
                    retry_after
                )
            
            # Check day limit
            if day_count >= self.requests_per_day:
                oldest_request = min(self.day_requests[user_id])
                retry_after = int(86400 - (current_time - oldest_request)) + 1
                return (
                    False,
                    f"Daily limit exceeded. Maximum {self.requests_per_day} requests per day.",
                    retry_after
                )
            
            return True, None, None
    
    def record_request(self, user_id):
        """
        Record a request for a user.
        
        Args:
            user_id (str): The user's identifier
        """
        current_time = time.time()
        
        with self.lock:
            self.minute_requests[user_id].append(current_time)
            self.day_requests[user_id].append(current_time)
    
    def get_usage(self, user_id):
        """
        Get current usage statistics for a user.
        
        Args:
            user_id (str): The user's identifier
            
        Returns:
            dict: Usage statistics
        """
        current_time = time.time()
        
        with self.lock:
            self._clean_old_requests(user_id, current_time)
            
            return {
                "requests_this_minute": len(self.minute_requests[user_id]),
                "requests_today": len(self.day_requests[user_id]),
                "minute_limit": self.requests_per_minute,
                "day_limit": self.requests_per_day,
                "minute_remaining": self.requests_per_minute - len(self.minute_requests[user_id]),
                "day_remaining": self.requests_per_day - len(self.day_requests[user_id])
            }
    
    def reset_user(self, user_id):
        """Reset rate limit counters for a user (admin use)."""
        with self.lock:
            self.minute_requests[user_id] = []
            self.day_requests[user_id] = []


# Global rate limiter instance
rate_limiter = RateLimiter(requests_per_minute=20, requests_per_day=500)


def rate_limit(get_user_id=None):
    """
    Decorator to apply rate limiting to a route.
    
    Args:
        get_user_id: Optional function to extract user_id from request.
                    Defaults to looking for user_id in JSON body.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get user ID
            if get_user_id:
                user_id = get_user_id()
            else:
                data = request.get_json(silent=True) or {}
                user_id = data.get('user_id', request.remote_addr)
            
            # Check rate limit
            is_allowed, error_message, retry_after = rate_limiter.check_rate_limit(user_id)
            
            if not is_allowed:
                response = jsonify({
                    "error": error_message,
                    "success": False,
                    "retry_after": retry_after
                })
                response.headers['Retry-After'] = str(retry_after)
                return response, 429
            
            # Record the request
            rate_limiter.record_request(user_id)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def get_rate_limit_status(user_id):
    """
    Get rate limit status for a user.
    
    Args:
        user_id (str): The user's identifier
        
    Returns:
        dict: Rate limit status and remaining requests
    """
    return rate_limiter.get_usage(user_id)
