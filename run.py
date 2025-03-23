import os
from main import app

if __name__ == '__main__':
    # Get port from environment variable or use default
    port = int(os.environ.get('SCHEDULER_PORT', 5006))
    
    # Get debug setting from environment variable
    debug_mode = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    # Run the Flask application
    app.run(host='0.0.0.0', port=port, debug=debug_mode)