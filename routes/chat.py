"""
Chat routes for the sales chatbot with validation, rate limiting, and analytics.
"""
from flask import Blueprint, request, jsonify
from database.models import db, User, ChatSession
from utils.gemini_client import GeminiClient
from utils.validators import validate_chat_request, validate_message, require_valid_json
from utils.rate_limiter import rate_limit, get_rate_limit_status
from utils.analytics import analytics, ResponseTimer
import uuid
from datetime import datetime
import logging
import csv
import io

chat_bp = Blueprint('chat', __name__)
gemini_client = GeminiClient()
logger = logging.getLogger(__name__)


@chat_bp.route('/api/chat/send', methods=['POST'])
@rate_limit()
def send_message():
    """
    Handle chat messages with validation, rate limiting, and context.
    
    Request body:
        message (str): User's message (1-2000 chars)
        user_id (str): User identifier
        session_id (str): Session identifier
        
    Returns:
        JSON with AI response and metadata
    """
    try:
        data = request.json
        
        # Validate required fields
        if not data:
            return jsonify({
                "error": "Request body is required",
                "success": False
            }), 400
        
        # Use validators
        is_valid, result = validate_message(data.get('message'))
        if not is_valid:
            return jsonify({
                "error": result,
                "success": False
            }), 400
        
        message = result  # sanitized message
        user_id = data.get('user_id', str(uuid.uuid4()))
        session_id = data.get('session_id', str(uuid.uuid4()))
        
        # Track analytics
        analytics.track_message(user_id)
        
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
        
        # Get conversation history for context
        conversation_history = gemini_client.get_conversation_history(user_id, session_id, limit=10)
        
        # Get additional context
        context = gemini_client.get_chat_context(user_id, session_id)
        
        # Generate AI response with timing
        timer = ResponseTimer()
        with timer:
            ai_response_data = gemini_client.generate_response(
                message,
                context=context,
                conversation_history=conversation_history
            )
        
        # Extract response text and tokens
        ai_response = ai_response_data['text'] if isinstance(ai_response_data, dict) else ai_response_data
        tokens_used = ai_response_data.get('tokens_used') if isinstance(ai_response_data, dict) else None
        response_time_ms = int(timer.duration_ms) if timer.duration_ms else None
        
        # Store AI response with performance metrics
        ai_msg = ChatSession(
            user_id=user_id,
            session_id=session_id,
            message_id=str(uuid.uuid4()),
            message_type='assistant',
            message_text=ai_response,
            timestamp=datetime.utcnow(),
            response_time_ms=response_time_ms,
            tokens_used=tokens_used
        )
        db.session.add(ai_msg)
        db.session.commit()
        
        # Get rate limit status
        rate_status = get_rate_limit_status(user_id)
        
        return jsonify({
            "success": True,
            "response": ai_response,
            "message_id": ai_msg.message_id,
            "user_id": user_id,
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "performance": {
                "response_time_ms": response_time_ms,
                "tokens_used": tokens_used
            },
            "rate_limit": {
                "remaining_minute": rate_status["minute_remaining"],
                "remaining_day": rate_status["day_remaining"]
            }
        })
        
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        analytics.track_error("chat_error")
        return jsonify({
            "error": "Internal server error",
            "success": False
        }), 500


@chat_bp.route('/api/chat/history/<user_id>', methods=['GET'])
def get_chat_history(user_id):
    """
    Retrieve chat history for a user.
    
    Query params:
        limit (int): Maximum messages to return (default 50)
        session_id (str): Filter by session ID
        
    Returns:
        JSON with chat history
    """
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
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
        return jsonify({"error": str(e), "success": False}), 500


@chat_bp.route('/api/chat/test', methods=['GET'])
def test_gemini():
    """Test Gemini API connection - does NOT call the API to save quota."""
    return jsonify({
        "success": True,
        "test": "Gemini API Status",
        "gemini_available": gemini_client.gemini_available,
        "message": "API client is configured" if gemini_client.gemini_available else "API key not configured"
    })


@chat_bp.route('/api/chat/export/<user_id>', methods=['GET'])
def export_chat_history(user_id):
    """
    Export chat history as JSON or CSV.
    
    Query params:
        format (str): 'json' or 'csv' (default 'json')
        session_id (str): Filter by session ID
        
    Returns:
        JSON or CSV file download
    """
    try:
        export_format = request.args.get('format', 'json').lower()
        session_id = request.args.get('session_id')
        
        # Query messages
        query = ChatSession.query.filter_by(user_id=user_id)
        if session_id:
            query = query.filter_by(session_id=session_id)
        
        chats = query.order_by(ChatSession.timestamp.asc()).all()
        
        if export_format == 'csv':
            # Generate CSV
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['Timestamp', 'Type', 'Message', 'Message ID', 'Session ID'])
            
            for chat in chats:
                writer.writerow([
                    chat.timestamp.isoformat() if chat.timestamp else '',
                    chat.message_type,
                    chat.message_text,
                    chat.message_id,
                    chat.session_id
                ])
            
            csv_content = output.getvalue()
            
            from flask import Response
            return Response(
                csv_content,
                mimetype='text/csv',
                headers={'Content-Disposition': f'attachment; filename=chat_export_{user_id}.csv'}
            )
        
        else:
            # JSON format
            history = [{
                "timestamp": chat.timestamp.isoformat() if chat.timestamp else None,
                "type": chat.message_type,
                "message": chat.message_text,
                "message_id": chat.message_id,
                "session_id": chat.session_id
            } for chat in chats]
            
            return jsonify({
                "success": True,
                "user_id": user_id,
                "total_messages": len(history),
                "export_date": datetime.utcnow().isoformat(),
                "messages": history
            })
            
    except Exception as e:
        logger.error(f"Export error: {str(e)}")
        return jsonify({"error": str(e), "success": False}), 500


@chat_bp.route('/api/chat/stats/<user_id>', methods=['GET'])
def get_user_stats(user_id):
    """
    Get usage statistics for a user.
    
    Returns:
        JSON with user stats and rate limit status
    """
    try:
        # Get analytics stats
        user_stats = analytics.get_user_stats(user_id)
        
        # Get rate limit status
        rate_status = get_rate_limit_status(user_id)
        
        # Get message count from database
        total_messages = ChatSession.query.filter_by(
            user_id=user_id,
            message_type='user'
        ).count()
        
        return jsonify({
            "success": True,
            "user_id": user_id,
            "stats": {
                "messages_today": user_stats.get("messages_today", 0),
                "total_messages": total_messages,
                "rate_limit": rate_status
            }
        })
        
    except Exception as e:
        logger.error(f"Stats error: {str(e)}")
        return jsonify({"error": str(e), "success": False}), 500


@chat_bp.route('/api/chat/analytics', methods=['GET'])
def get_system_analytics():
    """
    Get system-wide analytics (for admin use).
    
    Returns:
        JSON with system stats
    """
    try:
        system_stats = analytics.get_system_stats()
        daily_report = analytics.get_daily_report()
        
        return jsonify({
            "success": True,
            "system": system_stats,
            "today": daily_report
        })
        
    except Exception as e:
        logger.error(f"Analytics error: {str(e)}")
        return jsonify({"error": str(e), "success": False}), 500