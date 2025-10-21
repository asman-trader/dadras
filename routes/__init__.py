from .admin import admin_bp
from .admin_api import admin_api_bp
from .admin_logs import admin_logs_bp
from .notes import notes_bp
from .chats import chats_bp
from .auth import auth_bp
from .laws import laws_bp

all_blueprints = [admin_bp, admin_api_bp, admin_logs_bp, notes_bp, chats_bp, auth_bp, laws_bp]

