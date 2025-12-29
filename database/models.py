"""
Database models for the sales chatbot.
Includes User profiles and ChatSession with metadata.
"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    """User model with profile information for sales team members."""
    __tablename__ = 'users'
    
    user_id = db.Column(db.String(255), primary_key=True)
    session_id = db.Column(db.String(255))
    
    # Profile fields (for future use with authentication)
    name = db.Column(db.String(255), nullable=True)
    email = db.Column(db.String(255), nullable=True)
    role = db.Column(db.String(50), default='sales_rep')  # sales_rep, manager, admin
    team = db.Column(db.String(100), nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_active = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Settings (JSON stored as text for SQLite compatibility)
    preferences = db.Column(db.Text, nullable=True)  # JSON: {"theme": "dark", ...}
    
    # Relationships
    chats = db.relationship('ChatSession', backref='user', lazy=True)
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "user_id": self.user_id,
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "team": self.team,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_active": self.last_active.isoformat() if self.last_active else None
        }


class ChatSession(db.Model):
    """Chat message model with core fields and performance tracking."""
    __tablename__ = 'chat_sessions'
    
    chat_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(255), db.ForeignKey('users.user_id'), nullable=False)
    session_id = db.Column(db.String(255))
    message_id = db.Column(db.String(255))
    message_type = db.Column(db.String(20))  # 'user' or 'assistant'
    message_text = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Performance tracking (for AI responses only)
    response_time_ms = db.Column(db.Integer, nullable=True)  # AI response time
    tokens_used = db.Column(db.Integer, nullable=True)  # Token count from Gemini API
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "id": self.chat_id,
            "message_id": self.message_id,
            "message_type": self.message_type,
            "message": self.message_text,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "response_time_ms": self.response_time_ms,
            "tokens_used": self.tokens_used
        }
