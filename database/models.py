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
    activities = db.relationship('BrowserActivity', backref='user', lazy=True)

class ChatSession(db.Model):
    __tablename__ = 'chat_sessions'
    
    chat_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(255), db.ForeignKey('users.user_id'), nullable=False)
    session_id = db.Column(db.String(255))
    message_id = db.Column(db.String(255))
    message_type = db.Column(db.Enum('user', 'assistant'))
    message_text = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class BrowserActivity(db.Model):
    __tablename__ = 'browser_activities'
    
    activity_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(255), db.ForeignKey('users.user_id'), nullable=False)
    session_id = db.Column(db.String(255))
    url = db.Column(db.Text, nullable=False)
    domain = db.Column(db.String(255))
    page_title = db.Column(db.Text)
    activity_type = db.Column(db.Enum('page_visit', 'click', 'scroll', 'form_input', 'tab_change', 'search', 'copy', 'paste', 'keypress', 'navigation'))  
    element_details = db.Column(db.JSON)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    duration_seconds = db.Column(db.Integer, default=0)

class DailySession(db.Model):
    __tablename__ = 'daily_sessions'
    
    session_id = db.Column(db.String(255), primary_key=True)
    user_id = db.Column(db.String(255), db.ForeignKey('users.user_id'), nullable=False)
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    total_pages_visited = db.Column(db.Integer, default=0)
    total_interactions = db.Column(db.Integer, default=0)
    chat_messages_count = db.Column(db.Integer, default=0)