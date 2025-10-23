import sys
import logging
logging.basicConfig(stream=sys.stderr)
sys.path.insert(0, "/www/wwwroot/dadras")

from app import app as application
