import importlib.util
import os
import traceback

BASE = os.getcwd()
APP_PATH = os.path.join(BASE, 'app.py')
print('[diagnose] cwd =', BASE)
print('[diagnose] app.py =', APP_PATH)

try:
    spec = importlib.util.spec_from_file_location('app_module', APP_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError('cannot create spec for app.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    print('[diagnose] IMPORT_OK')
    app = getattr(mod, 'app', None)
    if app is None:
        print('[diagnose] Flask app not found as mod.app')
    else:
        try:
            routes = [str(r) for r in app.url_map.iter_rules()]
            print('[diagnose] routes =', routes)
        except Exception:
            print('[diagnose] app.url_map not available')
except Exception:
    print('[diagnose] IMPORT_ERR:')
    traceback.print_exc()

