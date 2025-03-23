# Planit Scheduler Microservice

A Flask-based microservice that monitors tasks with approaching deadlines and sends time-sensitive notifications at specific intervals.

## Overview

The Scheduler microservice is responsible for:

1. Monitoring tasks with approaching deadlines in MongoDB
2. Sending notifications at specific intervals (12h, 6h, 1h before deadline, and at deadline)
3. Tracking which notifications have been sent to avoid duplicates
4. Forwarding notification data to the messaging queue service
5. Providing health check endpoints for monitoring

## Folder Structure

```
scheduler/
├── main.py                 # Main Flask application with APScheduler
├── run.py                  # Script to run the service
├── Dockerfile              # Docker configuration
├── requirements.txt        # Python dependencies
└── .env.example            # Example environment configuration
```

## Requirements

- Python 3.9 or higher
- Flask 2.2.3
- Flask-APScheduler 1.12.4
- Flask-PyMongo 2.3.0
- Requests 2.28.2
- Python-dateutil 2.8.2
- MongoDB instance
- Messaging Queue Service

## Configuration

The service is configured using environment variables:

- `MONGO_URI`: MongoDB connection URI (default: `mongodb://localhost:27017/planit`)
- `MESSAGING_QUEUE_URL`: URL for the messaging queue service (default: `http://messaging_queue:5001/queue`)
- `MESSAGING_QUEUE_HEALTH_URL`: Health check URL for the messaging queue (default: `http://messaging_queue:5001/health`)
- `SCHEDULER_PORT`: Port for the Flask application (default: `5006`)
- `SCHEDULER_CHECK_INTERVAL`: Minutes between scheduled checks (default: `15`)
- `DEBUG`: Debug mode flag (default: `False`)

## API Endpoints

1. `/` - Basic service information
   - Method: GET
   - Response: Service name, status, and version

2. `/health` - Health check endpoint
   - Method: GET
   - Response: Status of MongoDB connection, APScheduler, and messaging queue

3. `/trigger` - Manually trigger notification checks
   - Method: POST
   - Response: Result of the notification check process

## How It Works

1. The service runs continuously with APScheduler executing checks every 15 minutes (configurable)
2. During each check, it:
   - Queries MongoDB for tasks approaching each notification threshold (12h, 6h, 1h, deadline)
   - For tasks needing notification, sends requests to the messaging queue
   - Updates MongoDB to mark that the notification was sent
3. The health check endpoint provides status for monitoring
4. The trigger endpoint allows manual execution of the check process

## Running Locally

1. Clone the repository
2. Create a `.env` file based on `.env.example` with your configuration
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Run the service:
   ```
   python run.py
   ```

## Running with Docker

1. Build the Docker image:
   ```
   docker build -t planit-scheduler .
   ```

2. Run the container:
   ```
   docker run -p 5006:5006 --env-file .env planit-scheduler
   ```

## MongoDB Schema Requirements

The service expects the following structure for task documents in MongoDB:

```json
{
  "_id": "ObjectId",
  "name": "Task name",
  "description": "Task description",
  "user_id": "User ID",
  "deadline": "2023-04-15T14:00:00Z",
  "status": "pending",
  "type": "task",  // or "meeting"
  "notifications_sent": ["12h", "6h"],  // Thresholds already notified
  "attendees": [],  // For meetings only
  "location": ""    // For meetings only
}
```

## Notification Payload Format

The service sends notifications to the messaging queue in the following format:

```json
{
  "type": "deadline_approaching",  // or "meeting_approaching"
  "user_id": "User ID",
  "task_id": "Task ID",
  "task_name": "Task name",
  "due_date": "2023-04-15T14:00:00Z",
  "hours_remaining": 5.8,
  "notification_threshold": "6h",  // "12h", "6h", "1h", or "deadline"
  "priority": "medium"  // "high" for 1h and deadline notifications
}
```

For meetings, additional fields are included:
```json
{
  "attendees": ["User1", "User2"],
  "location": "Meeting Room 3"
}
```