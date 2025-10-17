import os
import sys
import importlib.util

# Ensure project root is on sys.path
BASE_DIR = os.path.dirname(__file__)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Load the root-level app.py without clashing with the package named "app"
APP_MODULE_PATH = os.path.join(BASE_DIR, 'app.py')
spec = importlib.util.spec_from_file_location('app_root', APP_MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader, 'Cannot load app.py for Passenger'
spec.loader.exec_module(module)

# Expose Flask application for Phusion Passenger
application = getattr(module, 'app')


