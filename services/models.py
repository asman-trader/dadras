import os

def str_to_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on', 'y')

llama_instance = None
llama_error_message = None

def load_llama():
    global llama_instance, llama_error_message
    if llama_instance is not None:
        return llama_instance
    try:
        from llama_cpp import Llama
    except Exception as exc:
        llama_error_message = "کتابخانه llama-cpp-python نصب نیست. نصب: pip install llama-cpp-python"
        return None
    model_path = os.getenv('LLAMA_MODEL')
    if not model_path or not os.path.exists(model_path):
        llama_error_message = "مسیر مدل LLAMA_MODEL تنظیم/موجود نیست. یک فایل .gguf معتبر مشخص کنید."
        return None
    def _as_int(env_name, default_val):
        try:
            return int(os.getenv(env_name, str(default_val)))
        except ValueError:
            return default_val
    n_ctx = _as_int('LLAMA_CTX', 4096)
    n_threads = _as_int('LLAMA_THREADS', max(1, (os.cpu_count() or 4)))
    n_gpu_layers = _as_int('LLAMA_N_GPU_LAYERS', 0)
    try:
        kwargs = { 'model_path': model_path, 'n_ctx': n_ctx, 'n_threads': n_threads }
        if n_gpu_layers > 0:
            kwargs['n_gpu_layers'] = n_gpu_layers
        llama_instance = Llama(**kwargs)
        llama_error_message = None
        return llama_instance
    except Exception as exc:
        llama_error_message = f"خطا در بارگذاری مدل: {exc}"
        return None


