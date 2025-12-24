from flask import Blueprint, request, jsonify
from database.models import db, User, ChatSession
from utils.gemini_client import GeminiClient
import uuid
from datetime import datetime
import logging

chat_bp = Blueprint('chat', __name__)
gemini_client = GeminiClient()
logger = logging.getLogger(__name__)

@chat_bp.route('/api/chat/send', methods=['POST'])
def send_message():
    """Handle chat messages"""
    try:
        data = request.json
        
        # Validate required fields
        if not data or 'message' not in data:
            return jsonify({"error": "Message is required"}), 400
        
        user_id = data.get('user_id', str(uuid.uuid4()))
        session_id = data.get('session_id', str(uuid.uuid4()))
        message = data['message'].strip()
        
        # Validate message
        if not message:
            return jsonify({"error": "Message cannot be empty"}), 400
        
        # Create or get user
        user = User.query.filter_by(user_id=user_id).first()
        if not user:
            user = User(user_id=user_id, session_id=session_id)
            db.session.add(user)
            db.session.commit()
        
        # Store user message
        user_msg = ChatSession(
            user_id=user_id,
            session_id=session_id,
            message_id=str(uuid.uuid4()),
            message_type='user',
            message_text=message,
            timestamp=datetime.utcnow()
        )
        db.session.add(user_msg)
        
        # Get browsing context for AI
        context = gemini_client.get_chat_context(user_id, session_id)
        
        # Generate AI response
        ai_response = gemini_client.generate_response(message, context)
        
        # Store AI response
        ai_msg = ChatSession(
            user_id=user_id,
            session_id=session_id,
            message_id=str(uuid.uuid4()),
            message_type='assistant',
            message_text=ai_response,
            timestamp=datetime.utcnow()
        )
        db.session.add(ai_msg)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "response": ai_response,
            "message_id": ai_msg.message_id,
            "user_id": user_id,
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        return jsonify({"error": "Internal server error", "details": str(e)}), 500

@chat_bp.route('/api/chat/history/<user_id>', methods=['GET'])
def get_chat_history(user_id):
    """Retrieve chat history for a user"""
    try:
        limit = int(request.args.get('limit', 50))
        session_id = request.args.get('session_id')
        
        query = ChatSession.query.filter_by(user_id=user_id)
        if session_id:
            query = query.filter_by(session_id=session_id)
        
        chats = query.order_by(ChatSession.timestamp.asc()).limit(limit).all()
        
        history = [{
            "id": chat.chat_id,
            "message_id": chat.message_id,
            "message_type": chat.message_type,
            "message": chat.message_text,
            "timestamp": chat.timestamp.isoformat() if chat.timestamp else None
        } for chat in chats]
        
        return jsonify({
            "success": True,
            "history": history,
            "count": len(history)
        })
        
    except Exception as e:
        logger.error(f"History error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@chat_bp.route('/api/chat/test', methods=['GET'])
def test_gemini():
    """Test Gemini API connection - does NOT call the API to save quota"""
    return jsonify({
        "success": True,
        "test": "Gemini API Status",
        "gemini_available": gemini_client.gemini_available,
        "message": "API client is configured" if gemini_client.gemini_available else "API key not configured"
    })