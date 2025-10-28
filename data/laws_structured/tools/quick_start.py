#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
اسکریپت شروع سریع برای پردازش قوانین
"""

import sys
from pathlib import Path

# اضافه کردن path
sys.path.insert(0, str(Path(__file__).parent))

from law_parser import LawParser
from batch_processor import BatchProcessor


def quick_demo():
    """دموی سریع"""
    print("🚀 خوش آمدید به سیستم مستندسازی قوانین دادرس\n")
    
    print("📁 فایل‌های موجود در data/laws/:")
    laws_dir = Path('../../laws')
    if laws_dir.exists():
        for txt_file in laws_dir.glob('*.txt'):
            size = txt_file.stat().st_size / 1024
            print(f"  • {txt_file.name} ({size:.1f} KB)")
    else:
        print("  ❌ پوشه data/laws یافت نشد")
    
    print("\n" + "="*60)
    print("🛠️  دستورات پیشنهادی:")
    print("="*60)
    
    print("\n1️⃣  پردازش خودکار تمام فایل‌ها:")
    print("   python law_cli.py batch --auto")
    
    print("\n2️⃣  پارس یک فایل خاص:")
    print("   python law_cli.py parse INPUT LAW_CODE CATEGORY OUTPUT")
    
    print("\n3️⃣  جستجو:")
    print("   python law_cli.py search \"عقد\"")
    
    print("\n4️⃣  لیست قوانین:")
    print("   python law_cli.py list")
    
    print("\n5️⃣  آمار:")
    print("   python law_cli.py stats")
    
    print("\n" + "="*60)
    print("📖 برای راهنمای کامل:")
    print("   python law_cli.py --help")
    print("="*60)
    
    # سوال از کاربر
    print("\n❓ می‌خواهید الان پردازش خودکار را شروع کنید؟ (y/n): ", end='')
    
    try:
        choice = input().strip().lower()
        if choice in ['y', 'yes', 'بله']:
            print("\n🚀 شروع پردازش...")
            processor = BatchProcessor()
            processor.process_all()
        else:
            print("\n👋 برای شروع، از دستورات بالا استفاده کنید")
    except KeyboardInterrupt:
        print("\n\n👋 خروج")


def process_sample():
    """پردازش فایل نمونه"""
    sample_file = Path('../../laws/sample.txt')
    
    if not sample_file.exists():
        print(f"❌ فایل نمونه یافت نشد: {sample_file}")
        return
    
    print(f"📄 در حال پردازش فایل نمونه...")
    
    parser = LawParser()
    articles = parser.parse_file(
        str(sample_file),
        'sample_law',
        'نمونه'
    )
    
    if articles:
        print(f"✅ {len(articles)} ماده پارس شد:")
        for article in articles:
            print(f"  • ماده {article['article_number']}: {article['title']}")
        
        # ذخیره
        output_dir = Path('../sample_law/general')
        output_dir.mkdir(parents=True, exist_ok=True)
        parser.save_to_json(output_dir / 'articles_001-001.json', articles)
        
        print(f"\n✅ نتیجه در {output_dir} ذخیره شد")
    else:
        print("❌ هیچ ماده‌ای یافت نشد")


if __name__ == '__main__':
    import argparse
    
    parser_arg = argparse.ArgumentParser(description='شروع سریع')
    parser_arg.add_argument('--sample', action='store_true', help='پردازش فایل نمونه')
    
    args = parser_arg.parse_args()
    
    if args.sample:
        process_sample()
    else:
        quick_demo()

