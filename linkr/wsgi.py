"""
WSGI config for linkr project.
"""

import os
import sys

# Add your project directory to the sys.path
path = '/home/johnmos/links.ai-dnas.com'
if path not in sys.path:
    sys.path.append(path)

# Add the project's parent directory to the sys.path
path = '/home/johnmos'
if path not in sys.path:
    sys.path.append(path)

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'linkr.settings')
os.environ['DJANGO_DEBUG'] = 'False'

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    load_dotenv(env_path)
except ImportError:
    pass

application = get_wsgi_application()
