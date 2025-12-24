from flask import Blueprint, jsonify
from database.models import db, User, ChatSession
from datetime import datetime
import logging

debug_bp = Blueprint('debug', __name__)
logger = logging.getLogger(__name__)

@debug_bp.route('/api/debug/db-status', methods=['GET'])
def db_status():
    """Check database status and data"""
    try:
        # Count total records
        total_users = User.query.count()
        total_chats = ChatSession.query.count()
        
        # Check if tables exist
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        return jsonify({
            "success": True,
            "database_status": "connected",
            "tables": tables,
            "counts": {
                "users": total_users,
                "chat_messages": total_chats
            },
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Database status error: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "database_status": "error"
        }), 500

@debug_bp.route('/api/debug/user-data/<user_id>', methods=['GET'])
def user_data(user_id):
    """Get all data for a specific user"""
    try:
        # Get user
        user = User.query.filter_by(user_id=user_id).first()
        
        if not user:
            return jsonify({
                "success": False,
                "error": f"User {user_id} not found",
                "user_exists": False
            })
        
        # Get chat history for user
        chats = ChatSession.query.filter_by(
            user_id=user_id
        ).order_by(ChatSession.timestamp.desc()).limit(50).all()
        
        chats_list = []
        for chat in chats:
            chats_list.append({
                "chat_id": chat.chat_id,
                "message_type": chat.message_type,
                "message_text": chat.message_text[:100] if chat.message_text else "",
                "timestamp": chat.timestamp.isoformat() if chat.timestamp else None
            })
        
        return jsonify({
            "success": True,
            "user": {
                "user_id": user.user_id,
                "session_id": user.session_id,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "last_active": user.last_active.isoformat() if user.last_active else None
            },
            "chat_messages_count": len(chats),
            "chats": chats_list
        })
        
    except Exception as e:
        logger.error(f"User data error: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500