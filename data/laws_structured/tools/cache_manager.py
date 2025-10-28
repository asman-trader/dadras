#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
مدیریت Cache برای بهبود سرعت
- File-based cache
- Memory cache
- LRU eviction
- Cache invalidation
"""

import json
import pickle
import hashlib
from pathlib import Path
from typing import Any, Optional
from functools import wraps
from datetime import datetime, timedelta
import time


class CacheManager:
    """مدیریت cache برای پارسر"""
    
    def __init__(self, cache_dir: str = '.cache', max_age_hours: int = 24):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.max_age = timedelta(hours=max_age_hours)
        
        # Memory cache
        self.memory_cache = {}
        self.cache_hits = 0
        self.cache_misses = 0
    
    def _get_cache_key(self, *args, **kwargs) -> str:
        """تولید کلید cache"""
        key_data = str(args) + str(sorted(kwargs.items()))
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _get_cache_file(self, key: str) -> Path:
        """مسیر فایل cache"""
        return self.cache_dir / f"{key}.cache"
    
    def get(self, key: str) -> Optional[Any]:
        """دریافت از cache"""
        
        # ابتدا memory cache
        if key in self.memory_cache:
            self.cache_hits += 1
            return self.memory_cache[key]['data']
        
        # سپس file cache
        cache_file = self._get_cache_file(key)
        
        if cache_file.exists():
            try:
                with open(cache_file, 'rb') as f:
                    cached = pickle.load(f)
                
                # بررسی اعتبار
                if datetime.now() - cached['timestamp'] < self.max_age:
                    self.cache_hits += 1
                    # اضافه به memory cache
                    self.memory_cache[key] = cached
                    return cached['data']
                else:
                    # منقضی شده
                    cache_file.unlink()
            
            except Exception:
                pass
        
        self.cache_misses += 1
        return None
    
    def set(self, key: str, data: Any):
        """ذخیره در cache"""
        
        cached = {
            'data': data,
            'timestamp': datetime.now()
        }
        
        # Memory cache
        self.memory_cache[key] = cached
        
        # File cache
        cache_file = self._get_cache_file(key)
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(cached, f)
        except Exception as e:
            print(f"⚠️  خطا در ذخیره cache: {e}")
    
    def invalidate(self, key: str = None):
        """حذف از cache"""
        
        if key:
            # حذف یک کلید خاص
            if key in self.memory_cache:
                del self.memory_cache[key]
            
            cache_file = self._get_cache_file(key)
            if cache_file.exists():
                cache_file.unlink()
        else:
            # حذف تمام cache
            self.memory_cache.clear()
            
            for cache_file in self.cache_dir.glob('*.cache'):
                try:
                    cache_file.unlink()
                except Exception:
                    pass
    
    def get_stats(self) -> dict:
        """آمار cache"""
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total_requests * 100) if total_requests > 0 else 0
        
        cache_files = list(self.cache_dir.glob('*.cache'))
        total_size = sum(f.stat().st_size for f in cache_files)
        
        return {
            'hits': self.cache_hits,
            'misses': self.cache_misses,
            'hit_rate': f"{hit_rate:.1f}%",
            'memory_items': len(self.memory_cache),
            'file_items': len(cache_files),
            'total_size_mb': total_size / (1024 * 1024)
        }
    
    def print_stats(self):
        """چاپ آمار"""
        stats = self.get_stats()
        
        print("\n📊 آمار Cache:")
        print("="*50)
        print(f"✅ Hits: {stats['hits']}")
        print(f"❌ Misses: {stats['misses']}")
        print(f"📈 Hit Rate: {stats['hit_rate']}")
        print(f"💾 Memory Items: {stats['memory_items']}")
        print(f"📁 File Items: {stats['file_items']}")
        print(f"💽 Total Size: {stats['total_size_mb']:.2f} MB")
        print("="*50)


def cached(cache_manager: CacheManager):
    """دکوراتور cache"""
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # تولید کلید
            key = cache_manager._get_cache_key(func.__name__, *args, **kwargs)
            
            # جستجو در cache
            result = cache_manager.get(key)
            
            if result is not None:
                return result
            
            # اجرای تابع
            result = func(*args, **kwargs)
            
            # ذخیره در cache
            cache_manager.set(key, result)
            
            return result
        
        return wrapper
    return decorator


class SmartCache:
    """Cache هوشمند با الگوریتم LRU"""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.cache = {}
        self.access_times = {}
        self.access_counts = {}
    
    def get(self, key: str) -> Optional[Any]:
        """دریافت با به‌روزرسانی access time"""
        if key in self.cache:
            self.access_times[key] = time.time()
            self.access_counts[key] = self.access_counts.get(key, 0) + 1
            return self.cache[key]
        return None
    
    def set(self, key: str, value: Any):
        """ذخیره با eviction در صورت نیاز"""
        
        # اگر پر شد، حذف LRU
        if len(self.cache) >= self.max_size and key not in self.cache:
            self._evict_lru()
        
        self.cache[key] = value
        self.access_times[key] = time.time()
        self.access_counts[key] = 1
    
    def _evict_lru(self):
        """حذف کمترین استفاده شده"""
        if not self.cache:
            return
        
        # پیدا کردن قدیمی‌ترین
        lru_key = min(self.access_times, key=self.access_times.get)
        
        del self.cache[lru_key]
        del self.access_times[lru_key]
        del self.access_counts[lru_key]
    
    def get_hot_keys(self, top_n: int = 10) -> list:
        """کلیدهای پرکاربرد"""
        sorted_keys = sorted(
            self.access_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_keys[:top_n]
    
    def clear(self):
        """پاک کردن cache"""
        self.cache.clear()
        self.access_times.clear()
        self.access_counts.clear()


class PreComputedCache:
    """Cache از پیش محاسبه شده برای مواد پرکاربرد"""
    
    def __init__(self, precompute_file: str = 'precomputed.json'):
        self.precompute_file = Path(precompute_file)
        self.data = self._load()
    
    def _load(self) -> dict:
        """بارگذاری cache از پیش محاسبه شده"""
        if self.precompute_file.exists():
            try:
                with open(self.precompute_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}
    
    def precompute_common_articles(self, article_numbers: list, 
                                   law_code: str, data_dir: Path):
        """محاسبه از پیش برای مواد پرکاربرد"""
        
        print(f"⚙️  محاسبه از پیش {len(article_numbers)} ماده...")
        
        # بارگذاری و ذخیره مواد
        for num in article_numbers:
            # جستجو در فایل‌ها
            for json_file in data_dir.rglob('articles_*.json'):
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        articles = json.load(f)
                    
                    for article in articles:
                        if article.get('article_number') == num:
                            key = f"{law_code}_{num}"
                            self.data[key] = article
                            print(f"  ✅ ماده {num}")
                            break
                except Exception:
                    continue
        
        # ذخیره
        self._save()
    
    def _save(self):
        """ذخیره cache"""
        with open(self.precompute_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def get_article(self, law_code: str, article_number: int) -> Optional[dict]:
        """دریافت سریع ماده"""
        key = f"{law_code}_{article_number}"
        return self.data.get(key)


def main():
    """تست cache manager"""
    
    print("🧪 تست Cache Manager\n")
    
    # تست CacheManager
    cache = CacheManager(cache_dir='.cache_test', max_age_hours=1)
    
    # ذخیره
    cache.set('test1', {'data': 'value1'})
    cache.set('test2', [1, 2, 3, 4, 5])
    
    # دریافت
    print("Get test1:", cache.get('test1'))
    print("Get test2:", cache.get('test2'))
    print("Get test3 (not exist):", cache.get('test3'))
    
    # آمار
    cache.print_stats()
    
    # تست SmartCache
    print("\n🧠 تست Smart Cache\n")
    smart = SmartCache(max_size=3)
    
    smart.set('a', 1)
    smart.set('b', 2)
    smart.set('c', 3)
    
    # دسترسی
    smart.get('a')
    smart.get('a')
    smart.get('b')
    
    # اضافه کردن d -> باید a یا c حذف شود
    smart.set('d', 4)
    
    print("Hot keys:", smart.get_hot_keys())
    
    # پاکسازی
    cache.invalidate()
    print("\n✅ Cache پاک شد")


if __name__ == '__main__':
    main()

