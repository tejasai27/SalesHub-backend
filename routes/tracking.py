"""
Tracking routes for website visit tracking and analytics.
"""
from flask import Blueprint, request, jsonify
from database.models import db, User, WebsiteVisit
from sqlalchemy import func, desc
from urllib.parse import urlparse
from datetime import datetime, timedelta
import logging

tracking_bp = Blueprint('tracking', __name__)
logger = logging.getLogger(__name__)


@tracking_bp.route('/api/tracking/log', methods=['POST'])
def log_visit():
    """
    Log a website visit or tab change event.
    
    Request body:
        user_id (str): User identifier
        url (str): Page URL
        title (str): Page title
        event_type (str): 'page_visit', 'tab_switch', 'url_change'
        tab_id (int): Browser tab ID
        window_id (int): Browser window ID
        duration_seconds (int): Time spent on previous page
        
    Returns:
        JSON with success status
    """
    try:
        data = request.json
        
        if not data:
            return jsonify({"error": "Request body required", "success": False}), 400
        
        url = data.get('url', '')
        if not url:
            return jsonify({"error": "URL is required", "success": False}), 400
        
        user_id = data.get('user_id', 'anonymous')
        
        # Extract domain from URL
        try:
            parsed = urlparse(url)
            domain = parsed.netloc or parsed.path.split('/')[0]
        except:
            domain = url[:50]
        
        # Create or get user
        user = User.query.filter_by(user_id=user_id).first()
        if not user:
            user = User(user_id=user_id)
            db.session.add(user)
            db.session.commit()
        
        # Create visit record
        visit = WebsiteVisit(
            user_id=user_id,
            url=url[:2000],  # Limit URL length
            domain=domain[:255],
            title=data.get('title', '')[:500] if data.get('title') else None,
            favicon_url=data.get('favicon_url', '')[:500] if data.get('favicon_url') else None,
            event_type=data.get('event_type', 'page_visit'),
            tab_id=data.get('tab_id'),
            window_id=data.get('window_id'),
            duration_seconds=data.get('duration_seconds', 0),
            timestamp=datetime.utcnow()
        )
        
        db.session.add(visit)
        db.session.commit()
        
        logger.info(f"Logged visit: {domain} for user {user_id}")
        
        return jsonify({
            "success": True,
            "visit_id": visit.id,
            "domain": domain,
            "timestamp": visit.timestamp.isoformat()
        })
        
    except Exception as e:
        logger.error(f"Tracking log error: {str(e)}")
        db.session.rollback()
        return jsonify({"error": str(e), "success": False}), 500


@tracking_bp.route('/api/tracking/history/<user_id>', methods=['GET'])
def get_history(user_id):
    """
    Get visit history for a user.
    
    Query params:
        limit (int): Max results (default 100)
        offset (int): Pagination offset
        domain (str): Filter by domain
        
    Returns:
        JSON with visit history
    """
    try:
        limit = min(int(request.args.get('limit', 100)), 500)
        offset = int(request.args.get('offset', 0))
        domain_filter = request.args.get('domain')
        days = request.args.get('days')
        
        query = WebsiteVisit.query.filter_by(user_id=user_id)
        
        # Filter by days if provided
        if days:
            try:
                days_int = int(days)
                # Filter from start of day (midnight UTC) N days ago
                now = datetime.utcnow()
                start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
                since = start_of_today - timedelta(days=days_int - 1)  # -1 because days=1 means today only
                query = query.filter(WebsiteVisit.timestamp >= since)
            except ValueError:
                pass
        
        if domain_filter:
            query = query.filter_by(domain=domain_filter)
        
        total = query.count()
        visits = query.order_by(desc(WebsiteVisit.timestamp))\
                     .offset(offset)\
                     .limit(limit)\
                     .all()
        
        return jsonify({
            "success": True,
            "history": [v.to_dict() for v in visits],
            "total": total,
            "limit": limit,
            "offset": offset
        })
        
    except Exception as e:
        logger.error(f"History error: {str(e)}")
        return jsonify({"error": str(e), "success": False}), 500


