"""
مدیریت کامل پرونده - از شروع تا پایان
این ماژول وکیل کاملی است که پرونده را تا نتیجه نهایی پیگیری می‌کند
"""

import re
import json
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta


class CaseManager:
    """مدیریت کامل پرونده حقوقی"""
    
    def __init__(self):
        # مراحل پرونده
        self.case_stages = {
            'pre_complaint': {
                'name': 'قبل از شکایت',
                'actions': ['بررسی اولیه', 'جمع‌آوری مدارک', 'تنظیم دادخواست', 'محاسبه هزینه', 'ارائه دادخواست'],
                'documents': ['دادخواست', 'ضمائم', 'محاسبه خسارت']
            },
            'complaint_filed': {
                'name': 'دادخواست ارائه شده',
                'actions': ['پیگیری ثبت', 'دریافت شماره پرونده', 'پرداخت هزینه', 'پیگیری ارجاع'],
                'documents': ['رسید پرونده', 'قبض هزینه']
            },
            'court_session': {
                'name': 'جلسه دادگاه',
                'actions': ['آماده‌سازی دفاعیه', 'حضور در جلسه', 'ارائه دلایل', 'پاسخ به ایرادات'],
                'documents': ['دفاعیه', 'لایحه', 'مستندات تکمیلی']
            },
            'verdict': {
                'name': 'صدور رأی',
                'actions': ['بررسی رأی', 'تحلیل نتیجه', 'ارزیابی تجدیدنظر', 'اجرای حکم'],
                'documents': ['رأی دادگاه', 'برگ اجرایی']
            },
            'appeal': {
                'name': 'تجدیدنظر',
                'actions': ['تنظیم دادخواست تجدیدنظر', 'ارائه دلایل جدید', 'پیگیری'],
                'documents': ['دادخواست تجدیدنظر', 'لایحه تجدیدنظر']
            },
            'execution': {
                'name': 'اجرای احکام',
                'actions': ['مراجعه به اجرا', 'پیگیری اجرا', 'دریافت حقوق'],
                'documents': ['درخواست اجرا', 'پیگیری‌های اجرا']
            }
        }
        
        # نگاشت مرحله‌ها به کلیدها برای تشخیص هوشمند
        self.stage_alias_map = {
            'قبل از طرح شکایت': 'pre_complaint',
            'قبل از شکایت': 'pre_complaint',
            'قبل از دادخواست': 'pre_complaint',
            'دادخواست ارائه شده': 'complaint_filed',
            'تشکیل پرونده': 'complaint_filed',
            'در جریان دادگاه': 'court_session',
            'جلسه دادگاه': 'court_session',
            'برگزاری جلسه': 'court_session',
            'پس از صدور رأی': 'verdict',
            'صدور حکم': 'verdict',
            'صدور رأی': 'verdict',
            'مرحله تجدیدنظر': 'appeal',
            'تجدیدنظر': 'appeal',
            'فرجام': 'appeal',
            'اجرای حکم': 'execution',
            'اجرای احکام': 'execution'
        }

        self.stage_keyword_map = {
            'execution': ['اجرای حکم', 'اجراییه', 'دائره اجرا', 'اداره اجرا', 'اجرای احکام', 'اجرائیه'],
            'appeal': ['تجدیدنظر', 'واخواهی', 'فرجام', 'اعاده دادرسی', 'اعتراض به رای', 'اعتراض به رأی', 'برگ رأی تجدیدنظر'],
            'verdict': ['صدور رای', 'صدور رأی', 'حکم صادر', 'دادنامه', 'ابلاغ رای', 'ابلاغ رأی', 'محکوم'],
            'court_session': ['جلسه', 'دادرسی', 'دادگاه', 'تعیین وقت', 'حضور در دادگاه', 'استماع', 'اظهارات در جلسه'],
            'complaint_filed': ['ثبت دادخواست', 'ارجاع', 'شماره پرونده', 'کلاسه', 'ثبت پرونده', 'تشکیل پرونده', 'رسید ثبت'],
            'pre_complaint': ['مشاوره', 'جمع‌آوری مدارک', 'در حال آماده‌سازی', 'طرح شکایت', 'آماده شکایت']
        }

        # الگوهای اسناد
        self.document_templates = {
            'lawsuit': 'دادخواست',
            'defense': 'دفاعیه',
            'petition': 'لایحه',
            'complaint': 'شکواییه',
            'objection': 'اعتراض',
            'appeal': 'تجدیدنظر',
            'execution': 'اجرای حکم'
        }

        self.document_labels = {
            'lawsuit': 'دادخواست',
            'defense': 'دفاعیه',
            'petition': 'لایحه',
            'appeal': 'دادخواست تجدیدنظر'
        }

        self.document_playbook = {
            'criminal': {
                'initial': [
                    'شکواییه (شروع تعقیب کیفری)',
                    'گزارش ضابطان دادگستری',
                    'کیفرخواست (در صورت صدور توسط دادستان)',
                    'اظهارنامه کیفری یا اعلام جرم'
                ],
                'defense': [
                    'دفاعیه متهم یا وکیل او',
                    'لایحه دفاعیه در پاسخ به کیفرخواست',
                    'دلایل و مستندات دفاعی (شهود، مدارک، نظریه کارشناس و ...)',
                    'دفاع شفاهی و نکات کلیدی برای جلسه رسیدگی'
                ],
                'follow_up': [
                    'لایحه نهایی یا جمع‌بندی دفاع',
                    'اعتراض به رأی (واخواهی، تجدیدنظرخواهی، فرجام‌خواهی)',
                    'درخواست اعاده دادرسی',
                    'درخواست تعلیق، تخفیف یا عفو مجازات'
                ]
            },
            'civil': {
                'initial': [
                    'دادخواست اصلی (خواهان)',
                    'پیوست‌ها و مستندات دادخواست',
                    'اظهارنامه رسمی (پیش از طرح دعوا)',
                    'دادخواست تقابل یا ورود ثالث (در صورت نیاز)'
                ],
                'defense': [
                    'دفاعیه خوانده',
                    'پاسخ به دادخواست (لایحه دفاعیه)',
                    'اسناد، مدارک و دلایل دفاعی منسجم'
                ],
                'follow_up': [
                    'لایحه نهایی قبل از ختم دادرسی',
                    'اعتراض به رأی (تجدیدنظرخواهی، فرجام‌خواهی، اعاده دادرسی)',
                    'درخواست اجرای حکم یا صدور دستور موقت',
                    'درخواست تأمین خواسته یا تأمین دلیل'
                ]
            }
        }

    # ------------------------- ابزارهای داخلی -------------------------

    @staticmethod
    def _normalize_for_lookup(value: Optional[str]) -> str:
        if not value:
            return ''
        text = str(value).replace('\u200c', ' ')
        text = re.sub(r'\s+', ' ', text)
        return text.strip().lower()

    def _clean_placeholder(self, value: Optional[str], default: str) -> str:
        if value is None:
            return default
        text = str(value).strip()
        placeholders = {'', 'ندارد', 'نامشخص', 'مشخص نیست', '(ندارد)', '(نامشخص)', '(مشخص نشده)', '(در مکالمه ذکر نشد)', 'none', 'unknown'}
        normalized = self._normalize_for_lookup(text)
        if normalized in placeholders or text in placeholders:
            return default
        return text

    def _split_to_list(self, raw_value: Optional[str]) -> List[str]:
        if not raw_value:
            return []
        if isinstance(raw_value, list):
            iterable = raw_value
        else:
            iterable = re.split(r'[\n،,;]+', str(raw_value))
        items: List[str] = []
        for item in iterable:
            if not item:
                continue
            text = str(item).strip()
            if not text:
                continue
            if self._normalize_for_lookup(text) in {'ندارد', 'هیچ', 'ندارم'}:
                continue
            items.append(text)
        return items

    def _collect_stage_text(self, case_info: Dict) -> str:
        parts: List[str] = []
        for field in ('case_stage', 'actions_taken', 'status', 'deadlines', 'notes', 'latest_update', 'history'):
            value = case_info.get(field)
            if isinstance(value, str):
                parts.append(value)
        history = case_info.get('conversation_history')
        if isinstance(history, list):
            for item in history:
                if isinstance(item, dict):
                    content = item.get('text') or item.get('content') or ''
                else:
                    content = str(item)
                if content:
                    parts.append(content)
        return self._normalize_for_lookup(' '.join(parts))

    def _detect_case_stage_key(self, case_info: Dict) -> Tuple[str, str, str]:
        stage_field_raw = case_info.get('case_stage', '')
        normalized_stage = self._normalize_for_lookup(stage_field_raw)

        if normalized_stage in self.case_stages:
            stage_key = normalized_stage
            stage_label = self.case_stages.get(stage_key, self.case_stages['pre_complaint']).get('name', 'مرحله نامشخص')
            return stage_key, stage_label, 'explicit_key'

        for alias, key in self.stage_alias_map.items():
            alias_norm = self._normalize_for_lookup(alias)
            if alias_norm and alias_norm in normalized_stage:
                stage_label = self.case_stages.get(key, self.case_stages['pre_complaint']).get('name', 'مرحله نامشخص')
                return key, stage_label, 'case_stage_text'

        combined_text = self._collect_stage_text(case_info)
        stage_priority = ['execution', 'appeal', 'verdict', 'court_session', 'complaint_filed', 'pre_complaint']
        for stage_key in stage_priority:
            for keyword in self.stage_keyword_map.get(stage_key, []):
                if self._normalize_for_lookup(keyword) in combined_text:
                    stage_label = self.case_stages.get(stage_key, self.case_stages['pre_complaint']).get('name', 'مرحله نامشخص')
                    return stage_key, stage_label, 'keyword_match'

        case_number = self._clean_placeholder(case_info.get('case_number'), '')
        if case_number and self._normalize_for_lookup(case_number) not in {'ندارد', 'نامشخص'}:
            stage_label = self.case_stages['complaint_filed']['name']
            return 'complaint_filed', stage_label, 'case_number_present'

        actions_text = self._normalize_for_lookup(case_info.get('actions_taken', ''))
        if actions_text and ('دادخواست' in actions_text or 'شکایت' in actions_text):
            stage_label = self.case_stages['complaint_filed']['name']
            return 'complaint_filed', stage_label, 'actions_taken'

        return 'pre_complaint', self.case_stages['pre_complaint']['name'], 'fallback'

    def _summarize_case_facts(self, case_info: Dict) -> str:
        parts: List[str] = []
        incident_date = self._clean_placeholder(case_info.get('incident_date'), '')
        if incident_date:
            parts.append(f"📅 تاریخ وقوع: {incident_date}")

        incident_desc = self._clean_placeholder(case_info.get('incident_description'), '')
        if incident_desc:
            trimmed = incident_desc.strip()
            if len(trimmed) > 900:
                trimmed = trimmed[:900].rstrip() + '...'
            parts.append("📝 شرح ماجرا:\n" + trimmed)

        actions = self._split_to_list(case_info.get('actions_taken'))
        if actions:
            action_lines = '\n'.join(f"• {item}" for item in actions)
            parts.append("🔄 اقدامات انجام شده تاکنون:\n" + action_lines)

        if not parts:
            return 'شرح کامل واقعه هنوز ثبت نشده است؛ لطفاً جزئیات بیشتری را در پرونده اضافه کنید.'
        return '\n\n'.join(parts)

    def _build_documents_section(self, documents: List[str]) -> str:
        if not documents:
            return 'مدرک مشخصی معرفی نشده است. توصیه می‌شود فهرست دقیق مدارک را پیش از تقدیم سند تکمیل کنید.'
        return '\n'.join(f"• {doc}" for doc in documents)

    def _prepare_context(self, doc_type: str, case_info: Dict) -> Dict:
        stage_key, stage_label, stage_source = self._detect_case_stage_key(case_info)

        missing_fields: List[Dict[str, str]] = []

        case_title = self._clean_placeholder(case_info.get('case_title'), 'پرونده بدون عنوان')
        if case_title == 'پرونده بدون عنوان':
            missing_fields.append({'key': 'case_title', 'field': 'عنوان پرونده', 'prompt': 'عنوان پرونده را مشخص کن.'})

        client_name = self._clean_placeholder(case_info.get('client_name'), '[نام موکل]')
        if client_name == '[نام موکل]':
            missing_fields.append({'key': 'client_name', 'field': 'نام موکل', 'prompt': 'نام و نام خانوادگی کامل موکل را بنویس.'})

        opponent_name = self._clean_placeholder(case_info.get('opponent_name'), '[نام طرف مقابل]')
        if opponent_name == '[نام طرف مقابل]':
            missing_fields.append({'key': 'opponent_name', 'field': 'نام طرف مقابل', 'prompt': 'نام و مشخصات طرف مقابل را وارد کن.'})

        complaint_side = self._clean_placeholder(case_info.get('complaint_side'), 'موکل')
        if complaint_side == 'موکل':
            missing_fields.append({'key': 'complaint_side', 'field': 'نقش موکل', 'prompt': 'مشخص کن که موکل شاکی/خواهان است یا خوانده/متهم.'})

        case_number = self._clean_placeholder(case_info.get('case_number'), 'نامشخص')
        if case_number == 'نامشخص':
            missing_fields.append({'key': 'case_number', 'field': 'شماره پرونده', 'prompt': 'اگر شماره پرونده صادر شده، دقیقاً بنویس؛ در غیر این صورت ذکر کن که هنوز دریافت نشده.'})

        court_branch = self._clean_placeholder(case_info.get('court_branch'), 'مرجع قضایی مربوطه')
        if court_branch == 'مرجع قضایی مربوطه':
            missing_fields.append({'key': 'court_branch', 'field': 'شعبه رسیدگی', 'prompt': 'شعبه یا محل دادگاهی که پرونده در آن مطرح است را وارد کن.'})

        case_goal = self._clean_placeholder(case_info.get('case_goal'), 'تعیین نشده')
        if case_goal == 'تعیین نشده':
            missing_fields.append({'key': 'case_goal', 'field': 'هدف پرونده / خواسته', 'prompt': 'هدف یا خواسته اصلی موکل از طرح پرونده چیست؟'})

        incident_desc = case_info.get('incident_description')
        if not incident_desc or self._normalize_for_lookup(str(incident_desc)) in {'', 'در مکالمه ذکر نشد'}:
            missing_fields.append({'key': 'incident_description', 'field': 'شرح کامل ماجرا', 'prompt': 'جزئیات دقیق اتفاق یا اختلاف را شرح بده.'})

        documents_list = self._split_to_list(case_info.get('available_documents'))
        case_category = self._resolve_case_category(case_info)
        law_fallback = self._get_default_laws(case_info)

        context = {
            'stage_key': stage_key,
            'stage_label': stage_label,
            'stage_source': stage_source,
            'case_title': case_title,
            'client_name': client_name,
            'opponent_name': opponent_name,
            'complaint_side': complaint_side,
            'case_number': case_number,
            'court_branch': court_branch,
            'case_goal': case_goal,
            'documents_list': documents_list,
            'facts_summary': self._summarize_case_facts(case_info),
            'case_category': case_category,
            'doc_label': self.document_labels.get(doc_type, 'سند حقوقی'),
            'requested_relief': case_goal,
            'law_summary': law_fallback.get('laws_text', ''),
            'documents_section': self._build_documents_section(documents_list),
            'case_info': case_info,
            'today': datetime.now().strftime('%Y/%m/%d'),
            'missing_fields': missing_fields
        }
        return context

    def _compose_document_instructions(self, doc_type: str, context: Dict) -> str:
        destination = context.get('court_branch') or 'مرجع قضایی مربوطه'
        stage_label = context.get('stage_label')
        case_title = context.get('case_title')
        doc_label = context.get('doc_label', 'سند حقوقی')

        lines = [
            f"✅ متن {doc_label} برای پرونده «{case_title}» آماده شد.",
            f"لطفاً متن را مرور کن، در صورت نیاز اصلاحات نهایی را اعمال کن و سپس آن را به {destination} تقدیم کن."
        ]

        if stage_label and stage_label not in {'', 'مرحله نامشخص'}:
            lines.append(f"🔎 مرحله تشخیص داده‌شده پرونده: {stage_label}.")

        if doc_type == 'petition':
            lines.append('✉️ این لایحه برای ارائه توضیحات تکمیلی آماده شده است؛ مدارک پشتیبان را ضمیمه فراموش نکن.')
        elif doc_type == 'defense':
            lines.append('⚔️ این دفاعیه بر اساس شرح ماجرا و مدارک ثبت شده تهیه گردید؛ حتماً در جلسه دادگاه نسخه چاپی و مستندات را همراه داشته باش.')
        elif doc_type == 'lawsuit':
            lines.append('📥 پیش از ثبت دادخواست، پیوست‌ها و هزینه دادرسی را آماده کن.')
        elif doc_type == 'appeal':
            lines.append('🔁 این متن را به همراه ضمائم و دادنامه بدوی در مهلت قانونی تجدیدنظر ثبت کن.')

        missing_fields = context.get('missing_fields') or []
        if missing_fields:
            field_titles = [item.get('field') for item in missing_fields if item.get('field')]
            if field_titles:
                lines.append('⚠️ برای کامل شدن سند، این موارد را در پرونده ثبت یا تکمیل کن: ' + '، '.join(field_titles))

        return '\n'.join(lines)
    
    def analyze_case_status(self, case_info: Dict) -> Dict:
        """
        تحلیل وضعیت فعلی پرونده و تعیین اقدامات لازم
        """
        complaint_side = case_info.get('complaint_side', '')

        current_stage_key, detected_stage_label, stage_source = self._detect_case_stage_key(case_info)
        current_stage = self.case_stages.get(current_stage_key, self.case_stages['pre_complaint'])

        # هم‌تراز کردن نام مرحله با خروجی تشخیص
        stage_display_name = current_stage.get('name', detected_stage_label)
        if detected_stage_label and detected_stage_label not in {'', 'مرحله نامشخص'}:
            stage_display_name = detected_stage_label

        case_info.setdefault('case_stage', stage_display_name)

        # اقدامات فوری
        urgent_actions: List[str] = []
        if current_stage_key == 'pre_complaint':
            urgent_actions = [
                '📝 تنظیم دادخواست',
                '📄 جمع‌آوری مدارک',
                '💰 محاسبه خسارت و هزینه'
            ]
        elif current_stage_key == 'complaint_filed':
            urgent_actions = [
                '📨 پیگیری ابلاغ شعبه و وقت رسیدگی',
                '📑 آماده‌سازی مستندات برای جلسه',
                '🗂️ مرتب‌سازی پرونده و پیوست‌ها'
            ]
        elif current_stage_key == 'court_session':
            urgent_actions = [
                '⚖️ تنظیم دفاعیه',
                '📋 آماده‌سازی لایحه',
                '📎 تکمیل مستندات'
            ]
        elif current_stage_key == 'verdict':
            urgent_actions = [
                '🔍 بررسی دقیق رأی',
                '⚖️ ارزیابی امکان تجدیدنظر',
                '✅ اجرای حکم (در صورت موافقت)'
            ]
        elif current_stage_key == 'appeal':
            urgent_actions = [
                '✍️ تنظیم دادخواست تجدیدنظر ظرف مهلت مقرر',
                '📑 جمع‌آوری دلایل و مستندات جدید',
                '📮 ثبت دادخواست در دفتر خدمات قضایی'
            ]
        elif current_stage_key == 'execution':
            urgent_actions = [
                '🏛️ مراجعه به دایره اجرای احکام',
                '📨 پیگیری صدور اجرائیه',
                '💰 برنامه‌ریزی برای وصول محکوم‌به'
            ]

        strategy = self._generate_strategy(case_info, current_stage_key)
        risks_opportunities = self._analyze_risks_opportunities(case_info, current_stage_key)

        return {
            'current_stage': {**current_stage, 'name': stage_display_name},
            'current_stage_key': current_stage_key,
            'stage_display': stage_display_name,
            'stage_detected_from': stage_source,
            'urgent_actions': urgent_actions,
            'strategy': strategy,
            'risks': risks_opportunities['risks'],
            'opportunities': risks_opportunities['opportunities'],
            'next_steps': current_stage.get('actions', []),
            'required_documents': current_stage.get('documents', [])
        }
    
    def _generate_strategy(self, case_info: Dict, stage: str) -> str:
        """تولید استراتژی بر اساس نوع پرونده و مرحله"""
        complaint_side = self._normalize_for_lookup(case_info.get('complaint_side', ''))
        is_claimant = any(keyword in complaint_side for keyword in ['شاکی', 'خواهان', 'plaintiff', 'complainant'])

        if is_claimant:
            if stage == 'pre_complaint':
                return """**استراتژی تهاجمی:**
• جمع‌آوری حداکثر مدارک و شواهد
• تنظیم دادخواست قوی و مستدل
• محاسبه دقیق خسارات
• آماده‌سازی برای دفاع از خواسته"""
            if stage == 'complaint_filed':
                return """**استراتژی پیگیری:**
• رصد ابلاغیه‌ها و تعیین وقت دادگاه
• تکمیل ضمایم و برطرف کردن نواقص احتمالی
• آماده‌سازی فهرست شهود و کارشناسان مورد نیاز
• تهیه خلاصه پرونده برای ارائه در جلسه اول"""
            if stage == 'court_session':
                return """**استراتژی اثبات:**
• ارائه مستندات قوی و منظم
• پاسخ سریع و مستدل به ایرادات طرف مقابل
• تأکید بر جنبه‌های قانونی و قراردادی حق
• درخواست تصمیم مقتضی بر اساس خواسته"""
            if stage == 'verdict':
                return """**استراتژی پس از رأی:**
• بررسی دقیق دادنامه و مهلت اعتراض
• تحلیل نقاط قوت و ضعف رأی صادره
• تصمیم‌گیری درباره اجرای فوری یا اعتراض
• آماده‌سازی اسناد لازم برای مرحله بعد"""
            if stage == 'appeal':
                return """**استراتژی تجدیدنظرخواهی:**
• تدوین ایرادات شکلی و ماهوی رأی بدوی
• جمع‌آوری دلایل و مستندات تازه یا مغفول
• تمرکز بر نقض قانون یا تشریفات در رأی بدوی
• رعایت کامل مهلت‌ها و ضمائم الزامی دادخواست"""
            if stage == 'execution':
                return """**استراتژی اجرای حکم:**
• درخواست صدور اجرائیه و تشکیل پرونده اجرا
• شناسایی اموال و مطالبات محکوم‌علیه
• پیگیری مداوم اقدامات واحد اجرا تا وصول حق
• برنامه‌ریزی برای وصول سریع و کاهش هزینه‌ها"""
        else:
            if stage == 'pre_complaint':
                return """**استراتژی دفاعی:**
• بررسی دقیق ادعای طرف مقابل
• شناسایی نقاط ضعف شکایت
• آماده‌سازی دفاعیات قوی
• جمع‌آوری مدارک نقض ادعا"""
            if stage == 'complaint_filed':
                return """**استراتژی آمادگی دفاع:**
• مطالعه دادخواست و مستندات پیوست
• جمع‌آوری مدارک نقض ادعاها
• تدوین پیش‌نویس دفاعیه و فهرست شهود احتمالی
• درخواست دسترسی به مدارک و دلایل مورد نیاز"""
            if stage == 'court_session':
                return """**استراتژی دفاع:**
• رد ادعای طرف مقابل با استدلال دقیق
• ارائه مستندات دفاعی و گزارش‌های کارشناسی
• اثبات بی‌اساس بودن خواسته یا کاهش مسئولیت
• درخواست رد یا تعدیل دعوا"""
            if stage == 'verdict':
                return """**استراتژی پس از رأی علیه موکل:**
• استخراج ایرادات رأی برای اعتراض قانونی
• سنجش هزینه و فایده تجدیدنظر یا اجرای داوطلبانه
• آماده‌سازی مستندات حمایتی مرحله بعد
• مذاکره برای مصالحه در صورت توجیه اقتصادی"""
            if stage == 'appeal':
                return """**استراتژی دفاع در تجدیدنظر:**
• پاسخ مستدل به ایرادات تجدیدنظرخواه
• تقویت رأی بدوی با مستندات مکمل
• تبیین رعایت تشریفات و مقررات توسط دادگاه بدوی
• آماده‌سازی دفاع کتبی یا شفاهی در مرجع بالاتر"""
            if stage == 'execution':
                return """**استراتژی مدیریت اجرای حکم:**
• بررسی مفاد اجرائیه و مهلت‌های پرداخت
• مذاکره برای تقسیط یا تعلیق اجرای حکم در صورت امکان
• ارائه دلایل قانونی برای توقف یا اصلاح اجرا
• پایش اقدامات دایره اجرا و ثبت اعتراض‌های لازم"""

        return "استراتژی بر اساس تحلیل دقیق پرونده"
    
    def _analyze_risks_opportunities(self, case_info: Dict, stage: str) -> Dict:
        """تحلیل ریسک‌ها و فرصت‌های پرونده"""
        risks = []
        opportunities = []
        
        # بررسی مدارک
        if not case_info.get('available_documents') or case_info.get('available_documents') == '(در مکالمه ذکر نشد)':
            risks.append('⚠️ عدم وجود مدارک کافی')
        else:
            opportunities.append('✅ وجود مدارک و مستندات')
        
        # بررسی شماره پرونده
        if case_info.get('case_number') and case_info.get('case_number') != '(ندارد)':
            opportunities.append('✅ پرونده ثبت شده و دارای شماره')
        else:
            if stage != 'pre_complaint':
                risks.append('⚠️ عدم ثبت رسمی پرونده')
        
        # بررسی ضرب‌الاجل
        if case_info.get('deadlines') and case_info.get('deadlines') != '(ندارد)':
            risks.append('⏰ وجود ضرب‌الاجل - نیاز به اقدام فوری')
        
        # بررسی مرحله
        if stage == 'verdict':
            opportunities.append('📊 امکان ارزیابی نتیجه و تصمیم‌گیری')
        
        if stage == 'appeal':
            opportunities.append('🔄 فرصت بازبینی و اصلاح')
        
        return {
            'risks': risks if risks else ['بدون ریسک مشخص'],
            'opportunities': opportunities if opportunities else ['نیاز به بررسی بیشتر']
        }

    def _resolve_case_category(self, case_info: Dict) -> str:
        """تشخیص اینکه پرونده بیشتر ماهیت کیفری دارد یا حقوقی"""
        case_type = (case_info.get('case_type') or '').lower()
        incident = (case_info.get('incident_description') or '').lower()
        complaint_side = (case_info.get('complaint_side') or '').lower()

        keywords_criminal = ['کیف', 'جرم', 'جزا', 'شکایت کیفری', 'سرقت', 'کلاهبرداری', 'ضرب', 'criminal']
        keywords_civil = ['حقوق', 'حقوقی', 'مطالبه', 'مهریه', 'نفقه', 'خانواده', 'قرارداد', 'civil', 'family', 'املاک', 'دیون']

        if any(k in case_type for k in keywords_criminal) or any(k in incident for k in keywords_criminal):
            return 'criminal'
        if any(k in case_type for k in keywords_civil) or any(k in incident for k in keywords_civil):
            return 'civil'
        if 'شاکی' in complaint_side or 'متهم' in complaint_side:
            return 'criminal'
        return 'civil'

    def _build_document_plan(self, case_info: Dict, analysis: Dict) -> Optional[Dict]:
        """ایجاد برنامه آماده‌سازی اسناد متناسب با مرحله پرونده"""

        category = self._resolve_case_category(case_info)
        playbook = self.document_playbook.get(category, {})
        if not playbook:
            return None

        stage_key = analysis.get('current_stage_key', 'pre_complaint')
        stage_name = analysis.get('current_stage', {}).get('name', 'مرحله نامشخص')
        role_label = case_info.get('complaint_side') or 'موکل'

        bucket_plan: List[Tuple[str, str]] = []
        if stage_key in ('pre_complaint', 'complaint_filed'):
            bucket_plan.append(('initial', 'برای تکمیل تشکیل پرونده'))
            bucket_plan.append(('defense', 'تا جلسه‌ی رسیدگی آماده باشد'))
        elif stage_key == 'court_session':
            bucket_plan.append(('defense', 'برای جلسه دادگاه پیش رو'))
            bucket_plan.append(('initial', 'اگر هنوز تقدیم نشده‌اند، پیش از جلسه تکمیلشان کن'))
        elif stage_key in ('verdict', 'appeal'):
            bucket_plan.append(('follow_up', 'برای اعتراض یا پیگیری پس از رأی'))
            bucket_plan.append(('defense', 'در صورت برگزاری جلسه رسیدگی مجدد'))
        elif stage_key == 'execution':
            bucket_plan.append(('follow_up', 'برای اجرای حکم یا اقدامات تکمیلی'))
        else:
            bucket_plan.append(('initial', 'برای تکمیل مدارک عمومی پرونده'))

        messages: List[str] = []
        added_docs = set()
        for bucket, context_note in bucket_plan:
            docs = playbook.get(bucket) or []
            filtered_docs = [doc for doc in docs if doc not in added_docs]
            if not filtered_docs:
                continue
            added_docs.update(filtered_docs)
            header = "🗂️ **{}**".format(context_note)
            lines = [header]
            for doc in filtered_docs:
                lines.append(f"• تا جلسه بعدی این مورد را آماده کن و در صورت امکان به دادگاه تقدیم کن: {doc}")
            messages.append("\n".join(lines))

        if not messages:
            return None

        category_label = 'کیفری' if category == 'criminal' else 'حقوقی'
        summary = (
            f"این برنامه اسنادی بر اساس پرونده {category_label} شما و مرحله «{stage_name}» آماده شد."
        )

        return {
            'category': category,
            'category_label': category_label,
            'stage': stage_name,
            'role': role_label,
            'messages': messages,
            'summary': summary
        }
    
    def generate_document(
        self,
        doc_type: str,
        case_info: Dict,
        additional_info: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        تولید اسناد حقوقی (دادخواست، لایحه، دفاعیه)
        """
        ctx = self._prepare_context(doc_type, case_info)
        builders = {
            'lawsuit': self._build_lawsuit_document,
            'defense': self._build_defense_document,
            'petition': self._build_petition_document,
            'appeal': self._build_appeal_document
        }

        builder = builders.get(doc_type)
        missing_info = ctx.get('missing_fields') or []
        needs_info = bool(missing_info)

        document_text = ""
        instructions = ""

        if needs_info:
            prompts = [item.get('prompt') or item.get('field') or '' for item in missing_info]
            prompt_lines = ['• ' + p.strip() for p in prompts if p and p.strip()]
            instructions = 'برای تنظیم این سند، ابتدا اطلاعات زیر را تکمیل کن:'
            if prompt_lines:
                instructions += '\n' + '\n'.join(prompt_lines)
        elif builder:
            document_text = builder(ctx, additional_info or {})
            instructions = self._compose_document_instructions(doc_type, ctx)
        else:
            document_text = "نوع سند نامعتبر است"

        return {
            'text': document_text.strip(),
            'instructions': instructions,
            'stage_key': ctx.get('stage_key'),
            'stage_label': ctx.get('stage_label'),
            'doc_label': ctx.get('doc_label'),
            'case_title': ctx.get('case_title'),
            'needs_info': needs_info,
            'missing_fields': missing_info
        }
    
    def _build_lawsuit_document(self, context: Dict, additional_info: Dict) -> str:
        legal_section = additional_info.get('legal_references') or context.get('law_summary', '')
        legal_section = legal_section.strip() or 'مواد قانونی مرتبط مطابق ماهیت دعوا پس از بررسی نهایی درج خواهد شد.'

        requested_relief = additional_info.get('requested_relief') or context.get('requested_relief') or 'صدور حکم به نفع خواهان'

        return f"""📜 **{context['doc_label']}**

**پرونده:** {context['case_title']}
**مرجع رسیدگی:** {context['court_branch']}
**شماره پرونده:** {context['case_number']}
**خواهان:** {context['client_name']}
**خوانده:** {context['opponent_name']}

---
📝 **شرح ماوقع:**
{context['facts_summary']}

🎯 **خواسته:**
{requested_relief}

⚖️ **مستندات قانونی پیشنهادی:**
{legal_section}

📎 **مدارک پیوست:**
{context['documents_section']}

🖊️ **درخواست نهایی:**
با استناد به مطالب فوق و مستندات پیوست، تقاضای صدور حکم بر محکومیت خوانده را دارم.

تاریخ: {context['today']}
امضاء: {context['client_name']}"""

    def _build_defense_document(self, context: Dict, additional_info: Dict) -> str:
        defense_points = additional_info.get('defense_points')
        if not defense_points:
            defense_points = [
                'ادعاهای خواهان فاقد مستند معتبر بوده و با مدارک پیوست نقض می‌شود.',
                'واقعه رخ‌داده بر اساس شرح موکل متفاوت از آن چیزی است که در دادخواست آمده است.',
                'خواهان تکلیف قانونی خود در ارائه دلایل کافی را انجام نداده و ادعای وی مشمول رد است.'
            ]
        defense_body = '\n'.join(f"• {point}" for point in defense_points)

        legal_section = additional_info.get('legal_references') or context.get('law_summary', '')
        legal_section = legal_section.strip() or 'مواد قانونی مرتبط به‌محض نهایی شدن دفاعیات درج خواهد شد.'

        return f"""⚖️ **{context['doc_label']}**

**پرونده:** {context['case_title']}
**مرجع رسیدگی:** {context['court_branch']}
**شماره پرونده:** {context['case_number']}
**خوانده / متهم:** {context['client_name']}
**خواهان / شاکی:** {context['opponent_name']}

---
📝 **بیان دفاعیات:**
{context['facts_summary']}

🛡️ **محورهای دفاعی:**
{defense_body}

⚖️ **مستندات قانونی:**
{legal_section}

📎 **مدارک استنادی:**
{context['documents_section']}

🖊️ **خواسته دفاعی:**
با عنایت به مراتب فوق، تقاضای رد دعوای خواهان و صدور رأی به نفع خوانده را دارم.

تاریخ: {context['today']}
امضاء: {context['client_name']}"""

    def _build_petition_document(self, context: Dict, additional_info: Dict) -> str:
        subject = additional_info.get('subject') or 'ارائه توضیحات تکمیلی'
        points = additional_info.get('points') or [
            'شرح مختصر وضعیت پرونده و دلایل اهمیت موضوع.',
            'توضیح درباره مدارک یا مستندات تازه ضمیمه‌شده.',
            'درخواست مشخص از دادگاه برای اتخاذ تصمیم مورد نظر.'
        ]
        points_text = '\n'.join(f"• {item}" for item in points)

        request_text = additional_info.get('request') or 'با توجه به مطالب فوق، صدور دستور مقتضی مورد تقاضاست.'

        return f"""📋 **{context['doc_label']}**

**پرونده:** {context['case_title']}
**شماره پرونده:** {context['case_number']}
**مرجع رسیدگی:** {context['court_branch']}
**موضوع:** {subject}

---
📝 **شرح مختصر:**
{context['facts_summary']}

🔍 **نکات کلیدی:**
{points_text}

📎 **مدارک پیوست:**
{context['documents_section']}

🖊️ **درخواست:**
{request_text}

تاریخ: {context['today']}
امضاء: {context['client_name']}"""

    def _build_appeal_document(self, context: Dict, additional_info: Dict) -> str:
        appeal_reasons = additional_info.get('reasons') or [
            'دادگاه محترم بدوی در تشخیص وقایع و استناد به مدارک دچار اشتباه گردیده است.',
            'حکم صادره مخالف صریح مواد قانونی مرتبط با موضوع دعوا می‌باشد.',
            'تشریفات دادرسی از جمله حق دفاع و استماع اظهارات به نحو کامل رعایت نشده است.'
        ]
        reason_text = '\n'.join(f"• {reason}" for reason in appeal_reasons)

        requested_order = additional_info.get('requested_order') or 'نقض رأی بدوی و صدور حکم مقتضی به نفع تجدیدنظرخواه.'

        return f"""🔁 **{context['doc_label']}**

**پرونده:** {context['case_title']}
**شماره پرونده بدوی:** {context['case_number']}
**مرجع تجدیدنظر:** {context['court_branch']}
**تجدیدنظرخواه:** {context['client_name']}
**تجدیدنظرخوانده:** {context['opponent_name']}

---
📝 **خلاصه ماوقع:**
{context['facts_summary']}

⚖️ **جهات تجدیدنظر:**
{reason_text}

📎 **ضمائم و مستندات:**
{context['documents_section']}

🖊️ **خواسته:**
{requested_order}

تاریخ: {context['today']}
امضاء: {context['client_name']}"""
    
    def generate_checklist(self, stage: str, case_info: Dict) -> List[Dict]:
        """
        تولید چک‌لیست اقدامات برای هر مرحله
        """
        checklist = []
        
        if stage == 'pre_complaint':
            checklist = [
                {'id': 1, 'task': 'جمع‌آوری کامل مدارک', 'status': 'pending', 'priority': 'high'},
                {'id': 2, 'task': 'تنظیم دادخواست', 'status': 'pending', 'priority': 'high'},
                {'id': 3, 'task': 'محاسبه خسارت و هزینه دادرسی', 'status': 'pending', 'priority': 'medium'},
                {'id': 4, 'task': 'تهیه نسخه‌های لازم', 'status': 'pending', 'priority': 'medium'},
                {'id': 5, 'task': 'مراجعه به دادگاه و ثبت دادخواست', 'status': 'pending', 'priority': 'high'}
            ]
        elif stage == 'complaint_filed':
            checklist = [
                {'id': 1, 'task': 'کنترل ابلاغیه‌ها و دریافت کلاسه پرونده', 'status': 'pending', 'priority': 'high'},
                {'id': 2, 'task': 'رفع نواقص احتمالی پرونده نزد دفتر خدمات', 'status': 'pending', 'priority': 'medium'},
                {'id': 3, 'task': 'مرتب‌سازی مستندات برای جلسه اول رسیدگی', 'status': 'pending', 'priority': 'high'},
                {'id': 4, 'task': 'تهیه خلاصه پرونده و سوالات برای شهود', 'status': 'pending', 'priority': 'medium'}
            ]
        elif stage == 'court_session':
            checklist = [
                {'id': 1, 'task': 'تنظیم دفاعیه', 'status': 'pending', 'priority': 'high'},
                {'id': 2, 'task': 'آماده‌سازی مستندات', 'status': 'pending', 'priority': 'high'},
                {'id': 3, 'task': 'مطالعه پرونده', 'status': 'pending', 'priority': 'medium'},
                {'id': 4, 'task': 'حضور در جلسه دادگاه', 'status': 'pending', 'priority': 'high'},
                {'id': 5, 'task': 'ارائه دفاعیات', 'status': 'pending', 'priority': 'high'}
            ]
        elif stage == 'verdict':
            checklist = [
                {'id': 1, 'task': 'دریافت رأی', 'status': 'pending', 'priority': 'high'},
                {'id': 2, 'task': 'بررسی و تحلیل رأی', 'status': 'pending', 'priority': 'high'},
                {'id': 3, 'task': 'ارزیابی امکان تجدیدنظر', 'status': 'pending', 'priority': 'medium'},
                {'id': 4, 'task': 'اقدام برای اجرا یا تجدیدنظر', 'status': 'pending', 'priority': 'high'}
            ]
        elif stage == 'appeal':
            checklist = [
                {'id': 1, 'task': 'تهیه دادخواست تجدیدنظر و ضمائم اجباری', 'status': 'pending', 'priority': 'high'},
                {'id': 2, 'task': 'تدوین ایرادات رأی بدوی', 'status': 'pending', 'priority': 'high'},
                {'id': 3, 'task': 'ثبت دادخواست در مهلت قانونی', 'status': 'pending', 'priority': 'high'},
                {'id': 4, 'task': 'پیگیری ارجاع پرونده به شعبه تجدیدنظر', 'status': 'pending', 'priority': 'medium'}
            ]
        elif stage == 'execution':
            checklist = [
                {'id': 1, 'task': 'درخواست صدور اجرائیه', 'status': 'pending', 'priority': 'high'},
                {'id': 2, 'task': 'پیگیری تشکیل پرونده اجرا', 'status': 'pending', 'priority': 'high'},
                {'id': 3, 'task': 'شناسایی اموال محکوم‌علیه', 'status': 'pending', 'priority': 'medium'},
                {'id': 4, 'task': 'پیگیری وصول محکوم‌به', 'status': 'pending', 'priority': 'high'}
            ]
        
        return checklist
    
    def suggest_next_actions(self, case_info: Dict, analysis: Dict) -> List[str]:
        """پیشنهاد اقدامات بعدی"""
        actions = []
        stage = analysis['current_stage_key']
        
        # اقدامات فوری
        if analysis['risks']:
            actions.append(f"🚨 **اقدام فوری:** {analysis['risks'][0]}")
        
        # اقدامات بر اساس مرحله
        if stage == 'pre_complaint':
            actions.extend([
                "📝 **گام 1:** تنظیم دادخواست با جزئیات کامل",
                "📎 **گام 2:** جمع‌آوری و مرتب‌سازی تمام مدارک",
                "💰 **گام 3:** محاسبه دقیق خسارت و هزینه‌ها",
                "📋 **گام 4:** ارائه دادخواست به دادگاه"
            ])
        elif stage == 'complaint_filed':
            actions.extend([
                "📨 **گام 1:** بررسی ابلاغیه‌ها و دریافت وقت رسیدگی",
                "🗂️ **گام 2:** رفع نواقص و تکمیل ضمائم پرونده",
                "🧾 **گام 3:** تنظیم فهرست مدارک برای ارائه در جلسه",
                "🎤 **گام 4:** هماهنگی با شهود یا کارشناسان احتمالی"
            ])
        elif stage == 'court_session':
            actions.extend([
                "⚖️ **گام 1:** تنظیم دفاعیه قوی و مستدل",
                "📊 **گام 2:** آماده‌سازی برای جلسه دادگاه",
                "🎯 **گام 3:** پاسخ به ایرادات طرف مقابل",
                "✅ **گام 4:** پیگیری صدور رأی"
            ])
        elif stage == 'verdict':
            actions.extend([
                "🔍 **گام 1:** بررسی دقیق متن رأی",
                "⚖️ **گام 2:** ارزیابی موافقت یا اعتراض",
                "📝 **گام 3:** در صورت عدم موافقت، تجدیدنظرخواهی",
                "✅ **گام 4:** در صورت موافقت، اجرای حکم"
            ])
        elif stage == 'appeal':
            actions.extend([
                "✍️ **گام 1:** تدوین دادخواست تجدیدنظر و ایرادات قانونی",
                "📑 **گام 2:** ضمیمه کردن اسناد و دلایل جدید",
                "📮 **گام 3:** ثبت دادخواست و پیگیری ارجاع به شعبه",
                "🗓️ **گام 4:** آماده‌سازی برای دفاع در جلسه تجدیدنظر"
            ])
        elif stage == 'execution':
            actions.extend([
                "🏛️ **گام 1:** درخواست صدور اجرائیه و تشکیل پرونده اجرا",
                "📍 **گام 2:** شناسایی اموال و محل‌های قابل توقیف",
                "📞 **گام 3:** پیگیری مستمر شعبه اجرای احکام",
                "🤝 **گام 4:** بررسی امکان مصالحه یا تقسیط محکوم‌به"
            ])
        
        return actions
    
    def analyze_with_ai(self, case_info: Dict) -> Optional[Dict]:
        """
        تحلیل هوشمند پرونده با استفاده از AI
        """
        try:
            import os
            import requests
            
            api_key = os.getenv('DEEPSEEK_API_KEY', '').strip()
            if not api_key:
                return None
            
            # آماده‌سازی prompt
            prompt = f"""به عنوان یک وکیل خبره، این پرونده را تحلیل کن و موارد زیر را ارائه بده:

📁 **مشخصات پرونده:**
• عنوان: {case_info.get('case_title', 'نامشخص')}
• نوع: {case_info.get('case_type', 'نامشخص')}
• موقعیت موکل: {case_info.get('complaint_side', 'نامشخص')}
• مرحله: {case_info.get('case_stage', 'نامشخص')}

📝 **شرح ماجرا:**
{case_info.get('incident_description', 'ذکر نشده')[:500]}

📄 **مدارک:**
{case_info.get('available_documents', 'ذکر نشده')}

🎯 **هدف موکل:**
{case_info.get('case_goal', 'ذکر نشده')}

لطفاً موارد زیر را به صورت دقیق و حرفه‌ای ارائه بده:

1. **نقاط قوت پرونده** (3-4 مورد)
2. **نقاط ضعف و ریسک‌ها** (3-4 مورد)
3. **استراتژی پیشنهادی** (مختصر و کاربردی)
4. **احتمال موفقیت** (درصد تقریبی با توضیح کوتاه)
5. **اقدامات فوری** (3-4 مورد اولویت‌دار)

پاسخ را فارسی، مختصر و کاربردی بنویس."""

            model = os.getenv('DEEPSEEK_MODEL', '').strip() or 'deepseek-chat'
            base_url = os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com').strip()
            
            if not base_url.endswith('/v1'):
                base_url = base_url.rstrip('/') + '/v1'
            
            response = requests.post(
                f"{base_url}/chat/completions",
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': model,
                    'messages': [{'role': 'user', 'content': prompt}],
                    'temperature': 0.7,
                    'max_tokens': 1500
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                analysis_text = data.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
                
                if analysis_text and len(analysis_text) > 100:
                    return {
                        'ai_analysis': analysis_text,
                        'success': True
                    }
            
            return None
            
        except Exception as e:
            print(f"Error in AI analysis: {e}")
            return None
    
    def detect_relevant_laws(self, case_info: Dict) -> Dict:
        """
        تشخیص قوانین و مواد مرتبط با پرونده
        """
        try:
            import os
            import requests
            
            api_key = os.getenv('DEEPSEEK_API_KEY', '').strip()
            if not api_key:
                return self._get_default_laws(case_info)
            
            prompt = f"""بر اساس این پرونده حقوقی، مواد قانونی مرتبط از قوانین ایران را مشخص کن:

نوع پرونده: {case_info.get('case_type', 'نامشخص')}
شرح: {case_info.get('incident_description', 'ذکر نشده')[:300]}

لطفاً موارد زیر را ارائه بده:
1. قانون اصلی مرتبط (مثلاً قانون مدنی، قانون مجازات اسلامی)
2. 3-5 ماده مهم و کاربردی
3. توضیح مختصر هر ماده (یک خط)

فرمت پاسخ:
**قانون:** [نام قانون]
**مواد مرتبط:**
- ماده [شماره]: [توضیح مختصر]
- ماده [شماره]: [توضیح مختصر]
..."""

            model = os.getenv('DEEPSEEK_MODEL', '').strip() or 'deepseek-chat'
            base_url = os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com').strip()
            
            if not base_url.endswith('/v1'):
                base_url = base_url.rstrip('/') + '/v1'
            
            response = requests.post(
                f"{base_url}/chat/completions",
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': model,
                    'messages': [{'role': 'user', 'content': prompt}],
                    'temperature': 0.5,
                    'max_tokens': 800
                },
                timeout=20
            )
            
            if response.status_code == 200:
                data = response.json()
                laws_text = data.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
                
                if laws_text and len(laws_text) > 50:
                    return {
                        'laws_text': laws_text,
                        'source': 'ai',
                        'success': True
                    }
            
            return self._get_default_laws(case_info)
            
        except Exception as e:
            print(f"Error detecting laws: {e}")
            return self._get_default_laws(case_info)
    
    def _get_default_laws(self, case_info: Dict) -> Dict:
        """قوانین پیش‌فرض بر اساس نوع پرونده"""
        case_type = case_info.get('case_type', 'other')
        
        laws_map = {
            'civil': {
                'law_name': 'قانون مدنی',
                'articles': [
                    'مواد 10 و 219: اعتبار قراردادها',
                    'ماده 230: شرایط صحت معامله',
                    'مواد 515-520: خسارات وارده'
                ]
            },
            'criminal': {
                'law_name': 'قانون مجازات اسلامی',
                'articles': [
                    'کتاب تعزیرات: جرائم عمومی',
                    'فصل مربوط به جرم خاص',
                    'مواد مربوط به شکایت و دیه'
                ]
            },
            'family': {
                'law_name': 'قانون حمایت خانواده',
                'articles': [
                    'مواد مربوط به طلاق',
                    'مواد مربوط به نفقه و حضانت',
                    'مواد مربوط به مهریه'
                ]
            },
            'commercial': {
                'law_name': 'قانون تجارت',
                'articles': [
                    'مواد مربوط به چک و سفته',
                    'مواد مربوط به شرکت‌های تجاری',
                    'قانون ورشکستگی'
                ]
            },
            'labor': {
                'law_name': 'قانون کار',
                'articles': [
                    'مواد مربوط به قرارداد کار',
                    'مواد مربوط به اخراج',
                    'مواد مربوط به بیمه و حقوق'
                ]
            },
            'property': {
                'law_name': 'قانون مدنی (املاک)',
                'articles': [
                    'مواد مربوط به مالکیت',
                    'مواد مربوط به اجاره',
                    'مواد مربوط به تخلیه'
                ]
            }
        }
        
        law_info = laws_map.get(case_type, {
            'law_name': 'قوانین عمومی',
            'articles': ['نیاز به بررسی دقیق‌تر']
        })
        
        laws_text = f"""**قانون:** {law_info['law_name']}

**مواد مرتبط:**
"""
        for article in law_info['articles']:
            laws_text += f"• {article}\n"
        
        laws_text += "\n⚠️ **توجه:** این فهرست کلی است. برای مشاوره دقیق به متن کامل قوانین مراجعه کنید."
        
        return {
            'laws_text': laws_text,
            'source': 'default',
            'success': True
        }
    
    def predict_outcome(self, case_info: Dict, analysis: Dict) -> Dict:
        """
        پیش‌بینی نتایج احتمالی پرونده
        """
        try:
            import os
            import requests
            
            api_key = os.getenv('DEEPSEEK_API_KEY', '').strip()
            if not api_key:
                return self._get_default_prediction(case_info, analysis)
            
            prompt = f"""به عنوان یک وکیل با تجربه، نتایج احتمالی این پرونده را پیش‌بینی کن:

**مشخصات:**
• نوع: {case_info.get('case_type', '')}
• موقعیت: {case_info.get('complaint_side', '')}
• مرحله: {case_info.get('case_stage', '')}
• مدارک: {case_info.get('available_documents', '')[:200]}

**شرح:**
{case_info.get('incident_description', '')[:300]}

**هدف:**
{case_info.get('case_goal', '')}

لطفاً موارد زیر را ارائه بده:
1. **احتمال موفقیت کامل:** [درصد تقریبی و دلیل]
2. **احتمال موفقیت جزئی:** [درصد و توضیح]
3. **احتمال عدم موفقیت:** [درصد و دلیل]
4. **بهترین سناریو:** [توضیح مختصر]
5. **بدترین سناریو:** [توضیح مختصر]
6. **توصیه نهایی:** [یک پاراگراف]

پاسخ را فارسی، واقع‌بینانه و حرفه‌ای بنویس."""

            model = os.getenv('DEEPSEEK_MODEL', '').strip() or 'deepseek-chat'
            base_url = os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com').strip()
            
            if not base_url.endswith('/v1'):
                base_url = base_url.rstrip('/') + '/v1'
            
            response = requests.post(
                f"{base_url}/chat/completions",
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': model,
                    'messages': [{'role': 'user', 'content': prompt}],
                    'temperature': 0.6,
                    'max_tokens': 1000
                },
                timeout=25
            )
            
            if response.status_code == 200:
                data = response.json()
                prediction_text = data.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
                
                if prediction_text and len(prediction_text) > 100:
                    return {
                        'prediction_text': prediction_text,
                        'source': 'ai',
                        'success': True
                    }
            
            return self._get_default_prediction(case_info, analysis)
            
        except Exception as e:
            print(f"Error predicting outcome: {e}")
            return self._get_default_prediction(case_info, analysis)
    
    def _get_default_prediction(self, case_info: Dict, analysis: Dict) -> Dict:
        """پیش‌بینی پیش‌فرض بر اساس تحلیل"""
        
        # محاسبه امتیاز بر اساس عوامل مختلف
        score = 50  # پایه
        
        # بررسی مدارک
        if case_info.get('available_documents') and len(case_info.get('available_documents', '')) > 20:
            score += 15
        
        # بررسی موقعیت
        if 'شاکی' in case_info.get('complaint_side', '') or 'خواهان' in case_info.get('complaint_side', ''):
            score += 5
        
        # بررسی ریسک‌ها
        if analysis.get('risks'):
            score -= len(analysis['risks']) * 5
        
        # بررسی فرصت‌ها
        if analysis.get('opportunities'):
            score += len(analysis['opportunities']) * 5
        
        # محدود کردن به بازه 0-100
        score = max(0, min(100, score))
        
        prediction_text = f"""**پیش‌بینی نتایج پرونده:**

**احتمال موفقیت کلی:** حدود {score}%

**تحلیل:**
"""
        
        if score >= 70:
            prediction_text += "با توجه به مستندات و شرایط پرونده، احتمال موفقیت بالاست. "
        elif score >= 50:
            prediction_text += "پرونده دارای شانس متوسطی برای موفقیت است. "
        else:
            prediction_text += "پرونده نیاز به تقویت مستندات و استراتژی دارد. "
        
        prediction_text += f"""

**نکات مهم:**
• تکمیل مستندات می‌تواند شانس موفقیت را افزایش دهد
• مشورت با وکیل مجرب ضروری است
• زمان‌بندی صحیح اقدامات اهمیت دارد

**توصیه:**
پیشنهاد می‌شود با توجه به {analysis.get('current_stage', {}).get('name', 'مرحله فعلی')}، 
اقدامات لازم را با دقت و به موقع انجام دهید.

⚠️ **تذکر:** این پیش‌بینی تقریبی است و نتیجه نهایی به عوامل مختلفی بستگی دارد."""
        
        return {
            'prediction_text': prediction_text,
            'score': score,
            'source': 'default',
            'success': True
        }

    def generate_step_by_step_guidance(
        self,
        case_info: Dict,
        analysis: Optional[Dict] = None,
        law_data: Optional[Dict] = None
    ) -> Dict:
        """تولید راهنمای مرحله‌به‌مرحله برای موکل"""

        analysis = analysis or self.analyze_case_status(case_info)
        law_data = law_data or self.detect_relevant_laws(case_info)

        result = self._generate_guidance_with_ai(case_info, analysis, law_data)
        if not result:
            result = self._build_fallback_guidance(case_info, analysis, law_data)

        if result:
            document_plan = self._build_document_plan(case_info, analysis)
            if document_plan:
                result['document_plan'] = document_plan

        return result

    def _generate_guidance_with_ai(self, case_info: Dict, analysis: Dict, law_data: Optional[Dict]) -> Optional[Dict]:
        """تلاش برای تولید برنامه مرحله‌به‌مرحله با کمک AI"""
        try:
            import os
            import requests

            api_key = os.getenv('DEEPSEEK_API_KEY', '').strip()
            if not api_key:
                return None

            stage_name = analysis.get('current_stage', {}).get('name', 'مرحله نامشخص')
            complaint_side = case_info.get('complaint_side', 'نامشخص')
            goal = case_info.get('case_goal', 'نامشخص')
            urgent_actions = analysis.get('urgent_actions', [])
            next_steps = analysis.get('next_steps', [])
            strategy_text = analysis.get('strategy', '')
            risks = analysis.get('risks', [])
            opportunities = analysis.get('opportunities', [])
            law_overview = (law_data or {}).get('laws_text', '')

            prompt = f"""تو نقش «دادرس هوشمند» را داری؛ یک وکیل پایه یک که با لحن دوستانه و قابل فهم مرحله‌به‌مرحله راهنمایی می‌کند.

مشخصات پرونده:
- عنوان پرونده: {case_info.get('case_title', 'نامشخص')}
- نقش موکل: {complaint_side}
- هدف: {goal}
- مرحله فعلی: {stage_name}

اطلاعات تحلیلی:
- استراتژی پیشنهادی: {strategy_text}
- اقدامات فوری: {', '.join(urgent_actions) or 'موردی ثبت نشده'}
- مراحل بعدی: {', '.join(next_steps) or 'موردی ثبت نشده'}
- فرصت‌ها: {', '.join(opportunities) or 'ذکر نشده'}
- ریسک‌ها: {', '.join(risks) or 'ذکر نشده'}

خلاصه ماجرا:
{case_info.get('incident_description', '')[:600]}

خلاصه قوانین مرتبط:
{law_overview}

لطفاً فقط یک JSON فارسی با ساختار زیر برگردان:
{{
  "steps": [
    {{
      "title": "گام ۱ - ...",
      "summary": "شرح کوتاه و صمیمی",
      "actions": ["کار ۱", "کار ۲"]
    }}
  ],
  "encouragement": "پیام دلگرم‌کننده",
  "legal_summary": "جمع‌بندی کوتاه قوانین (اختیاری)"
}}

شرایط:
- حداکثر 4 گام تهیه کن.
- هر اکشن باید بسیار مشخص و کاربردی باشد.
- لحنت مهربان، ساده و حرفه‌ای باشد.
- اگر قانونی را ذکر می‌کنی شماره ماده یا قانون را بنویس.
- فقط JSON معتبر برگردان؛ توضیح اضافی، متن خارج از JSON یا کد بلاک نیاور."""

            model = os.getenv('DEEPSEEK_MODEL', '').strip() or 'deepseek-chat'
            base_url = os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com').strip()

            if not base_url.endswith('/v1'):
                base_url = base_url.rstrip('/') + '/v1'

            response = requests.post(
                f"{base_url}/chat/completions",
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': model,
                    'messages': [
                        {'role': 'system', 'content': 'You are a helpful Persian legal assistant. Return only JSON strings.'},
                        {'role': 'user', 'content': prompt}
                    ],
                    'temperature': 0.55,
                    'max_tokens': 1000
                },
                timeout=25
            )

            if response.status_code != 200:
                return None

            data = response.json()
            raw_content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
            if not raw_content:
                return None

            cleaned = raw_content.strip()
            if cleaned.startswith('```'):
                cleaned = re.sub(r'^```(?:json)?', '', cleaned, flags=re.IGNORECASE).strip()
                cleaned = re.sub(r'```$', '', cleaned).strip()

            json_match = re.search(r'\{[\s\S]*\}', cleaned)
            if json_match:
                cleaned = json_match.group(0)

            parsed = json.loads(cleaned)
            if not isinstance(parsed, dict):
                return None

            steps_data = parsed.get('steps') or []
            messages = []
            for idx, step in enumerate(steps_data):
                if not isinstance(step, dict):
                    continue
                title = step.get('title') or f"گام {idx+1}"
                summary = (step.get('summary') or '').strip()
                actions = step.get('actions') or []

                text_parts = [f"✅ **{title.strip()}**"]
                if summary:
                    text_parts.append(summary)
                valid_actions = [a.strip() for a in actions if isinstance(a, str) and a.strip()]
                if valid_actions:
                    text_parts.append("\n".join(f"• {a}" for a in valid_actions))

                message = "\n".join(text_parts).strip()
                if message:
                    messages.append(message)

            if not messages:
                return None

            encouragement = (parsed.get('encouragement') or '').strip()
            legal_summary = (parsed.get('legal_summary') or '').strip()

            result = {
                'messages': messages,
                'encouragement': encouragement,
                'source': 'ai'
            }

            if legal_summary:
                result['law_overview'] = legal_summary

            if law_overview and not result.get('law_overview'):
                result['law_overview'] = law_overview

            return result

        except Exception as exc:
            print(f"Error in AI step guidance: {exc}")
            return None

    def _build_fallback_guidance(self, case_info: Dict, analysis: Dict, law_data: Optional[Dict]) -> Dict:
        """راهنمای مرحله‌به‌مرحله در صورت عدم دسترسی به AI"""
        stage_name = analysis.get('current_stage', {}).get('name', 'مرحله نامشخص')
        complaint_side = case_info.get('complaint_side', 'موکل')
        goal = case_info.get('case_goal', '(مشخص نشده)')
        strategy_text = analysis.get('strategy', '')
        urgent_actions = analysis.get('urgent_actions', [])
        next_steps = analysis.get('next_steps', [])
        opportunities = analysis.get('opportunities', [])
        risks = analysis.get('risks', [])
        law_overview = (law_data or {}).get('laws_text', '')

        prediction_baseline = self._get_default_prediction(case_info, analysis)
        success_score = prediction_baseline.get('score')
        prediction_text = prediction_baseline.get('prediction_text', '')

        messages: List[str] = []

        overview_lines = [
            "👣 **گام ۱ – مرور وضعیت فعلی:**",
            f"مرحله فعلی پرونده: {stage_name}",
            f"نقش شما: {complaint_side}",
            f"هدف اعلام‌شده: {goal}"
        ]
        if strategy_text:
            overview_lines.append("\n" + strategy_text.strip())
        if opportunities:
            overview_lines.append("\nفرصت‌ها:" + "\n" + "\n".join(f"• {item}" for item in opportunities))
        if risks:
            overview_lines.append("\nریسک‌های مهم:" + "\n" + "\n".join(f"• {item}" for item in risks))
        messages.append("\n".join(overview_lines).strip())

        urgent_text = urgent_actions if urgent_actions else ['اقدام فوری مشخصی ثبت نشده، اما مرور مدارک و آماده‌سازی خود را ادامه دهید.']
        next_text = next_steps if next_steps else ['مورد خاصی ثبت نشده است.']

        actions_lines = [
            "🛠️ **گام ۲ – اقداماتی که باید انجام دهیم:**",
            "اقدامات فوری:" + "\n" + "\n".join(f"• {item}" for item in urgent_text),
            "\nمراحل بعدی دادگاه:" + "\n" + "\n".join(f"• {item}" for item in next_text)
        ]
        messages.append("\n".join(actions_lines).strip())

        if law_overview:
            messages.append(
                "📚 **گام ۳ – تکیه بر مواد قانونی مرتبط:**\n" + law_overview.strip()
            )

        prediction_lines = ["🎯 **گام ۴ – برآورد مسیر پیش رو:**"]
        if success_score is not None:
            prediction_lines.append(f"برآورد اولیه نشان می‌دهد شانس موفقیت حدود {success_score}٪ است.")
        if prediction_text:
            preview = prediction_text.strip()
            if len(preview) > 600:
                preview = preview[:600] + '...'
            prediction_lines.append(preview)
        messages.append("\n".join(prediction_lines).strip())

        encouragement = (
            "من به عنوان دادرس هوشمند تا پایان همراه شما هستم. هر زمان سوالی داشتید یا نیاز به آماده‌سازی سندی بود، کافیست بگویید تا مرحله بعد را با هم پیش ببریم."
        )

        result = {
            'messages': messages,
            'encouragement': encouragement,
            'source': 'fallback'
        }

        if law_overview:
            result['law_overview'] = law_overview

        return result

