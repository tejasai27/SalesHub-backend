from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    user_id = db.Column(db.String(255), primary_key=True)
    session_id = db.Column(db.String(255), unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_active = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    chats = db.relationship('ChatSession', backref='user', lazy=True)

class ChatSession(db.Model):
    __tablename__ = 'chat_sessions'
    
    chat_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(255), db.ForeignKey('users.user_id'), nullable=False)
    session_id = db.Column(db.String(255))
    message_id = db.Column(db.String(255))
    message_type = db.Column(db.Enum('user', 'assistant'))
    message_text = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
