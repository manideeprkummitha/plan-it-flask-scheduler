import os
import logging
import datetime
from flask import Flask, jsonify, request
from flask_apscheduler import APScheduler
from flask_pymongo import PyMongo
import requests
from datetime import datetime, timedelta
from dateutil import parser

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('scheduler')

# Initialize Flask app
app = Flask(__name__)

# Load configuration from environment variables
app.config['MONGO_URI'] = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/planit')
messaging_queue_url = os.environ.get('MESSAGING_QUEUE_URL', 'http://messaging_queue:5001/queue')
messaging_queue_health_url = os.environ.get('MESSAGING_QUEUE_HEALTH_URL', 'http://messaging_queue:5001/health')
scheduler_check_interval = int(os.environ.get('SCHEDULER_CHECK_INTERVAL', 15))
debug_mode = os.environ.get('DEBUG', 'False').lower() == 'true'

# Configure MongoDB
mongo = PyMongo(app)

# Initialize scheduler
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.api_enabled = True

# Notification thresholds in hours
NOTIFICATION_THRESHOLDS = [12, 6, 1, 0]  # 0 represents the deadline

def is_messaging_queue_reachable():
    """Check if the messaging queue service is reachable"""
    try:
        response = requests.get(messaging_queue_health_url, timeout=5)
        return response.status_code == 200
    except requests.RequestException as e:
        logger.error(f"Failed to connect to messaging queue: {str(e)}")
        return False

def send_notification(notification_data):
    """Send notification to the messaging queue"""
    try:
        response = requests.post(
            messaging_queue_url, 
            json=notification_data,
            timeout=5
        )
        if response.status_code == 200:
            logger.info(f"Notification sent for task: {notification_data['task_id']}")
            return True
        else:
            logger.error(f"Failed to send notification: {response.status_code} - {response.text}")
            return False
    except requests.RequestException as e:
        logger.error(f"Error sending notification: {str(e)}")
        return False

def mark_notification_sent(task_id, threshold):
    """Mark that a notification has been sent for a specific threshold"""
    try:
        result = mongo.db.tasks.update_one(
            {"_id": task_id},
            {"$addToSet": {"notifications_sent": threshold}}
        )
        return result.modified_count > 0
    except Exception as e:
        logger.error(f"Failed to mark notification as sent: {str(e)}")
        return False

def check_and_send_notifications(threshold_hours):
    """Check for tasks approaching the given threshold and send notifications"""
    logger.info(f"Checking for tasks approaching {threshold_hours} hour threshold")
    
    # Calculate the time range for this threshold
    now = datetime.utcnow()
    
    if threshold_hours == 0:
        # For deadline notifications, find tasks due within the next 15 minutes
        start_time = now
        end_time = now + timedelta(minutes=scheduler_check_interval)
        threshold_name = "deadline"
    else:
        # For other thresholds, find tasks that will hit the threshold in the next 15 minutes
        start_time = now + timedelta(hours=threshold_hours) - timedelta(minutes=scheduler_check_interval)
        end_time = now + timedelta(hours=threshold_hours)
        threshold_name = f"{threshold_hours}h"

    try:
        # Query for tasks that are approaching the notification threshold and haven't been notified yet
        tasks = mongo.db.tasks.find({
            "deadline": {"$gte": start_time, "$lte": end_time},
            "status": {"$ne": "completed"},
            "notifications_sent": {"$nin": [threshold_name]}
        })

        notification_count = 0
        for task in tasks:
            # Calculate hours remaining
            deadline = task.get('deadline')
            if isinstance(deadline, str):
                deadline = parser.parse(deadline)
            
            hours_remaining = (deadline - now).total_seconds() / 3600
            
            # Prepare notification data
            notification_data = {
                "type": "deadline_approaching",
                "user_id": task.get('user_id'),
                "task_id": str(task.get('_id')),
                "task_name": task.get('name'),
                "due_date": deadline.isoformat(),
                "hours_remaining": round(hours_remaining, 1),
                "notification_threshold": threshold_name,
                "priority": "high" if threshold_hours <= 1 else "medium"
            }
            
            # Special handling for meeting-specific data
            if task.get('type') == 'meeting':
                notification_data["type"] = "meeting_approaching"
                notification_data["attendees"] = task.get('attendees', [])
                notification_data["location"] = task.get('location', '')
            
            # Send notification
            if send_notification(notification_data):
                # Mark notification as sent
                mark_notification_sent(task.get('_id'), threshold_name)
                notification_count += 1
        
        logger.info(f"Sent {notification_count} notifications for {threshold_name} threshold")
        return notification_count
    
    except Exception as e:
        logger.error(f"Error checking tasks for {threshold_name} threshold: {str(e)}")
        return 0

@scheduler.task('interval', id='notification_check', minutes=scheduler_check_interval, misfire_grace_time=120)
def scheduled_notification_check():
    """Scheduled job to check for all notification thresholds"""
    logger.info("Running scheduled notification check")
    
    total_notifications = 0
    for threshold in NOTIFICATION_THRESHOLDS:
        count = check_and_send_notifications(threshold)
        total_notifications += count
    
    logger.info(f"Completed scheduled check. Sent {total_notifications} notifications.")
    return total_notifications

@app.route('/')
def index():
    """Basic service information endpoint"""
    return jsonify({
        "service": "Planit Scheduler",
        "status": "running",
        "version": "1.0.0"
    })

@app.route('/health')
def health_check():
    """Health check endpoint"""
    mongo_status = True
    try:
        # Check MongoDB connection
        mongo.db.command('ping')
    except Exception as e:
        mongo_status = False
        logger.error(f"MongoDB health check failed: {str(e)}")
    
    # Check if scheduler is running
    scheduler_status = scheduler.running

    # Check messaging queue connection
    messaging_queue_status = is_messaging_queue_reachable()
    
    # Overall status is healthy if all components are working
    overall_status = mongo_status and scheduler_status and messaging_queue_status
    
    return jsonify({
        "status": "healthy" if overall_status else "unhealthy",
        "components": {
            "mongodb": "connected" if mongo_status else "disconnected",
            "scheduler": "running" if scheduler_status else "stopped",
            "messaging_queue": "reachable" if messaging_queue_status else "unreachable"
        },
        "timestamp": datetime.utcnow().isoformat()
    }), 200 if overall_status else 503

@app.route('/trigger', methods=['POST'])
def trigger_check():
    """Manually trigger notification check"""
    logger.info("Manual trigger initiated")
    
    try:
        total_notifications = scheduled_notification_check()
        return jsonify({
            "status": "success",
            "message": f"Notification check completed. Sent {total_notifications} notifications.",
            "timestamp": datetime.utcnow().isoformat()
        })
    except Exception as e:
        logger.error(f"Error during manual trigger: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Failed to complete notification check: {str(e)}",
            "timestamp": datetime.utcnow().isoformat()
        }), 500

if __name__ == '__main__':
    # Start the scheduler
    scheduler.start()
    logger.info("Scheduler started")
    
    # Start the Flask app
    port = int(os.environ.get('SCHEDULER_PORT', 5006))
    app.run(host='0.0.0.0', port=port, debug=debug_mode)