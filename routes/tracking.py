from flask import Blueprint, request, jsonify
from database.models import db, User, BrowserActivity, DailySession
import uuid
from datetime import datetime, timedelta
import logging
from urllib.parse import urlparse

# Define the blueprint FIRST
tracking_bp = Blueprint('tracking', __name__)
logger = logging.getLogger(__name__)

@tracking_bp.route('/api/track/activity', methods=['POST'])
def track_activity():
    """Track browser activities"""
    try:
        data = request.json
        
        if not data or 'activity_type' not in data:
            return jsonify({"error": "Activity type is required"}), 400
        
        user_id = data.get('user_id', str(uuid.uuid4()))
        session_id = data.get('session_id', str(uuid.uuid4()))
        
        # Create or get user
        user = User.query.filter_by(user_id=user_id).first()
        if not user:
            user = User(user_id=user_id, session_id=session_id)
            db.session.add(user)
        
        # Extract domain from URL
        url = data.get('url', '')
        domain = ''
        if url:
            try:
                parsed_url = urlparse(url)
                domain = parsed_url.netloc
            except:
                pass
        
        # Create activity record
        activity = BrowserActivity(
            user_id=user_id,
            session_id=session_id,
            url=url,
            domain=domain,
            page_title=data.get('page_title', ''),
            activity_type=data['activity_type'],
            element_details=data.get('element_details', {}),
            duration_seconds=data.get('duration_seconds', 0)
        )
        
        db.session.add(activity)
        
        # Update daily session
        daily_session = DailySession.query.filter_by(session_id=session_id).first()
        if daily_session:
            if data['activity_type'] == 'page_visit':
                 daily_session.total_pages_visited = (daily_session.total_pages_visited or 0) + 1
            daily_session.total_interactions = (daily_session.total_interactions or 0) + 1
            daily_session.end_time = datetime.utcnow()
        else:
            daily_session = DailySession(
                session_id=session_id,
                user_id=user_id,
                start_time=datetime.utcnow(),
                end_time=datetime.utcnow(),
                total_pages_visited=1 if data['activity_type'] == 'page_visit' else 0,
                total_interactions=1
            )
            db.session.add(daily_session)
        
        db.session.commit()
        
        return jsonify({
            "success": True,
            "activity_id": activity.activity_id,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Tracking error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@tracking_bp.route('/api/track/summary/<user_id>', methods=['GET'])
def get_daily_summary(user_id):
    """Get daily summary for a user with more detailed data"""
    try:
        # Get today's date
        today = datetime.utcnow().date()
        start_of_day = datetime.combine(today, datetime.min.time())
        end_of_day = datetime.combine(today, datetime.max.time())
        
        # Also get yesterday's date for fallback
        yesterday = today - timedelta(days=1)
        start_of_yesterday = datetime.combine(yesterday, datetime.min.time())
        end_of_yesterday = datetime.combine(yesterday, datetime.max.time())
        
        # Also get 2 days ago for more fallback options
        two_days_ago = today - timedelta(days=2)
        start_of_two_days_ago = datetime.combine(two_days_ago, datetime.min.time())
        end_of_two_days_ago = datetime.combine(two_days_ago, datetime.max.time())
        
        # Log for debugging
        logger.info(f"Getting summary for user: {user_id}, today: {today}, yesterday: {yesterday}")
        
        # Get activities for today
        today_activities = BrowserActivity.query.filter(
            BrowserActivity.user_id == user_id,
            BrowserActivity.timestamp >= start_of_day,
            BrowserActivity.timestamp < end_of_day
        ).order_by(BrowserActivity.timestamp.desc()).all()
        
        # Get activities for yesterday (for fallback)
        yesterday_activities = BrowserActivity.query.filter(
            BrowserActivity.user_id == user_id,
            BrowserActivity.timestamp >= start_of_yesterday,
            BrowserActivity.timestamp < end_of_yesterday
        ).order_by(BrowserActivity.timestamp.desc()).all()
        
        # Get activities for 2 days ago (for fallback)
        two_days_ago_activities = BrowserActivity.query.filter(
            BrowserActivity.user_id == user_id,
            BrowserActivity.timestamp >= start_of_two_days_ago,
            BrowserActivity.timestamp < end_of_two_days_ago
        ).order_by(BrowserActivity.timestamp.desc()).all()
        
        logger.info(f"Found {len(today_activities)} activities today, {len(yesterday_activities)} activities yesterday, {len(two_days_ago_activities)} activities 2 days ago for user {user_id}")
        
        # Decide which activities to use for display
        # Priority: today -> yesterday -> 2 days ago
        if today_activities:
            display_activities = today_activities
            display_date = today
            is_today_data = True
            logger.info(f"Using TODAY's data for display ({len(today_activities)} activities)")
        elif yesterday_activities:
            display_activities = yesterday_activities
            display_date = yesterday
            is_today_data = False
            logger.info(f"Using YESTERDAY's data for display ({len(yesterday_activities)} activities)")
        elif two_days_ago_activities:
            display_activities = two_days_ago_activities
            display_date = two_days_ago
            is_today_data = False
            logger.info(f"Using 2 DAYS AGO data for display ({len(two_days_ago_activities)} activities)")
        else:
            # No recent activities at all
            display_activities = []
            display_date = today
            is_today_data = True
            logger.info(f"No recent activities found, using empty data")
        
        # Get ALL activities for this user for weekly data
        week_ago = today - timedelta(days=7)
        weekly_activities = BrowserActivity.query.filter(
            BrowserActivity.user_id == user_id,
            BrowserActivity.timestamp >= week_ago
        ).order_by(BrowserActivity.timestamp.asc()).all()
        
        # Get all activities for this user (for total counts)
        all_activities = BrowserActivity.query.filter_by(user_id=user_id).all()
        
        # Get daily session
        daily_session = DailySession.query.filter_by(user_id=user_id).first()
        
        # Calculate statistics
        domains_visited = {}
        activity_types_count = {}
        recent_activities = []
        
        for activity in display_activities[:20]:  # Only get recent 20 for display
            # Count domains
            if activity.domain:
                domains_visited[activity.domain] = domains_visited.get(activity.domain, 0) + 1
            
            # Count activity types
            activity_types_count[activity.activity_type] = activity_types_count.get(activity.activity_type, 0) + 1
            
            # Prepare recent activities for display
            recent_activities.append({
                "activity_type": activity.activity_type,
                "url": activity.url,
                "page_title": activity.page_title,
                "timestamp": activity.timestamp.isoformat(),
                "element_details": activity.element_details
            })
        
        # Calculate page visits (only page_visit activities)
        page_visits = sum(1 for a in display_activities if a.activity_type == 'page_visit')
        
        # Calculate total interactions (all activities)
        total_interactions = len(display_activities)
        
        # Calculate total time spent
        total_time_spent = sum(a.duration_seconds for a in display_activities)
        
        # Calculate average time per interaction
        avg_time_per_interaction = total_time_spent // (total_interactions or 1)
        
        # Calculate active days (last 7 days)
        active_days = db.session.query(
            db.func.DATE(BrowserActivity.timestamp).label('date')
        ).filter(
            BrowserActivity.user_id == user_id,
            BrowserActivity.timestamp >= week_ago,
            BrowserActivity.activity_type == 'page_visit'
        ).distinct().count()
        
        # Prepare daily activity for chart (last 7 days)
        daily_activity = []
        for i in range(7):
            day = today - timedelta(days=i)
            day_start = datetime.combine(day, datetime.min.time())
            day_end = datetime.combine(day, datetime.max.time())
            
            day_activities = [a for a in weekly_activities if day_start <= a.timestamp < day_end]
            day_page_visits = sum(1 for a in day_activities if a.activity_type == 'page_visit')
            day_interactions = len(day_activities)
            
            daily_activity.append({
                "date": day.isoformat(),
                "page_visits": day_page_visits,
                "interactions": day_interactions
            })
        
        # Sort daily activity by date (oldest to newest)
        daily_activity.sort(key=lambda x: x['date'])
        
        # If we have a daily session, use its values for totals (but only if we have real data)
        if daily_session and page_visits == 0 and total_interactions == 0:
            # If no activities found, use session data as fallback
            page_visits = daily_session.total_pages_visited or 0
            total_interactions = daily_session.total_interactions or 0
        
        # Ensure active_days is at least 1 if we have any page visits
        if page_visits > 0 and active_days == 0:
            active_days = 1
        
        summary = {
            "date": display_date.isoformat(),
            "is_today": is_today_data,
            "total_pages": page_visits,
            "page_visits": page_visits,
            "total_interactions": total_interactions,
            "interactions": total_interactions,
            "total_time_spent": total_time_spent,
            "avg_time_per_interaction": avg_time_per_interaction,
            "unique_domains": len(domains_visited),
            "active_days": max(active_days, 1),
            "domains_visited": domains_visited,
            "activity_breakdown": activity_types_count,
            "recent_activities": recent_activities,
            "daily_activity": daily_activity,
            "daily_session": {
                "start_time": daily_session.start_time.isoformat() if daily_session else None,
                "end_time": daily_session.end_time.isoformat() if daily_session else None,
                "total_pages_visited": daily_session.total_pages_visited if daily_session else 0,
                "total_interactions": daily_session.total_interactions if daily_session else 0
            } if daily_session else None
        }
        
        logger.info(f"Summary for user {user_id}: {page_visits} pages, {total_interactions} interactions (using {'today' if is_today_data else 'historical'} data from {display_date})")
        
        return jsonify({
            "success": True,
            "summary": summary,
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat(),
            "debug_info": {
                "using_today_data": is_today_data,
                "display_date": display_date.isoformat(),
                "today_activities_count": len(today_activities),
                "yesterday_activities_count": len(yesterday_activities),
                "two_days_ago_activities_count": len(two_days_ago_activities),
                "display_activities_count": len(display_activities),
                "all_activities_count": len(all_activities),
                "page_visits": page_visits,
                "interactions": total_interactions,
                "unique_domains": len(domains_visited),
                "active_days": active_days
            }
        })
        
    except Exception as e:
        logger.error(f"Summary error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            "success": False,
            "error": str(e),
            "summary": {
                "date": datetime.utcnow().date().isoformat(),
                "is_today": True,
                "total_pages": 0,
                "page_visits": 0,
                "total_interactions": 0,
                "interactions": 0,
                "total_time_spent": 0,
                "avg_time_per_interaction": 0,
                "unique_domains": 0,
                "active_days": 1,
                "recent_activities": [],
                "daily_activity": []
            }
        }), 500

@tracking_bp.route('/api/track/recent/<user_id>', methods=['GET'])
def get_recent_activities(user_id):
    """Get recent activities for a user"""
    try:
        limit = request.args.get('limit', 20, type=int)
        
        recent_activities = BrowserActivity.query.filter_by(
            user_id=user_id
        ).order_by(BrowserActivity.timestamp.desc()).limit(limit).all()
        
        activities_list = []
        for activity in recent_activities:
            activities_list.append({
                "activity_id": activity.activity_id,
                "activity_type": activity.activity_type,
                "url": activity.url,
                "page_title": activity.page_title,
                "domain": activity.domain,
                "timestamp": activity.timestamp.isoformat(),
                "element_details": activity.element_details,
                "duration_seconds": activity.duration_seconds
            })
        
        return jsonify({
            "success": True,
            "activities": activities_list,
            "count": len(activities_list)
        })
        
    except Exception as e:
        logger.error(f"Recent activities error: {str(e)}")
        return jsonify({"error": str(e)}), 500