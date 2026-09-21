import os
import logging

# Ensure logs directory exists within project directory
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(_current_dir)))
log_dir = os.path.join(_project_root, 'logs', 'crawler_logs')
if not os.path.isdir(log_dir):
    os.makedirs(log_dir, exist_ok=True)

# Configure root logger
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# Create handlers
c_handler = logging.StreamHandler()
f_handler = logging.FileHandler(os.path.join(log_dir, 'debug.log'), mode='a')

# Set levels
c_handler.setLevel(logging.INFO)
f_handler.setLevel(logging.INFO) # Set back to INFO for production-like state

# Create formatters and add it to handlers
log_format = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
c_handler.setFormatter(log_format)
f_handler.setFormatter(log_format)

# Add handlers to the logger
logger.addHandler(c_handler)
logger.addHandler(f_handler)
