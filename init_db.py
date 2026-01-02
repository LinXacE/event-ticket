from app import app, db
from models import User, Event, PassType, EventPass, ValidationLog, EventAnalytics
from flask_bcrypt import Bcrypt

bcrypt = Bcrypt(app)

with app.app_context():
    db.create_all()
    # Create a test admin user
    if not User.query.filter_by(username='admin').first():
        hashed_password = bcrypt.generate_password_hash('admin').decode('utf-8')
        user = User(
            username='admin',
            email='admin@example.com',
            password_hash=hashed_password,
            full_name='Admin User',
            role='admin'
        )
        db.session.add(user)
        db.session.commit()
        print("Admin user created")
    
    print("Database tables created successfully!")