@tracking_bp.route('/api/tracking/analytics/<user_id>', methods=['GET'])
def get_analytics(user_id):
    """
    Get aggregated analytics for a user.
    
    Query params:
        days (int): Number of days to analyze (default 7)
        
    Returns:
        JSON with analytics data
    """
    try:
        days = min(int(request.args.get('days', 7)), 30)
        # Filter from start of day (midnight UTC) N days ago
        now = datetime.utcnow()
        start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        since = start_of_today - timedelta(days=days - 1)  # -1 because days=1 means today only
        
        # Base query
        base_query = WebsiteVisit.query.filter(
            WebsiteVisit.user_id == user_id,
            WebsiteVisit.timestamp >= since
        )
        
        # Total visits
        total_visits = base_query.count()
        
        # Top domains by visit count
        top_domains = db.session.query(
            WebsiteVisit.domain,
            func.count(WebsiteVisit.id).label('visit_count'),
            func.sum(WebsiteVisit.duration_seconds).label('total_duration')
        ).filter(
            WebsiteVisit.user_id == user_id,
            WebsiteVisit.timestamp >= since
        ).group_by(WebsiteVisit.domain)\
         .order_by(desc('visit_count'))\
         .limit(10)\
         .all()
        
        # Visits by day
        visits_by_day = db.session.query(
            func.date(WebsiteVisit.timestamp).label('date'),
            func.count(WebsiteVisit.id).label('count')
        ).filter(
            WebsiteVisit.user_id == user_id,
            WebsiteVisit.timestamp >= since
        ).group_by(func.date(WebsiteVisit.timestamp))\
         .order_by('date')\
         .all()
        
        # Visits by hour (for activity pattern)
        visits_by_hour = db.session.query(
            func.strftime('%H', WebsiteVisit.timestamp).label('hour'),
            func.count(WebsiteVisit.id).label('count')
        ).filter(
            WebsiteVisit.user_id == user_id,
            WebsiteVisit.timestamp >= since
        ).group_by('hour')\
         .order_by('hour')\
         .all()
        
        # Total time tracked
        total_duration = db.session.query(
            func.sum(WebsiteVisit.duration_seconds)
        ).filter(
            WebsiteVisit.user_id == user_id,
            WebsiteVisit.timestamp >= since
        ).scalar() or 0
        
        # Recent unique domains
        unique_domains = db.session.query(
            func.count(func.distinct(WebsiteVisit.domain))
        ).filter(
            WebsiteVisit.user_id == user_id,
            WebsiteVisit.timestamp >= since
        ).scalar() or 0
        
        return jsonify({
            "success": True,
            "analytics": {
                "period_days": days,
                "total_visits": total_visits,
                "unique_domains": unique_domains,
                "total_duration_seconds": total_duration,
                "total_duration_formatted": format_duration(total_duration),
                "top_domains": [
                    {
                        "domain": d[0],
                        "visits": d[1],
                        "duration_seconds": d[2] or 0,
                        "duration_formatted": format_duration(d[2] or 0)
                    } for d in top_domains
                ],
                "visits_by_day": [
                    {"date": str(d[0]), "count": d[1]} for d in visits_by_day
                ],
                "visits_by_hour": [
                    {"hour": d[0], "count": d[1]} for d in visits_by_hour
                ]
            }
        })
        
    except Exception as e:
        logger.error(f"Analytics error: {str(e)}")
        return jsonify({"error": str(e), "success": False}), 500


@tracking_bp.route('/api/tracking/update-duration', methods=['POST'])
def update_duration():
    """
    Update duration for a previous visit (called when leaving a page).
    
    Request body:
        visit_id (int): ID of the visit to update
        duration_seconds (int): Time spent on page
        
    Returns:
        JSON with success status
    """
    try:
        data = request.json
        visit_id = data.get('visit_id')
        duration = data.get('duration_seconds', 0)
        
        if not visit_id:
            return jsonify({"error": "visit_id required", "success": False}), 400
        
        visit = WebsiteVisit.query.get(visit_id)
        if visit:
            visit.duration_seconds = duration
            db.session.commit()
            return jsonify({"success": True, "updated": True})
        
        return jsonify({"success": False, "error": "Visit not found"}), 404
        
    except Exception as e:
        logger.error(f"Update duration error: {str(e)}")
        return jsonify({"error": str(e), "success": False}), 500


def format_duration(seconds):
    """Format seconds into human-readable duration."""
    if not seconds or seconds < 0:
        return "0s"
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    if hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"
