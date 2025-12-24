"""
Input validation utilities for the sales chatbot.
Provides validation for messages, user IDs, and content sanitization.
"""
import re
import html
from functools import wraps
from flask import request, jsonify


class ValidationError(Exception):
    """Custom exception for validation errors."""
    def __init__(self, message, field=None):
        self.message = message
        self.field = field
        super().__init__(self.message)


# Validation Constants
MIN_MESSAGE_LENGTH = 1
MAX_MESSAGE_LENGTH = 2000
MAX_USER_ID_LENGTH = 100
MAX_SESSION_ID_LENGTH = 100
USER_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_\-]+$')
SESSION_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_\-]+$')


def sanitize_html(text):
    """
    Sanitize text by escaping HTML entities to prevent XSS attacks.
    
    Args:
        text (str): Raw input text
        
    Returns:
        str: Sanitized text with HTML entities escaped
    """
    if not text:
        return text
    
    # Escape HTML entities
    sanitized = html.escape(text)
    
    # Remove any remaining script-like patterns
    sanitized = re.sub(r'<script[^>]*>.*?</script>', '', sanitized, flags=re.IGNORECASE | re.DOTALL)
    sanitized = re.sub(r'javascript:', '', sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r'on\w+\s*=', '', sanitized, flags=re.IGNORECASE)
    
    return sanitized.strip()


def validate_message(message):
    """
    Validate a chat message.
    
    Args:
        message (str): The message to validate
        
    Returns:
        tuple: (is_valid, sanitized_message or error_message)
    """
    if message is None:
        return False, "Message is required"
    
    if not isinstance(message, str):
        return False, "Message must be a string"
    
    # Trim whitespace
    message = message.strip()
    
    if len(message) < MIN_MESSAGE_LENGTH:
        return False, "Message cannot be empty"
    
    if len(message) > MAX_MESSAGE_LENGTH:
        return False, f"Message too long. Maximum {MAX_MESSAGE_LENGTH} characters allowed"
    
    # Sanitize the message
    sanitized = sanitize_html(message)
    
    return True, sanitized


def validate_user_id(user_id):
    """
    Validate a user ID.
    
    Args:
        user_id (str): The user ID to validate
        
    Returns:
        tuple: (is_valid, user_id or error_message)
    """
    if not user_id:
        return False, "User ID is required"
    
    if not isinstance(user_id, str):
        return False, "User ID must be a string"
    
    if len(user_id) > MAX_USER_ID_LENGTH:
        return False, f"User ID too long. Maximum {MAX_USER_ID_LENGTH} characters"
    
    if not USER_ID_PATTERN.match(user_id):
        return False, "User ID contains invalid characters"
    
    return True, user_id


def validate_session_id(session_id):
    """
    Validate a session ID.
    
    Args:
        session_id (str): The session ID to validate
        
    Returns:
        tuple: (is_valid, session_id or error_message)
    """
    if not session_id:
        return False, "Session ID is required"
    
    if not isinstance(session_id, str):
        return False, "Session ID must be a string"
    
    if len(session_id) > MAX_SESSION_ID_LENGTH:
        return False, f"Session ID too long. Maximum {MAX_SESSION_ID_LENGTH} characters"
    
    if not SESSION_ID_PATTERN.match(session_id):
        return False, "Session ID contains invalid characters"
    
    return True, session_id


def validate_chat_request(data):
    """
    Validate a complete chat request.
    
    Args:
        data (dict): Request data containing message, user_id, session_id
        
    Returns:
        tuple: (is_valid, validated_data or error_dict)
    """
    errors = {}
    validated = {}
    
    # Validate message
    is_valid, result = validate_message(data.get('message'))
    if is_valid:
        validated['message'] = result
    else:
        errors['message'] = result
    
    # Validate user_id
    is_valid, result = validate_user_id(data.get('user_id'))
    if is_valid:
        validated['user_id'] = result
    else:
        errors['user_id'] = result
    
    # Validate session_id
    is_valid, result = validate_session_id(data.get('session_id'))
    if is_valid:
        validated['session_id'] = result
    else:
        errors['session_id'] = result
    
    if errors:
        return False, errors
    
    return True, validated


def require_valid_json(f):
    """
    Decorator to ensure request has valid JSON body.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not request.is_json:
            return jsonify({
                "error": "Content-Type must be application/json",
                "success": False
            }), 400
        
        data = request.get_json(silent=True)
        if data is None:
            return jsonify({
                "error": "Invalid JSON body",
                "success": False
            }), 400
        
        return f(*args, **kwargs)
    return decorated_function
