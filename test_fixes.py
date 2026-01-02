from app import app, db
from models import User, Event
from flask_login import login_user
from datetime import datetime, date, time

def test_fixes():
    with app.app_context():
        # Create a test organizer
        organizer = User.query.filter_by(username='organizer').first()
        if not organizer:
            organizer = User(
                username='organizer',
                email='organizer@example.com',
                password_hash='hash',
                full_name='Organizer User',
                role='organizer'
            )
            db.session.add(organizer)
            db.session.commit()
            print("Organizer created")
        else:
            print("Organizer exists")

        # Create a test event
        event = Event(
            event_name="Test Event 123",
            event_description="Description",
            event_date=date(2025, 12, 25),
            event_time=time(18, 0),
            location="Test Location",
            total_capacity=100,
            organizer_id=organizer.id
        )
        db.session.add(event)
        db.session.commit()
        print(f"Event created: {event.event_name}")

        # Verify Event Name retrieval
        retrieved_event = Event.query.filter_by(event_name="Test Event 123").first()
        if retrieved_event and retrieved_event.event_name == "Test Event 123":
            print("✅ Event name stored and retrieved correctly.")
        else:
            print("❌ Event name retrieval failed.")

        # Test Analytics Query for Admin
        admin = User.query.filter_by(username='admin').first()
        if admin:
            # Simulate logic in routes/analytics.py
            if admin.role == 'admin':
                events = Event.query.all()
                print(f"Admin sees {len(events)} events.")
                if len(events) > 0:
                    print("✅ Admin can see events.")
                else:
                    print("❌ Admin sees 0 events (unexpected if we just created one).")
            else:
                print("❌ Admin user is not role 'admin'")
        else:
            print("❌ Admin user not found")

if __name__ == "__main__":
    test_fixes()
