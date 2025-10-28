#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
نظارت بر عملکرد سیستم
- Profiling
- Memory tracking
- Speed benchmarking
- Resource monitoring
"""

import time
import psutil
import os
from functools import wraps
from typing import Dict, List
from datetime import datetime
import json


class PerformanceMonitor:
    """کلاس نظارت بر عملکرد"""
    
    def __init__(self):
        self.metrics = []
        self.start_time = None
        self.process = psutil.Process(os.getpid())
    
    def start(self):
        """شروع نظارت"""
        self.start_time = time.time()
        self.start_memory = self.process.memory_info().rss / 1024 / 1024  # MB
    
    def stop(self) -> Dict:
        """پایان و گزارش"""
        if self.start_time is None:
            return {}
        
        elapsed = time.time() - self.start_time
        current_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        memory_used = current_memory - self.start_memory
        
        cpu_percent = self.process.cpu_percent()
        
        metric = {
            'timestamp': datetime.now().isoformat(),
            'elapsed_seconds': elapsed,
            'memory_used_mb': memory_used,
            'current_memory_mb': current_memory,
            'cpu_percent': cpu_percent
        }
        
        self.metrics.append(metric)
        self.start_time = None
        
        return metric
    
    def get_system_info(self) -> Dict:
        """اطلاعات سیستم"""
        return {
            'cpu_count': psutil.cpu_count(),
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_total_gb': psutil.virtual_memory().total / 1024 / 1024 / 1024,
            'memory_available_gb': psutil.virtual_memory().available / 1024 / 1024 / 1024,
            'memory_percent': psutil.virtual_memory().percent,
            'disk_usage_percent': psutil.disk_usage('/').percent
        }
    
    def print_summary(self):
        """چاپ خلاصه"""
        if not self.metrics:
            print("هیچ متریکی ثبت نشده")
            return
        
        total_time = sum(m['elapsed_seconds'] for m in self.metrics)
        total_memory = sum(m['memory_used_mb'] for m in self.metrics)
        avg_cpu = sum(m['cpu_percent'] for m in self.metrics) / len(self.metrics)
        
        print("\n📊 خلاصه عملکرد:")
        print("="*60)
        print(f"⏱️  زمان کل: {total_time:.2f} ثانیه")
        print(f"💾 حافظه استفاده شده: {total_memory:.2f} MB")
        print(f"🖥️  میانگین CPU: {avg_cpu:.1f}%")
        print(f"📈 تعداد عملیات: {len(self.metrics)}")
        print("="*60)
    
    def save_report(self, filename: str = 'performance_report.json'):
        """ذخیره گزارش"""
        report = {
            'system_info': self.get_system_info(),
            'metrics': self.metrics,
            'summary': {
                'total_operations': len(self.metrics),
                'total_time': sum(m['elapsed_seconds'] for m in self.metrics),
                'total_memory': sum(m['memory_used_mb'] for m in self.metrics),
            }
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"✅ گزارش در {filename} ذخیره شد")


def profile_function(monitor: PerformanceMonitor = None):
    """دکوراتور profiling"""
    
    if monitor is None:
        monitor = PerformanceMonitor()
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            monitor.start()
            result = func(*args, **kwargs)
            metric = monitor.stop()
            
            print(f"\n⚡ {func.__name__}:")
            print(f"  ⏱️  {metric['elapsed_seconds']:.3f}s")
            print(f"  💾 {metric['memory_used_mb']:.2f} MB")
            print(f"  🖥️  {metric['cpu_percent']:.1f}% CPU")
            
            return result
        return wrapper
    return decorator


class SpeedBenchmark:
    """بنچمارک سرعت"""
    
    @staticmethod
    def compare_parsers(test_file: str, iterations: int = 5):
        """مقایسه سرعت پارسرهای مختلف"""
        
        print(f"🏁 مقایسه پارسرها با {iterations} تکرار\n")
        
        results = {}
        
        # تست پارسر عادی
        try:
            from law_parser import LawParser
            
            print("📊 تست پارسر عادی...")
            times = []
            
            for i in range(iterations):
                parser = LawParser()
                start = time.time()
                articles = parser.parse_file(test_file, 'test', 'test')
                elapsed = time.time() - start
                times.append(elapsed)
                print(f"  دور {i+1}: {elapsed:.3f}s")
            
            results['normal'] = {
                'avg': sum(times) / len(times),
                'min': min(times),
                'max': max(times)
            }
        except ImportError:
            results['normal'] = None
        
        # تست پارسر سریع
        try:
            from law_parser_fast import FastLawParser
            
            print("\n⚡ تست پارسر سریع...")
            times = []
            
            for i in range(iterations):
                parser = FastLawParser()
                start = time.time()
                articles = list(parser.parse_file_fast(test_file, 'test', 'test'))
                elapsed = time.time() - start
                times.append(elapsed)
                print(f"  دور {i+1}: {elapsed:.3f}s")
            
            results['fast'] = {
                'avg': sum(times) / len(times),
                'min': min(times),
                'max': max(times)
            }
        except ImportError:
            results['fast'] = None
        
        # مقایسه
        print("\n" + "="*60)
        print("📊 نتایج مقایسه:")
        print("="*60)
        
        if results.get('normal') and results.get('fast'):
            speedup = results['normal']['avg'] / results['fast']['avg']
            
            print(f"پارسر عادی:")
            print(f"  میانگین: {results['normal']['avg']:.3f}s")
            print(f"  کمترین: {results['normal']['min']:.3f}s")
            print(f"  بیشترین: {results['normal']['max']:.3f}s")
            
            print(f"\nپارسر سریع:")
            print(f"  میانگین: {results['fast']['avg']:.3f}s")
            print(f"  کمترین: {results['fast']['min']:.3f}s")
            print(f"  بیشترین: {results['fast']['max']:.3f}s")
            
            print(f"\n🚀 افزایش سرعت: {speedup:.2f}x")
        
        print("="*60)
        
        return results


class MemoryProfiler:
    """پروفایلر حافظه"""
    
    def __init__(self):
        self.snapshots = []
    
    def take_snapshot(self, label: str = ""):
        """گرفتن عکس از وضعیت حافظه"""
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        
        snapshot = {
            'label': label,
            'timestamp': time.time(),
            'rss_mb': memory_info.rss / 1024 / 1024,
            'vms_mb': memory_info.vms / 1024 / 1024,
        }
        
        self.snapshots.append(snapshot)
        return snapshot
    
    def print_report(self):
        """گزارش حافظه"""
        if len(self.snapshots) < 2:
            print("حداقل دو snapshot نیاز است")
            return
        
        print("\n💾 گزارش حافظه:")
        print("="*60)
        
        for i, snap in enumerate(self.snapshots):
            print(f"{i+1}. {snap['label']}: {snap['rss_mb']:.2f} MB")
            
            if i > 0:
                diff = snap['rss_mb'] - self.snapshots[i-1]['rss_mb']
                print(f"   تغییر: {diff:+.2f} MB")
        
        total_diff = self.snapshots[-1]['rss_mb'] - self.snapshots[0]['rss_mb']
        print(f"\n📈 تغییر کل: {total_diff:+.2f} MB")
        print("="*60)


def main():
    """تست ابزار"""
    
    print("🧪 تست Performance Monitor\n")
    
    # تست PerformanceMonitor
    monitor = PerformanceMonitor()
    
    print("📊 اطلاعات سیستم:")
    sys_info = monitor.get_system_info()
    for key, value in sys_info.items():
        print(f"  {key}: {value}")
    
    # تست profiling
    @profile_function(monitor)
    def test_function():
        # عملیات تستی
        data = [i**2 for i in range(1000000)]
        return sum(data)
    
    print("\n🔬 تست Profiling:")
    result = test_function()
    
    # خلاصه
    monitor.print_summary()
    
    # تست MemoryProfiler
    print("\n💾 تست Memory Profiler:")
    mem_prof = MemoryProfiler()
    
    mem_prof.take_snapshot("شروع")
    
    # اضافه کردن داده
    data = [i for i in range(1000000)]
    mem_prof.take_snapshot("بعد از ایجاد لیست")
    
    data = None
    mem_prof.take_snapshot("بعد از پاک کردن")
    
    mem_prof.print_report()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ متوقف شد")

