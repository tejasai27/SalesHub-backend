import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from database.models import db

app = create_app()

with app.app_context():
    print("Creating database tables...")
    db.create_all()
    print("Database tables created successfully!")
    
    # Create initial admin user if needed
    from database.models import User
    import uuid
    
    admin_user = User.query.filter_by(user_id='admin').first()
    if not admin_user:
        admin_user = User(
            user_id='admin',
            session_id=str(uuid.uuid4())
        )
        db.session.add(admin_user)
        db.session.commit()
        print("Admin user created!")
    
    print("Database initialization complete!")