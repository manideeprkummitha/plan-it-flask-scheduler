FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py run.py ./

# Set environment variables (these can be overridden at runtime)
ENV MONGO_URI=mongodb://localhost:27017/planit
ENV MESSAGING_QUEUE_URL=http://messaging_queue:5001/queue
ENV MESSAGING_QUEUE_HEALTH_URL=http://messaging_queue:5001/health
ENV SCHEDULER_PORT=5006
ENV SCHEDULER_CHECK_INTERVAL=15
ENV DEBUG=False

# Expose the port the app runs on
EXPOSE 5006

# Command to run the application
CMD ["python", "run.py"]