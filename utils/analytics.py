"""
Analytics utilities for tracking chatbot usage and performance metrics.
"""
import time
from collections import defaultdict
from datetime import datetime, timedelta
import threading


class Analytics:
    """
    Simple in-memory analytics tracking for the sales chatbot.
    
    Tracks:
    - Message counts per user/day
    - Response times
    - Error rates
    - Popular topics
    """
    
    def __init__(self):
        self.lock = threading.Lock()
        
        # Message tracking: {date_str: {user_id: count}}
        self.daily_messages = defaultdict(lambda: defaultdict(int))
        
        # Response times: [(timestamp, duration_ms)]
        self.response_times = []
        
        # Error tracking: {date_str: count}
        self.daily_errors = defaultdict(int)
        
        # Total counts
        self.total_messages = 0
        self.total_errors = 0
    
    def _get_date_key(self):
        """Get current date as string key."""
        return datetime.utcnow().strftime('%Y-%m-%d')
    
    def track_message(self, user_id):
        """
        Track a message sent by a user.
        
        Args:
            user_id (str): The user's identifier
        """
        with self.lock:
            date_key = self._get_date_key()
            self.daily_messages[date_key][user_id] += 1
            self.total_messages += 1
    
    def track_response_time(self, duration_ms):
        """
        Track API response time.
        
        Args:
            duration_ms (float): Response time in milliseconds
        """
        with self.lock:
            current_time = time.time()
            self.response_times.append((current_time, duration_ms))
            
            # Keep only last 24 hours of response times
            day_ago = current_time - 86400
            self.response_times = [
                (ts, dur) for ts, dur in self.response_times
                if ts > day_ago
            ]
    
    def track_error(self, error_type="general"):
        """
        Track an error occurrence.
        
        Args:
            error_type (str): Type of error
        """
        with self.lock:
            date_key = self._get_date_key()
            self.daily_errors[date_key] += 1
            self.total_errors += 1
    
    def get_user_stats(self, user_id):
        """
        Get statistics for a specific user.
        
        Args:
            user_id (str): The user's identifier
            
        Returns:
            dict: User statistics
        """
        with self.lock:
            date_key = self._get_date_key()
            messages_today = self.daily_messages[date_key].get(user_id, 0)
            
            # Calculate total messages for user
            total_user_messages = sum(
                users.get(user_id, 0)
                for users in self.daily_messages.values()
            )
            
            return {
                "messages_today": messages_today,
                "total_messages": total_user_messages,
            }
    
    def get_system_stats(self):
        """
        Get system-wide statistics.
        
        Returns:
            dict: System statistics
        """
        with self.lock:
            date_key = self._get_date_key()
            
            # Calculate average response time
            if self.response_times:
                avg_response_time = sum(dur for _, dur in self.response_times) / len(self.response_times)
            else:
                avg_response_time = 0
            
            # Count unique users today
            unique_users_today = len(self.daily_messages[date_key])
            
            return {
                "total_messages": self.total_messages,
                "messages_today": sum(self.daily_messages[date_key].values()),
                "unique_users_today": unique_users_today,
                "total_errors": self.total_errors,
                "errors_today": self.daily_errors[date_key],
                "avg_response_time_ms": round(avg_response_time, 2),
                "response_samples": len(self.response_times)
            }
    
    def get_daily_report(self, date_str=None):
        """
        Get a daily usage report.
        
        Args:
            date_str (str): Date in YYYY-MM-DD format. Defaults to today.
            
        Returns:
            dict: Daily report
        """
        if date_str is None:
            date_str = self._get_date_key()
        
        with self.lock:
            user_messages = self.daily_messages.get(date_str, {})
            
            return {
                "date": date_str,
                "total_messages": sum(user_messages.values()),
                "unique_users": len(user_messages),
                "errors": self.daily_errors.get(date_str, 0),
                "top_users": sorted(
                    user_messages.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:10]
            }


# Global analytics instance
analytics = Analytics()


class ResponseTimer:
    """Context manager for tracking response times."""
    
    def __init__(self):
        self.start_time = None
        self.duration_ms = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        end_time = time.time()
        self.duration_ms = (end_time - self.start_time) * 1000
        analytics.track_response_time(self.duration_ms)
        
        if exc_type is not None:
            analytics.track_error(str(exc_type))
        
        return False  # Don't suppress exceptions
