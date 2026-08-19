import os
import sys

# Get the absolute path to the src directory
SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Make Django apps and config importable
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()