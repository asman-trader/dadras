#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
پردازش دسته‌ای (Batch) فایل‌های متعدد قانونی
"""

import json
import glob
from pathlib import Path
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from law_parser import LawParser


class BatchProcessor:
    """کلاس پردازش دسته‌ای قوانین"""
    
    def __init__(self, base_input_dir: str = 'data/laws', 
                 base_output_dir: str = 'data/laws_structured'):
        self.base_input_dir = Path(base_input_dir)
        self.base_output_dir = Path(base_output_dir)
        self.parser = LawParser()
        self.results = []
    
    def process_all(self, config_file: str = None):
        """پردازش تمام قوانین براساس فایل تنظیمات"""
        
        if config_file:
            config = self._load_config(config_file)
        else:
            config = self._auto_discover()
        
        print(f"🚀 شروع پردازش {len(config)} فایل...\n")
        
        # پردازش موازی
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(self._process_single, item): item 
                for item in config
            }
            
            for future in as_completed(futures):
                item = futures[future]
                try:
                    result = future.result()
                    self.results.append(result)
                except Exception as e:
                    print(f"❌ خطا در {item['input']}: {e}")
        
        # خلاصه نتایج
        self._print_summary()
        
        # به‌روزرسانی index
        self._update_index()
    
    def _load_config(self, config_file: str) -> List[Dict]:
        """بارگذاری تنظیمات از فایل JSON"""
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _auto_discover(self) -> List[Dict]:
        """کشف خودکار فایل‌های TXT"""
        config = []
        
        # جستجوی فایل‌های txt در پوشه laws
        for txt_file in self.base_input_dir.glob('*.txt'):
            if txt_file.name == 'sample.txt':
                continue
            
            # حدس زدن law_code و category از نام فایل
            name = txt_file.stem
            
            config.append({
                'input': str(txt_file),
                'law_code': self._normalize_code(name),
                'category': name,
                'output_section': 'general'
            })
        
        return config
    
    def _normalize_code(self, name: str) -> str:
        """نرمال‌سازی نام به کد"""
        # حذف کاراکترهای خاص
        name = name.replace('قانون-', '').replace('قانون', '')
        name = name.replace('-', '_').replace(' ', '_')
        
        # ترجمه نام‌های رایج
        translations = {
            'مدنی': 'civil_law',
            'تجارت': 'commercial_law',
            'کیفری': 'criminal_law',
            'جزا': 'criminal_law',
            'معاملات': 'transactions',
        }
        
        return translations.get(name, name.lower())
    
    def _process_single(self, item: Dict) -> Dict:
        """پردازش یک فایل"""
        try:
            input_file = item['input']
            law_code = item['law_code']
            category = item.get('category', 'عمومی')
            output_section = item.get('output_section', 'general')
            
            # مسیر خروجی
            output_dir = self.base_output_dir / law_code / output_section
            
            # پارس و ذخیره
            articles = self.parser.parse_file(input_file, law_code, category)
            
            if articles:
                # ذخیره به chunk ها
                chunk_size = item.get('chunk_size', 20)
                self._save_chunks(articles, output_dir, chunk_size)
                
                return {
                    'success': True,
                    'input': input_file,
                    'law_code': law_code,
                    'article_count': len(articles),
                    'output_dir': str(output_dir)
                }
            else:
                return {
                    'success': False,
                    'input': input_file,
                    'error': 'No articles found'
                }
                
        except Exception as e:
            return {
                'success': False,
                'input': item['input'],
                'error': str(e)
            }
    
    def _save_chunks(self, articles: List[Dict], output_dir: Path, chunk_size: int):
        """ذخیره مواد به صورت chunk"""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        for i in range(0, len(articles), chunk_size):
            chunk = articles[i:i + chunk_size]
            start = chunk[0]['article_number']
            end = chunk[-1]['article_number']
            
            filename = f"articles_{start:03d}-{end:03d}.json"
            output_file = output_dir / filename
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(chunk, f, ensure_ascii=False, indent=2)
    
    def _print_summary(self):
        """چاپ خلاصه نتایج"""
        print("\n" + "="*70)
        print("📊 خلاصه پردازش")
        print("="*70)
        
        total = len(self.results)
        success = sum(1 for r in self.results if r.get('success'))
        failed = total - success
        total_articles = sum(r.get('article_count', 0) for r in self.results if r.get('success'))
        
        print(f"📁 تعداد کل فایل‌ها: {total}")
        print(f"✅ موفق: {success}")
        print(f"❌ ناموفق: {failed}")
        print(f"📝 تعداد کل مواد: {total_articles}")
        
        if success > 0:
            print(f"\n✅ فایل‌های پردازش شده:")
            for result in self.results:
                if result.get('success'):
                    print(f"  • {Path(result['input']).name}: "
                          f"{result['article_count']} ماده "
                          f"→ {result['law_code']}")
        
        if failed > 0:
            print(f"\n❌ فایل‌های ناموفق:")
            for result in self.results:
                if not result.get('success'):
                    print(f"  • {Path(result['input']).name}: {result.get('error')}")
        
        print("="*70)
    
    def _update_index(self):
        """به‌روزرسانی فایل index.json"""
        index_file = self.base_output_dir / 'index.json'
        
        if not index_file.exists():
            print("⚠️  فایل index.json یافت نشد")
            return
        
        with open(index_file, 'r', encoding='utf-8') as f:
            index = json.load(f)
        
        # به‌روزرسانی آمار
        total_articles = sum(r.get('article_count', 0) for r in self.results if r.get('success'))
        
        index['statistics']['indexed_articles'] = total_articles
        index['statistics']['last_update'] = LawParser().current_article.get('last_modified', '')
        
        # ذخیره
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ فایل index.json به‌روزرسانی شد")
    
    def create_config_template(self, output_file: str = 'batch_config.json'):
        """ایجاد قالب فایل تنظیمات"""
        template = [
            {
                "input": "data/laws/قانون-مدنی.txt",
                "law_code": "civil_law",
                "category": "مدنی",
                "output_section": "general",
                "chunk_size": 20,
                "metadata": {
                    "title": "قانون مدنی",
                    "date_approved": "1307/05/08"
                }
            },
            {
                "input": "data/laws/moamlat.txt",
                "law_code": "civil_law",
                "category": "معاملات",
                "output_section": "transactions",
                "chunk_size": 20
            }
        ]
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(template, f, ensure_ascii=False, indent=2)
        
        print(f"✅ قالب تنظیمات ذخیره شد: {output_file}")


def main():
    """تابع اصلی"""
    import argparse
    
    parser = argparse.ArgumentParser(description='پردازش دسته‌ای قوانین')
    parser.add_argument('--config', '-c', help='فایل تنظیمات JSON')
    parser.add_argument('--auto', '-a', action='store_true', help='کشف خودکار فایل‌ها')
    parser.add_argument('--template', '-t', action='store_true', help='ایجاد قالب تنظیمات')
    
    args = parser.parse_args()
    
    processor = BatchProcessor()
    
    if args.template:
        processor.create_config_template()
    elif args.auto:
        processor.process_all()
    elif args.config:
        processor.process_all(args.config)
    else:
        print("❌ لطفاً یکی از گزینه‌ها را انتخاب کنید:")
        print("  --auto      : کشف و پردازش خودکار")
        print("  --config    : استفاده از فایل تنظیمات")
        print("  --template  : ایجاد قالب تنظیمات")


if __name__ == '__main__':
    main()

