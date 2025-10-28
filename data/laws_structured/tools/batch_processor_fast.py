#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
پردازشگر دسته‌ای بهینه با multiprocessing
- استفاده از چند هسته CPU
- Progress bar
- پردازش موازی واقعی
- مدیریت بهینه منابع
"""

import json
import time
from pathlib import Path
from typing import List, Dict
from multiprocessing import Pool, cpu_count, Manager
from functools import partial
import sys

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    print("💡 نصب tqdm برای نمایش progress bar:")
    print("   pip install tqdm")

from law_parser_fast import FastLawParser


class FastBatchProcessor:
    """پردازشگر دسته‌ای بهینه با multiprocessing"""
    
    def __init__(self, base_input_dir: str = 'data/laws',
                 base_output_dir: str = 'data/laws_structured',
                 num_workers: int = None):
        self.base_input_dir = Path(base_input_dir)
        self.base_output_dir = Path(base_output_dir)
        
        # تعداد workers (پیش‌فرض: تعداد CPU ها)
        self.num_workers = num_workers or max(1, cpu_count() - 1)
        
        self.results = []
        
        print(f"🚀 پردازشگر سریع با {self.num_workers} worker")
    
    def process_all_parallel(self, config: List[Dict] = None):
        """پردازش موازی با multiprocessing"""
        
        if config is None:
            config = self._auto_discover()
        
        if not config:
            print("❌ هیچ فایلی برای پردازش یافت نشد")
            return
        
        print(f"\n⚡ شروع پردازش {len(config)} فایل با {self.num_workers} worker...\n")
        
        start_time = time.time()
        
        # استفاده از multiprocessing Pool
        with Pool(processes=self.num_workers) as pool:
            if TQDM_AVAILABLE:
                # با progress bar
                results = list(tqdm(
                    pool.imap(self._process_single_worker, config),
                    total=len(config),
                    desc="پردازش فایل‌ها",
                    unit="فایل"
                ))
            else:
                # بدون progress bar
                results = pool.map(self._process_single_worker, config)
        
        self.results = results
        
        elapsed = time.time() - start_time
        
        # خلاصه نتایج
        self._print_summary_fast(elapsed)
        
        # به‌روزرسانی index
        self._update_index()
    
    @staticmethod
    def _process_single_worker(item: Dict) -> Dict:
        """پردازش یک فایل در worker"""
        try:
            parser = FastLawParser()
            
            input_file = item['input']
            law_code = item['law_code']
            category = item.get('category', 'عمومی')
            output_section = item.get('output_section', 'general')
            
            # مسیر خروجی
            base_output = Path(item.get('base_output', 'data/laws_structured'))
            output_dir = base_output / law_code / output_section
            
            # پارس سریع
            articles_count = 0
            chunk = []
            chunk_start = None
            chunk_size = item.get('chunk_size', 20)
            
            output_dir.mkdir(parents=True, exist_ok=True)
            
            for article in parser.parse_file_fast(input_file, law_code, category):
                if chunk_start is None:
                    chunk_start = article['article_number']
                
                chunk.append(article)
                articles_count += 1
                
                if len(chunk) >= chunk_size:
                    parser._save_chunk_fast(chunk, output_dir, chunk_start)
                    chunk = []
                    chunk_start = None
            
            # ذخیره آخرین chunk
            if chunk:
                parser._save_chunk_fast(chunk, output_dir, chunk_start)
            
            return {
                'success': True,
                'input': input_file,
                'law_code': law_code,
                'article_count': articles_count,
                'output_dir': str(output_dir)
            }
            
        except Exception as e:
            return {
                'success': False,
                'input': item.get('input', 'unknown'),
                'error': str(e)
            }
    
    def _auto_discover(self) -> List[Dict]:
        """کشف خودکار فایل‌های TXT"""
        config = []
        
        if not self.base_input_dir.exists():
            return config
        
        for txt_file in self.base_input_dir.glob('*.txt'):
            if txt_file.name in ['sample.txt', 'test.txt']:
                continue
            
            name = txt_file.stem
            law_code = self._normalize_code(name)
            
            config.append({
                'input': str(txt_file),
                'law_code': law_code,
                'category': name,
                'output_section': 'general',
                'base_output': str(self.base_output_dir),
                'chunk_size': 20
            })
        
        return config
    
    @staticmethod
    def _normalize_code(name: str) -> str:
        """نرمال‌سازی نام به کد"""
        name = name.replace('قانون-', '').replace('قانون', '')
        name = name.replace('-', '_').replace(' ', '_')
        
        translations = {
            'مدنی': 'civil_law',
            'تجارت': 'commercial_law',
            'کیفری': 'criminal_law',
            'جزا': 'criminal_law',
            'معاملات': 'transactions',
        }
        
        return translations.get(name, name.lower())
    
    def _print_summary_fast(self, elapsed: float):
        """چاپ خلاصه سریع نتایج"""
        print("\n" + "="*70)
        print("📊 خلاصه پردازش")
        print("="*70)
        
        total = len(self.results)
        success = sum(1 for r in self.results if r.get('success'))
        failed = total - success
        total_articles = sum(r.get('article_count', 0) for r in self.results if r.get('success'))
        
        print(f"⏱️  زمان کل: {elapsed:.2f} ثانیه")
        print(f"📁 تعداد فایل‌ها: {total}")
        print(f"✅ موفق: {success}")
        print(f"❌ ناموفق: {failed}")
        print(f"📝 تعداد کل مواد: {total_articles}")
        
        if elapsed > 0:
            speed = total_articles / elapsed
            print(f"⚡ سرعت: {speed:.1f} ماده/ثانیه")
            print(f"🚀 سرعت: {total/elapsed:.2f} فایل/ثانیه")
        
        if success > 0:
            print(f"\n✅ فایل‌های موفق:")
            for result in self.results:
                if result.get('success'):
                    name = Path(result['input']).name
                    print(f"  • {name}: {result['article_count']} ماده")
        
        if failed > 0:
            print(f"\n❌ فایل‌های ناموفق:")
            for result in self.results:
                if not result.get('success'):
                    name = Path(result['input']).name
                    print(f"  • {name}: {result.get('error')}")
        
        print("="*70)
    
    def _update_index(self):
        """به‌روزرسانی فایل index"""
        index_file = self.base_output_dir / 'index.json'
        
        if not index_file.exists():
            return
        
        try:
            with open(index_file, 'r', encoding='utf-8') as f:
                index = json.load(f)
            
            # به‌روزرسانی آمار
            total_articles = sum(r.get('article_count', 0) 
                               for r in self.results if r.get('success'))
            
            index['statistics']['indexed_articles'] = total_articles
            index['statistics']['last_update'] = time.strftime('%Y-%m-%dT%H:%M:%S')
            
            with open(index_file, 'w', encoding='utf-8') as f:
                json.dump(index, f, ensure_ascii=False, indent=2)
            
            print(f"\n✅ فایل index.json به‌روزرسانی شد")
        except Exception as e:
            print(f"⚠️  خطا در به‌روزرسانی index: {e}")
    
    def benchmark(self, test_file: str, iterations: int = 5):
        """بنچمارک سرعت پردازش"""
        
        if not Path(test_file).exists():
            print(f"❌ فایل تست یافت نشد: {test_file}")
            return
        
        print(f"🏁 بنچمارک با {iterations} تکرار...\n")
        
        times = []
        article_counts = []
        
        for i in range(iterations):
            print(f"دور {i+1}/{iterations}:")
            
            start = time.time()
            
            parser = FastLawParser()
            count = sum(1 for _ in parser.parse_file_fast(
                test_file, 'test', 'test'
            ))
            
            elapsed = time.time() - start
            times.append(elapsed)
            article_counts.append(count)
            
            print(f"  ⏱️  {elapsed:.3f}s - {count} ماده - {count/elapsed:.1f} ماده/ثانیه\n")
        
        # آمار
        avg_time = sum(times) / len(times)
        avg_speed = article_counts[0] / avg_time
        
        print("="*60)
        print("📊 نتایج بنچمارک:")
        print(f"  میانگین زمان: {avg_time:.3f} ثانیه")
        print(f"  سریع‌ترین: {min(times):.3f} ثانیه")
        print(f"  کندترین: {max(times):.3f} ثانیه")
        print(f"  میانگین سرعت: {avg_speed:.1f} ماده/ثانیه")
        print("="*60)


class StreamProcessor:
    """پردازشگر جریانی برای فایل‌های بسیار بزرگ"""
    
    @staticmethod
    def process_stream(input_file: str, output_dir: str, 
                      law_code: str, chunk_size: int = 100):
        """پردازش جریانی بدون بارگذاری کامل در حافظه"""
        
        print(f"🌊 پردازش جریانی: {input_file}")
        
        parser = FastLawParser()
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        chunk = []
        chunk_start = None
        total = 0
        
        # Generator برای حافظه کم
        for article in parser.parse_file_fast(input_file, law_code, 'general'):
            if chunk_start is None:
                chunk_start = article['article_number']
            
            chunk.append(article)
            total += 1
            
            if len(chunk) >= chunk_size:
                parser._save_chunk_fast(chunk, output_path, chunk_start)
                chunk = []
                chunk_start = None
                
                # گزارش پیشرفت
                if total % 100 == 0:
                    print(f"  📝 {total} ماده پردازش شد...")
        
        # ذخیره باقیمانده
        if chunk:
            parser._save_chunk_fast(chunk, output_path, chunk_start)
        
        print(f"✅ جمع: {total} ماده")


def main():
    """تابع اصلی"""
    import argparse
    
    parser = argparse.ArgumentParser(description='پردازشگر سریع با multiprocessing')
    parser.add_argument('--workers', '-w', type=int, help='تعداد workers')
    parser.add_argument('--auto', '-a', action='store_true', help='پردازش خودکار')
    parser.add_argument('--benchmark', '-b', help='بنچمارک با فایل')
    parser.add_argument('--stream', '-s', nargs=3, 
                       metavar=('INPUT', 'OUTPUT', 'CODE'),
                       help='پردازش جریانی')
    
    args = parser.parse_args()
    
    if args.benchmark:
        processor = FastBatchProcessor(num_workers=args.workers)
        processor.benchmark(args.benchmark)
    
    elif args.stream:
        input_file, output_dir, law_code = args.stream
        StreamProcessor.process_stream(input_file, output_dir, law_code)
    
    elif args.auto:
        processor = FastBatchProcessor(num_workers=args.workers)
        processor.process_all_parallel()
    
    else:
        print("❌ لطفاً یک گزینه انتخاب کنید:")
        print("  --auto        : پردازش خودکار")
        print("  --benchmark   : بنچمارک")
        print("  --stream      : پردازش جریانی")
        print("  --workers N   : تعداد workers")


if __name__ == '__main__':
    main()

