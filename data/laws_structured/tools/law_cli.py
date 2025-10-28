#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ابزار خط فرمان (CLI) برای مدیریت سیستم قوانین
"""

import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict

# اضافه کردن مسیر tools به sys.path
sys.path.insert(0, str(Path(__file__).parent))

from law_parser import LawParser
from batch_processor import BatchProcessor


class LawCLI:
    """کلاس CLI برای مدیریت قوانین"""
    
    def __init__(self):
        self.base_dir = Path('data/laws_structured')
        self.parser = LawParser()
        self.processor = BatchProcessor()
    
    def parse_single(self, input_file: str, law_code: str, category: str, output_dir: str):
        """پارس یک فایل"""
        print(f"📄 در حال پارس: {input_file}")
        
        self.parser.parse_and_save(
            input_file=input_file,
            output_dir=output_dir,
            law_code=law_code,
            category=category
        )
        
        print("✅ پارس با موفقیت انجام شد!")
    
    def batch_process(self, config_file: str = None, auto: bool = False):
        """پردازش دسته‌ای"""
        if auto:
            print("🔍 کشف خودکار فایل‌ها...")
            self.processor.process_all()
        elif config_file:
            print(f"📋 استفاده از فایل تنظیمات: {config_file}")
            self.processor.process_all(config_file)
        else:
            print("❌ باید --config یا --auto را مشخص کنید")
    
    def validate(self, path: str = None):
        """اعتبارسنجی فایل‌ها"""
        import sys
        sys.path.insert(0, str(self.base_dir))
        
        try:
            from validate import LawValidator
            validator = LawValidator()
            results = validator.validate_all()
            validator.print_summary(results)
            
            return results['invalid_files'] == 0
        except ImportError:
            print("❌ فایل validate.py یافت نشد")
            return False
    
    def list_laws(self):
        """لیست تمام قوانین"""
        index_file = self.base_dir / 'index.json'
        
        if not index_file.exists():
            print("❌ فایل index.json یافت نشد")
            return
        
        with open(index_file, 'r', encoding='utf-8') as f:
            index = json.load(f)
        
        print("📚 لیست قوانین:")
        print("="*60)
        
        for law in index.get('laws', []):
            print(f"\n📖 {law['title']} ({law['code']})")
            print(f"   وضعیت: {law.get('status', 'نامشخص')}")
            print(f"   زبان: {law.get('language', 'fa')}")
            
            if 'sections' in law:
                print(f"   بخش‌ها:")
                for section in law['sections']:
                    count = section.get('article_count', 0)
                    print(f"     • {section['name']}: {count} ماده")
        
        stats = index.get('statistics', {})
        print(f"\n📊 آمار کلی:")
        print(f"   تعداد قوانین: {index.get('total_laws', 0)}")
        print(f"   تعداد مواد: {stats.get('indexed_articles', 0)}")
        print("="*60)
    
    def search(self, query: str, law_code: str = None, limit: int = 10):
        """جستجوی ساده در مواد"""
        print(f"🔍 جستجو برای: {query}")
        
        results = []
        search_path = self.base_dir
        
        if law_code:
            search_path = search_path / law_code
        
        # جستجو در تمام فایل‌های JSON
        for json_file in search_path.rglob('articles_*.json'):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    articles = json.load(f)
                
                for article in articles:
                    text = (f"{article.get('title', '')} "
                           f"{article.get('text', '')} "
                           f"{article.get('explanation', '')}").lower()
                    
                    if query.lower() in text:
                        results.append({
                            'article': article,
                            'file': str(json_file.relative_to(self.base_dir))
                        })
            except Exception as e:
                continue
        
        # نمایش نتایج
        if not results:
            print("❌ نتیجه‌ای یافت نشد")
            return
        
        print(f"\n✅ {len(results)} نتیجه یافت شد:")
        print("="*60)
        
        for i, result in enumerate(results[:limit], 1):
            article = result['article']
            print(f"\n{i}. ماده {article.get('article_number')}: {article.get('title')}")
            print(f"   📁 {result['file']}")
            print(f"   📝 {article.get('explanation', '')[:100]}...")
            print(f"   🏷️  {', '.join(article.get('tags', []))}")
        
        if len(results) > limit:
            print(f"\n... و {len(results) - limit} نتیجه دیگر")
    
    def stats(self):
        """نمایش آمار کلی"""
        index_file = self.base_dir / 'index.json'
        
        if not index_file.exists():
            print("❌ فایل index.json یافت نشد")
            return
        
        with open(index_file, 'r', encoding='utf-8') as f:
            index = json.load(f)
        
        stats = index.get('statistics', {})
        
        print("📊 آمار سیستم قوانین")
        print("="*60)
        print(f"نسخه: {index.get('version', 'نامشخص')}")
        print(f"تعداد قوانین: {index.get('total_laws', 0)}")
        print(f"تعداد دسته‌بندی‌ها: {stats.get('total_categories', 0)}")
        print(f"تعداد بخش‌ها: {stats.get('total_sections', 0)}")
        print(f"تعداد مواد: {stats.get('indexed_articles', 0)}")
        print(f"تعداد تگ‌ها: {stats.get('total_tags', 0)}")
        print(f"آخرین به‌روزرسانی: {stats.get('last_update', 'نامشخص')}")
        print("="*60)
        
        # آمار فایل‌ها
        json_files = list(self.base_dir.rglob('articles_*.json'))
        print(f"\n📁 فایل‌های JSON: {len(json_files)}")
        
        total_size = sum(f.stat().st_size for f in json_files)
        print(f"📦 حجم کل: {total_size / 1024:.2f} KB")
    
    def export(self, law_code: str, output_file: str, format: str = 'json'):
        """صادرات یک قانون"""
        print(f"📤 در حال صادرات {law_code}...")
        
        law_dir = self.base_dir / law_code
        if not law_dir.exists():
            print(f"❌ قانون {law_code} یافت نشد")
            return
        
        all_articles = []
        
        # جمع‌آوری تمام مواد
        for json_file in law_dir.rglob('articles_*.json'):
            with open(json_file, 'r', encoding='utf-8') as f:
                articles = json.load(f)
                all_articles.extend(articles)
        
        # مرتب‌سازی براساس شماره ماده
        all_articles.sort(key=lambda x: x.get('article_number', 0))
        
        # ذخیره
        output_path = Path(output_file)
        
        if format == 'json':
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(all_articles, f, ensure_ascii=False, indent=2)
        
        elif format == 'txt':
            with open(output_path, 'w', encoding='utf-8') as f:
                for article in all_articles:
                    f.write(f"ماده {article['article_number']}: {article['title']}\n")
                    f.write(f"{article['text']}\n\n")
                    f.write(f"توضیح: {article['explanation']}\n")
                    f.write("-" * 60 + "\n\n")
        
        print(f"✅ {len(all_articles)} ماده در {output_file} ذخیره شد")
    
    def create_law(self, code: str, title: str):
        """ایجاد قانون جدید"""
        law_dir = self.base_dir / code
        
        if law_dir.exists():
            print(f"⚠️  قانون {code} قبلاً وجود دارد")
            return
        
        # ایجاد ساختار
        law_dir.mkdir(parents=True, exist_ok=True)
        (law_dir / 'general').mkdir(exist_ok=True)
        
        # ایجاد metadata
        metadata = {
            'code': code,
            'title': title,
            'status': 'draft',
            'sections': [],
            'tags': [],
            'version': '1.0.0'
        }
        
        with open(law_dir / 'metadata.json', 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        print(f"✅ قانون {code} ایجاد شد در {law_dir}")


def main():
    """تابع اصلی CLI"""
    parser = argparse.ArgumentParser(
        description='🔧 ابزار مدیریت سیستم قوانین دادرس',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
مثال‌های استفاده:
  %(prog)s parse input.txt civil_law معاملات output/
  %(prog)s batch --auto
  %(prog)s search "عقد" --law civil_law
  %(prog)s list
  %(prog)s validate
  %(prog)s stats
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='دستورات')
    
    # Parse command
    parse_parser = subparsers.add_parser('parse', help='پارس یک فایل')
    parse_parser.add_argument('input', help='فایل ورودی')
    parse_parser.add_argument('law_code', help='کد قانون')
    parse_parser.add_argument('category', help='دسته')
    parse_parser.add_argument('output', help='پوشه خروجی')
    
    # Batch command
    batch_parser = subparsers.add_parser('batch', help='پردازش دسته‌ای')
    batch_parser.add_argument('--config', '-c', help='فایل تنظیمات')
    batch_parser.add_argument('--auto', '-a', action='store_true', help='کشف خودکار')
    
    # Validate command
    subparsers.add_parser('validate', help='اعتبارسنجی فایل‌ها')
    
    # List command
    subparsers.add_parser('list', help='لیست قوانین')
    
    # Search command
    search_parser = subparsers.add_parser('search', help='جستجو')
    search_parser.add_argument('query', help='عبارت جستجو')
    search_parser.add_argument('--law', help='کد قانون')
    search_parser.add_argument('--limit', type=int, default=10, help='حداکثر نتایج')
    
    # Stats command
    subparsers.add_parser('stats', help='آمار')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='صادرات')
    export_parser.add_argument('law_code', help='کد قانون')
    export_parser.add_argument('output', help='فایل خروجی')
    export_parser.add_argument('--format', choices=['json', 'txt'], default='json')
    
    # Create command
    create_parser = subparsers.add_parser('create', help='ایجاد قانون جدید')
    create_parser.add_argument('code', help='کد قانون')
    create_parser.add_argument('title', help='عنوان قانون')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    cli = LawCLI()
    
    # اجرای دستور
    if args.command == 'parse':
        cli.parse_single(args.input, args.law_code, args.category, args.output)
    
    elif args.command == 'batch':
        cli.batch_process(args.config, args.auto)
    
    elif args.command == 'validate':
        success = cli.validate()
        sys.exit(0 if success else 1)
    
    elif args.command == 'list':
        cli.list_laws()
    
    elif args.command == 'search':
        cli.search(args.query, args.law, args.limit)
    
    elif args.command == 'stats':
        cli.stats()
    
    elif args.command == 'export':
        cli.export(args.law_code, args.output, args.format)
    
    elif args.command == 'create':
        cli.create_law(args.code, args.title)


if __name__ == '__main__':
    main()

