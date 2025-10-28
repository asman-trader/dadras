#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CLI سریع با تمام بهینه‌سازی‌ها
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from law_parser_fast import FastLawParser, MemoryMappedParser
from batch_processor_fast import FastBatchProcessor, StreamProcessor
from cache_manager import CacheManager, SmartCache
from performance_monitor import PerformanceMonitor, SpeedBenchmark


class FastCLI:
    """CLI بهینه‌شده"""
    
    def __init__(self):
        self.monitor = PerformanceMonitor()
        self.cache = CacheManager()
    
    def parse_fast(self, input_file: str, law_code: str, category: str, output_dir: str):
        """پارس سریع"""
        print(f"⚡ پارس سریع: {input_file}\n")
        
        self.monitor.start()
        
        parser = FastLawParser()
        parser.parse_and_save_fast(input_file, output_dir, law_code, category)
        
        metric = self.monitor.stop()
        
        print(f"\n✅ انجام شد:")
        print(f"  ⏱️  {metric['elapsed_seconds']:.2f} ثانیه")
        print(f"  💾 {metric['memory_used_mb']:.2f} MB حافظه")
        print(f"  🖥️  {metric['cpu_percent']:.1f}% CPU")
    
    def batch_fast(self, workers: int = None):
        """پردازش دسته‌ای سریع"""
        print(f"⚡ پردازش دسته‌ای سریع\n")
        
        self.monitor.start()
        
        processor = FastBatchProcessor(num_workers=workers)
        processor.process_all_parallel()
        
        metric = self.monitor.stop()
        
        print(f"\n✅ انجام شد:")
        print(f"  ⏱️  {metric['elapsed_seconds']:.2f} ثانیه")
        print(f"  💾 {metric['memory_used_mb']:.2f} MB حافظه")
    
    def stream_fast(self, input_file: str, output_dir: str, law_code: str):
        """پردازش جریانی"""
        print(f"🌊 پردازش جریانی: {input_file}\n")
        
        self.monitor.start()
        
        StreamProcessor.process_stream(input_file, output_dir, law_code)
        
        metric = self.monitor.stop()
        
        print(f"\n✅ انجام شد:")
        print(f"  ⏱️  {metric['elapsed_seconds']:.2f} ثانیه")
    
    def benchmark(self, test_file: str, iterations: int = 5):
        """بنچمارک سرعت"""
        if not Path(test_file).exists():
            print(f"❌ فایل تست یافت نشد: {test_file}")
            return
        
        SpeedBenchmark.compare_parsers(test_file, iterations)
    
    def cache_stats(self):
        """آمار cache"""
        self.cache.print_stats()
    
    def cache_clear(self):
        """پاک کردن cache"""
        self.cache.invalidate()
        print("✅ Cache پاک شد")
    
    def system_info(self):
        """اطلاعات سیستم"""
        info = self.monitor.get_system_info()
        
        print("\n🖥️  اطلاعات سیستم:")
        print("="*50)
        print(f"CPU Cores: {info['cpu_count']}")
        print(f"CPU Usage: {info['cpu_percent']}%")
        print(f"Memory Total: {info['memory_total_gb']:.2f} GB")
        print(f"Memory Available: {info['memory_available_gb']:.2f} GB")
        print(f"Memory Usage: {info['memory_percent']}%")
        print(f"Disk Usage: {info['disk_usage_percent']}%")
        print("="*50)


def main():
    """تابع اصلی"""
    
    parser = argparse.ArgumentParser(
        description='🚀 CLI سریع با تمام بهینه‌سازی‌ها',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
مثال‌های استفاده:
  %(prog)s parse-fast input.txt civil_law معاملات output/
  %(prog)s batch-fast --workers 8
  %(prog)s stream input.txt output/ law_code
  %(prog)s benchmark test.txt --iterations 10
  %(prog)s cache-stats
  %(prog)s system-info
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='دستورات')
    
    # Parse Fast
    parse_parser = subparsers.add_parser('parse-fast', help='پارس سریع')
    parse_parser.add_argument('input', help='فایل ورودی')
    parse_parser.add_argument('law_code', help='کد قانون')
    parse_parser.add_argument('category', help='دسته')
    parse_parser.add_argument('output', help='پوشه خروجی')
    
    # Batch Fast
    batch_parser = subparsers.add_parser('batch-fast', help='پردازش دسته‌ای سریع')
    batch_parser.add_argument('--workers', '-w', type=int, help='تعداد workers')
    
    # Stream
    stream_parser = subparsers.add_parser('stream', help='پردازش جریانی')
    stream_parser.add_argument('input', help='فایل ورودی')
    stream_parser.add_argument('output', help='پوشه خروجی')
    stream_parser.add_argument('law_code', help='کد قانون')
    
    # Benchmark
    bench_parser = subparsers.add_parser('benchmark', help='بنچمارک')
    bench_parser.add_argument('test_file', help='فایل تست')
    bench_parser.add_argument('--iterations', '-i', type=int, default=5, help='تعداد تکرار')
    
    # Cache
    subparsers.add_parser('cache-stats', help='آمار cache')
    subparsers.add_parser('cache-clear', help='پاک کردن cache')
    
    # System
    subparsers.add_parser('system-info', help='اطلاعات سیستم')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    cli = FastCLI()
    
    try:
        if args.command == 'parse-fast':
            cli.parse_fast(args.input, args.law_code, args.category, args.output)
        
        elif args.command == 'batch-fast':
            cli.batch_fast(args.workers)
        
        elif args.command == 'stream':
            cli.stream_fast(args.input, args.output, args.law_code)
        
        elif args.command == 'benchmark':
            cli.benchmark(args.test_file, args.iterations)
        
        elif args.command == 'cache-stats':
            cli.cache_stats()
        
        elif args.command == 'cache-clear':
            cli.cache_clear()
        
        elif args.command == 'system-info':
            cli.system_info()
    
    except KeyboardInterrupt:
        print("\n\n❌ متوقف شد")
    except Exception as e:
        print(f"\n❌ خطا: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()

