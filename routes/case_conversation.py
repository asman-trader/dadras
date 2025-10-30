"""
سیستم گفتگوی هوشمند برای جمع‌آوری اطلاعات پرونده
این ماژول مانند یک وکیل واقعی با موکل گفتگو می‌کند و اطلاعات را جمع‌آوری می‌کند
"""

import re
import json
import os
from typing import Dict, List, Optional, Tuple
from datetime import datetime


class CaseConversationManager:
    """مدیریت گفتگوی هوشمند برای جمع‌آوری اطلاعات پرونده"""
    
    def __init__(self):
        self.assistant_name = "دادرس هوشمند"
        self.assistant_title = "شبیه‌ساز وکیل پایه یک دادگستری"
        
        # پاسخ‌های تأیید و تشویق برای ایجاد تجربه چت طبیعی
        self.acknowledgments = [
            "عالی، متشکرم از اطلاعاتتان.",
            "بسیار خوب، ثبت شد.",
            "دریافت کردم، ممنونم.",
            "خیلی خوب، متوجه شدم.",
            "کاملاً واضح است، متشکرم.",
            "بله، درک کردم.",
        ]
        
        # پاسخ‌های انتقالی برای حالت چت
        self.transitions = [
            "حالا بگذارید به موضوع بعدی برویم.",
            "خیلی خوب، سوال بعدی:",
            "عالی. حالا می‌خواهم بدانم:",
            "متشکرم. اجازه دهید درباره موضوع دیگری بپرسم:",
            "دریافت شد. سوال بعدی:",
        ]

        # توضیحات راهنما برای استخراج اطلاعات با AI
        self.field_guidance = {
            'client_name': 'نام و نام خانوادگی کامل موکل (دو یا چند کلمه).',
            'client_phone': 'شماره تماس یا موبایل 11 رقمی. اگر ذکر نشد خالی بماند.',
            'opponent_name': 'نام و مشخصات طرف مقابل اختلاف یا دعوا.',
            'complaint_side': 'نقش موکل در پرونده: شاکی/خواهان یا خوانده/متهم.',
            'case_stage': 'مرحله فعلی پرونده مانند قبل از طرح شکایت، در دادگاه، پس از صدور رأی یا تجدیدنظر.',
            'case_number': 'شماره پرونده یا ذکر «ندارد» در صورت نبود.',
            'court_branch': 'نام شعبه یا محل دادگاه در حال رسیدگی.',
            'incident_date': 'تاریخ یا بازه زمانی وقوع رویداد اصلی پرونده.',
            'incident_description': 'شرح خلاصه‌ی اتفاقات مربوط به پرونده.',
            'available_documents': 'مدارک یا مستندات موجود نزد موکل.',
            'actions_taken': 'اقدامات انجام شده تا کنون مانند طرح شکایت، حضور در دادگاه.',
            'case_goal': 'هدف یا نتیجه مورد انتظار موکل از پیگیری پرونده.',
            'deadlines': 'هرگونه مهلت یا ضرب‌الاجل مرتبط با پرونده.'
        }
        
        # تعریف سوالات بر اساس مراحل
        self.questions_flow = [
            {
                'id': 'greeting',
                'question': '⚖️ **سلام و درود!**\n\nمن **{assistant_name}** هستم، {assistant_title}.\n\nخوشحالم که در خدمت شما هستم تا پروندهٔ «**{case_title}**» را با هم بررسی کنیم. من اینجا هستم تا مثل یک وکیل واقعی، شما را در تمام مراحل راهنمایی کنم. 💼\n\n**برای شروع، لطفاً نام و نام خانوادگی خود را به من بگویید.** 👤',
                'extract': ['client_name'],
                'required': True,
                'next_question': 'contact',
                'chat_response': '✅ خوشبختم که با شما آشنا شدم، {client_name} جان!'
            },
            {
                'id': 'contact',
                'question': '**برای ارتباط بهتر و پیگیری پرونده، لطفاً شماره تماس خود را در اختیارم قرار دهید.** 📱\n\n(مثلاً: 09121234567)',
                'extract': ['client_phone'],
                'required': True,
                'next_question': 'opponent',
                'chat_response': '✅ شماره تماستان ثبت شد.'
            },
            {
                'id': 'opponent',
                'question': '**حالا بفرمایید طرف مقابل شما کیست؟**\n\nیعنی:\n• اگر شکایت کرده‌اید → **خوانده** کیست؟\n• اگر از شما شکایت شده → **شاکی** کیست؟\n\nنام و مشخصات ایشان را بنویسید. 👥',
                'extract': ['opponent_name'],
                'required': True,
                'next_question': 'complaint_side',
                'chat_response': '✅ نام طرف مقابل ثبت شد.'
            },
            {
                'id': 'complaint_side',
                'question': '**خیلی خوب. حالا بگویید در این پرونده، شما چه نقشی دارید؟**\n\n🔹 **شما شاکی/خواهان هستید؟** (شکایت کرده‌اید)\n🔹 **یا شما خوانده/متهم هستید؟** (از شما شکایت شده)\n\nلطفاً یکی را انتخاب کنید یا توضیح دهید.',
                'extract': ['complaint_side'],
                'required': True,
                'next_question': 'case_stage',
                'chat_response': '✅ فهمیدم، موقعیت شما روشن شد.'
            },
            {
                'id': 'case_stage',
                'question': '**اکنون بگویید پرونده شما در چه مرحله‌ای است؟** 📊\n\n🔹 **قبل از طرح شکایت** (هنوز اقدام نکرده‌اید)\n🔹 **در دادگاه** (در حال رسیدگی)\n🔹 **پس از صدور رأی** (حکم صادر شده)\n🔹 **مرحله تجدیدنظر یا فرجام** (اعتراض به رأی)\n\nکدام گزینه را انتخاب می‌کنید؟',
                'extract': ['case_stage'],
                'required': True,
                'next_question': 'case_number',
                'chat_response': '✅ مرحله پرونده ثبت شد.'
            },
            {
                'id': 'case_number',
                'question': '**آیا شماره پرونده دارید؟** 📋\n\nاگر دارید لطفاً بنویسید، در غیر این صورت بگویید «**ندارم**» یا «**هنوز**».',
                'extract': ['case_number'],
                'required': False,
                'next_question': 'court_branch',
                'chat_response': '✅ متوجه شدم.'
            },
            {
                'id': 'court_branch',
                'question': '**آیا پرونده در شعبه خاصی از دادگاه در حال رسیدگی است؟** ⚖️\n\nاگر بله، لطفاً شعبه و محل دادگاه را بنویسید.\n(مثلاً: شعبه 5 دادگاه عمومی تهران)\n\nاگر خیر، بگویید «**ندارم**».',
                'extract': ['court_branch'],
                'required': False,
                'next_question': 'incident_date',
                'chat_response': '✅ اطلاعات دادگاه ثبت شد.'
            },
            {
                'id': 'incident_date',
                'question': '**حالا بگویید این ماجرا کی اتفاق افتاد؟** 📅\n\nتاریخ وقوع موضوع پرونده را بنویسید.\n(مثلاً: 1403/05/10 یا دو ماه پیش)',
                'extract': ['incident_date'],
                'required': True,
                'next_question': 'incident_description',
                'chat_response': '✅ تاریخ وقوع ثبت شد.'
            },
            {
                'id': 'incident_description',
                'question': '**خیلی خوب، حالا مهم‌ترین قسمت!** 📝\n\n**لطفاً با جزئیات کامل برایم توضیح دهید که چه اتفاقی افتاده؟**\n\nماجرا را از ابتدا تا الان شرح دهید. نگران نباشید، وقت دارید.\n\n💡 **نکته:** هر چه دقیق‌تر توضیح دهید، بهتر می‌توانم راهنماییتان کنم.\n\n👉 **چه اتفاقی افتاد؟**',
                'extract': ['incident_description'],
                'required': True,
                'next_question': 'available_documents',
                'chat_response': '✅ متن شما را دقیقاً خواندم و ثبت کردم.'
            },
            {
                'id': 'available_documents',
                'question': '**عالی! حالا بگویید چه مدارک و مستنداتی در اختیار دارید؟** 📄\n\nمثلاً:\n✓ **قرارداد** کتبی یا توافقنامه\n✓ **چک یا سفته** \n✓ **رسید و فاکتور**\n✓ **تصاویر یا ویدیو**\n✓ **پیامک، ایمیل یا مکاتبات**\n✓ **شهود**\n\n👉 **همه چیزهایی که دارید را بنویسید:**',
                'extract': ['available_documents'],
                'required': True,
                'next_question': 'actions_taken',
                'chat_response': '✅ مدارک شما ثبت شد. این مستندات خیلی مهم هستند!'
            },
            {
                'id': 'actions_taken',
                'question': '**تا الان چه کارهایی برای این پرونده انجام داده‌اید؟** 🔄\n\nمثلاً:\n• شکایت کردید؟\n• به جلسه دادگاه رفتید؟\n• کارشناس معرفی شده؟\n• قرار تامین گرفتید؟\n• با وکیل مشورت کردید؟\n\nاگر هیچ اقدامی نکرده‌اید، بگویید «**هیچ اقدامی**».',
                'extract': ['actions_taken'],
                'required': False,
                'next_question': 'case_goal',
                'chat_response': '✅ اقدامات شما ثبت شد.'
            },
            {
                'id': 'case_goal',
                'question': '**هدف شما از پیگیری این پرونده چیست؟** 🎯\n\n**می‌خواهید به چه نتیجه‌ای برسید؟**\n\nمثلاً:\n• دریافت خسارت\n• وصول طلب\n• برائت از اتهام\n• طلاق\n• تخلیه ملک\n\n👉 **هدفتان را بنویسید:**',
                'extract': ['case_goal'],
                'required': True,
                'next_question': 'deadlines',
                'chat_response': '✅ هدف شما واضح است. این خیلی کمک می‌کند!'
            },
            {
                'id': 'deadlines',
                'question': '**آخرین سوال:** 🕐\n\n**آیا ضرب‌الاجل یا مهلت خاصی دارید؟**\n\nمثلاً:\n• مهلت تجدیدنظر (معمولاً 20 روز)\n• مهلت ارسال لایحه\n• تاریخ جلسه بعدی دادگاه\n\nاگر ندارید، بگویید «**ندارم**».\n\n👉 **مهلت دارید؟**',
                'extract': ['deadlines'],
                'required': False,
                'next_question': None,
                'chat_response': '✅ ضرب‌الاجل‌ها ثبت شد.'
            }
        ]
        
    def get_chat_acknowledgment(self, question_data: Dict, case_info: Dict) -> str:
        """
        تولید پاسخ تأیید به صورت چت برای هر سوال
        """
        import random
        
        # اگر سوال chat_response دارد، از آن استفاده کن
        if 'chat_response' in question_data:
            response = question_data['chat_response']
            # جایگزینی متغیرها
            response = response.format(
                client_name=case_info.get('client_name', 'شما'),
                assistant_name=self.assistant_name
            )
            return response
        
        # در غیر این صورت از پاسخ‌های عمومی استفاده کن
        return random.choice(self.acknowledgments)
    
    def extract_info_from_answer(self, answer: str, current_field: List[str], case_info: Dict) -> Dict:
        """
        استخراج اطلاعات از پاسخ کاربر
        
        Args:
            answer: پاسخ کاربر
            current_field: فیلدهایی که باید استخراج شوند
            case_info: اطلاعات فعلی پرونده
            
        Returns:
            اطلاعات به‌روزرسانی شده
        """
        answer_lower = answer.lower()
        
        # استخراج نام
        if 'client_name' in current_field and not case_info.get('client_name'):
            # الگوهای مختلف برای نام
            patterns = [
                r'(?:نام من|اسم من|من)\s+([^\n.،]+(?:\s+[^\n.،]+)+)',
                r'^([^\n.،]+(?:\s+[^\n.،]+)+)$'
            ]
            for pattern in patterns:
                match = re.search(pattern, answer.strip())
                if match:
                    name = match.group(1).strip()
                    # بررسی که نام معتبر باشد (حداقل دو کلمه)
                    if len(name.split()) >= 2:
                        case_info['client_name'] = name
                        break
        
        # استخراج شماره تماس
        if 'client_phone' in current_field and not case_info.get('client_phone'):
            phone_match = re.search(r'09\d{9}|۰۹[\u06F0-\u06F9]{9}', answer)
            if phone_match:
                case_info['client_phone'] = phone_match.group(0)
        
        # تشخیص طرف شکایت
        if 'complaint_side' in current_field and not case_info.get('complaint_side'):
            if any(word in answer_lower for word in ['من شکایت کردم', 'من شاکی', 'من خواهان', 'شکایت کردم']):
                case_info['complaint_side'] = 'شاکی/خواهان'
            elif any(word in answer_lower for word in ['علیه من', 'من خوانده', 'من متهم', 'از من شکایت']):
                case_info['complaint_side'] = 'خوانده/متهم'
        
        # تشخیص مرحله پرونده
        if 'case_stage' in current_field and not case_info.get('case_stage'):
            if any(word in answer_lower for word in ['هنوز شکایت نکردم', 'قبل از شکایت', 'نکردم']):
                case_info['case_stage'] = 'قبل از طرح شکایت'
            elif any(word in answer_lower for word in ['دادگاه', 'جلسه', 'رسیدگی']):
                case_info['case_stage'] = 'در دادگاه'
            elif any(word in answer_lower for word in ['رأی', 'حکم', 'صادر شد']):
                case_info['case_stage'] = 'پس از صدور رأی'
            elif any(word in answer_lower for word in ['تجدیدنظر', 'فرجام']):
                case_info['case_stage'] = 'مرحله تجدیدنظر'
        
        # استخراج شماره پرونده
        if 'case_number' in current_field and not case_info.get('case_number'):
            case_num_match = re.search(r'(?:شماره\s+پرونده|پرونده\s+شماره)[:\s]*(\d+[-/]\d+[-/]\d+)', answer)
            if case_num_match:
                case_info['case_number'] = case_num_match.group(1)
            elif re.search(r'\d+[-/]\d+[-/]\d+', answer):
                match = re.search(r'\d+[-/]\d+[-/]\d+', answer)
                case_info['case_number'] = match.group(0)
            elif 'ندارم' in answer_lower or 'نداریم' in answer_lower or 'هنوز' in answer_lower:
                case_info['case_number'] = 'ندارد'
        
        # اطلاعات دیگر را مستقیم ذخیره کن
        for field in current_field:
            if field not in ['client_name', 'client_phone', 'complaint_side', 'case_stage', 'case_number']:
                if not case_info.get(field):
                    case_info[field] = answer.strip()

        # در صورت در دسترس بودن AI، تلاش برای استخراج دقیق‌تر
        try:
            ai_result = self._extract_info_with_ai(answer, current_field, case_info)
            if ai_result:
                for key, value in ai_result.items():
                    if value:
                        case_info[key] = value.strip()
                    elif not case_info.get(key):
                        case_info[key] = value
        except Exception:
            # عدم استفاده از AI نباید مانع ادامه روند شود
            pass
        
        return case_info

    def _extract_info_with_ai(self, answer: str, current_field: List[str], case_info: Dict) -> Dict:
        """استفاده از هوش مصنوعی برای استخراج دقیق اطلاعات پاسخ"""
        target_fields = list(dict.fromkeys(current_field or []))
        if not target_fields:
            return {}
        if not answer or not answer.strip():
            return {}
        api_key = os.getenv('DEEPSEEK_API_KEY', '').strip()
        if not api_key:
            return {}

        import requests

        # آماده‌سازی توضیحات برای فیلدهای مورد نیاز
        field_instructions = []
        for field in target_fields:
            desc = self.field_guidance.get(field, '')
            if desc:
                field_instructions.append(f"- {field}: {desc}")
            else:
                field_instructions.append(f"- {field}: مقدار مرتبط با این کلید را استخراج کن.")

        guidance_text = "\n".join(field_instructions)
        known_context = []
        for key, value in case_info.items():
            if value and key not in target_fields:
                known_context.append(f"{key}: {value}")
        context_text = "\n".join(known_context) if known_context else "(اطلاعات قبلی موجود نیست)"

        existing_values = []
        for key in target_fields:
            if case_info.get(key):
                existing_values.append(f"{key}: {case_info[key]}")
        existing_text = "\n".join(existing_values) if existing_values else "(مقداری ثبت نشده)"

        prompt = f"""شما یک دستیار حقوقی هوشمند هستید. پاسخ کاربر را تحلیل کن و مقادیر مورد نیاز را به صورت JSON بازگردان.

پاسخ کاربر:
"""

        prompt += answer.strip() + "\n\n"
        prompt += "فیلدهایی که باید استخراج شوند:\n" + guidance_text + "\n\n"
        prompt += "اطلاعاتی که قبلاً داریم (فقط برای زمینه):\n" + context_text + "\n\n"
        prompt += "مقادیر فعلی که ثبت شده‌اند (در صورت نیاز اصلاح کن):\n" + existing_text + "\n\n"
        prompt += "فقط یک JSON فارسی با کلیدهای مشخص شده برگردان. مقادیر باید تمیز و بدون عبارت‌های اضافی مثل «هستم»، «می‌باشد»، «احتمالاً» باشند. اگر مقداری وجود ندارد رشته خالی قرار بده. مثال:\n{\"client_name\": \"مثال\", \"case_stage\": \"\"}"

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
                    {'role': 'system', 'content': 'You are an expert Persian legal assistant. Return only valid JSON strings.'},
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.2,
                'max_tokens': 400
            },
            timeout=12
        )

        if response.status_code != 200:
            return {}

        data = response.json()
        raw_content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
        if not raw_content:
            return {}

        cleaned = raw_content.strip()
        if cleaned.startswith('```'):
            cleaned = re.sub(r'^```(?:json)?', '', cleaned, flags=re.IGNORECASE).strip()
            cleaned = re.sub(r'```$', '', cleaned).strip()

        json_match = re.search(r'\{[\s\S]*\}', cleaned)
        if json_match:
            cleaned = json_match.group(0)

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            return {}

        if not isinstance(parsed, dict):
            return {}

        result = {}
        for key in target_fields:
            value = parsed.get(key)
            if value is None:
                continue
            if isinstance(value, str):
                result[key] = value
            else:
                result[key] = str(value)
        return result
    
    def get_next_question(
        self, 
        case_info: Dict, 
        conversation_history: List[Dict],
        case_title: str,
        lawyer_name: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[str], bool, Optional[str]]:
        """
        سوال بعدی را بر اساس اطلاعات جمع‌آوری شده بازگردان (به صورت چت)
        
        Returns:
            (question_text, question_id, is_complete, chat_acknowledgment)
        """
        import random
        
        # پیدا کردن آخرین سوال پرسیده شده
        last_question_id = None
        for item in reversed(conversation_history):
            if item.get('role') == 'assistant' and item.get('question_id'):
                last_question_id = item['question_id']
                break
        
        # اگر سوالی پرسیده نشده، از ابتدا شروع کن
        if not last_question_id:
            question_data = self.questions_flow[0]
            question_text = question_data['question'].format(
                assistant_name=self.assistant_name,
                assistant_title=self.assistant_title,
                case_title=case_title,
                client_name=case_info.get('client_name', '')
            )
            return question_text, question_data['id'], False, None
        
        # پیدا کردن سوال فعلی و بررسی اینکه آیا پاسخ داده شده
        current_question = None
        current_index = -1
        for i, q in enumerate(self.questions_flow):
            if q['id'] == last_question_id:
                current_question = q
                current_index = i
                break
        
        if current_question is None:
            return None, None, True, None
        
        # بررسی اینکه آیا فیلدهای مورد نیاز پر شده‌اند
        all_filled = all(case_info.get(field) for field in current_question['extract'])
        
        # تولید پاسخ تأیید برای چت
        chat_ack = None
        if all_filled:
            chat_ack = self.get_chat_acknowledgment(current_question, case_info)
        
        # اگر سوال فعلی پاسخ داده نشده و اجباری است، دوباره بپرس
        if current_question['required'] and not all_filled:
            retry_text = f"❓ **متوجه نشدم یا اطلاعات کامل نیست.**\n\n{current_question['question']}"
            retry_text = retry_text.format(
                assistant_name=self.assistant_name,
                assistant_title=self.assistant_title,
                case_title=case_title,
                client_name=case_info.get('client_name', 'شما')
            )
            return retry_text, current_question['id'], False, None
        
        # رفتن به سوال بعدی
        next_question_id = current_question.get('next_question')
        
        if not next_question_id:
            # گفتگو تمام شده
            return None, None, True, chat_ack
        
        # پیدا کردن سوال بعدی
        next_question_data = None
        for q in self.questions_flow:
            if q['id'] == next_question_id:
                next_question_data = q
                break
        
        if not next_question_data:
            return None, None, True, chat_ack
        
        # ساخت پیام چت با انتقال نرم
        transition = random.choice(self.transitions)
        question_text = next_question_data['question'].format(
            assistant_name=self.assistant_name,
            assistant_title=self.assistant_title,
            case_title=case_title,
            client_name=case_info.get('client_name', 'شما')
        )
        
        # ترکیب تأیید + انتقال + سوال برای حس چت طبیعی
        full_message = question_text
        if chat_ack:
            full_message = f"{chat_ack}\n\n{transition}\n\n{question_text}"
        
        return full_message, next_question_data['id'], False, None
    
    def finalize_case_info(self, case_info: Dict, case_type: str) -> Dict:
        """
        نهایی‌سازی و خلاصه‌سازی اطلاعات پرونده
        
        Returns:
            خلاصه کامل اطلاعات
        """
        type_labels = {
            'civil': '👨‍⚖️ مدنی',
            'criminal': '🔒 کیفری',
            'family': '👨‍👩‍👧‍👦 خانواده',
            'commercial': '💼 تجاری',
            'labor': '👷 کار',
            'property': '🏠 املاک',
            'other': '📋 سایر'
        }
        
        summary = {
            'complete': True,
            'case_title': case_info.get('case_title', ''),
            'case_type': type_labels.get(case_type, case_type),
            'client_name': case_info.get('client_name', '(ذکر نشده)'),
            'client_phone': case_info.get('client_phone', '(ذکر نشده)'),
            'opponent_name': case_info.get('opponent_name', '(ذکر نشده)'),
            'complaint_side': case_info.get('complaint_side', '(مشخص نشد)'),
            'case_stage': case_info.get('case_stage', '(مشخص نشد)'),
            'case_number': case_info.get('case_number', '(ندارد)'),
            'court_branch': case_info.get('court_branch', '(ندارد)'),
            'incident_date': case_info.get('incident_date', '(ذکر نشده)'),
            'incident_description': case_info.get('incident_description', '(توضیح داده نشده)'),
            'available_documents': case_info.get('available_documents', '(اعلام نشده)'),
            'actions_taken': case_info.get('actions_taken', '(اقدام خاصی انجام نشده)'),
            'case_goal': case_info.get('case_goal', '(مشخص نشده)'),
            'deadlines': case_info.get('deadlines', '(ندارد)'),
            'created_at': case_info.get('created_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        }
        
        return summary
    
    def generate_summary_text(self, summary: Dict) -> str:
        """
        تولید متن خلاصه برای نمایش
        """
        text = f"""🎉 **بررسی اولیه پرونده کامل شد!**

من **{self.assistant_name}** ({self.assistant_title}) اطلاعات کامل پرونده شما را دریافت و ثبت کردم:

━━━━━━━━━━━━━━━━━━━━━━━
**📁 مشخصات پرونده:**
• عنوان: {summary['case_title']}
• نوع: {summary['case_type']}
• تاریخ ایجاد: {summary['created_at']}

**👤 موکل:**
• نام: {summary['client_name']}
• تماس: {summary['client_phone']}

**👥 طرف مقابل:**
{summary['opponent_name']}

**⚖️ وضعیت پرونده:**
• موقعیت: {summary['complaint_side']}
• مرحله: {summary['case_stage']}
• شماره پرونده: {summary['case_number']}
• شعبه: {summary['court_branch']}

**📅 تاریخ وقوع:**
{summary['incident_date']}

**📄 مدارک موجود:**
{summary['available_documents']}

**📋 اقدامات انجام شده:**
{summary['actions_taken']}

**🎯 هدف از پیگیری:**
{summary['case_goal']}

**⏰ ضرب‌الاجل‌ها:**
{summary['deadlines']}

**📝 خلاصه موضوع:**
{summary['incident_description'][:500]}{'...' if len(summary['incident_description']) > 500 else ''}

━━━━━━━━━━━━━━━━━━━━━━━

✅ **وضعیت:** پرونده آماده برای تحلیل و مشاوره حقوقی است

💼 **من به عنوان {self.assistant_name}، اکنون می‌توانم:**

🔍 **تحلیل و بررسی:**
• تحلیل حقوقی کامل پرونده
• شناسایی نقاط قوت و ضعف
• ارزیابی شانس موفقیت

⚖️ **راهنمایی حقوقی:**
• معرفی قوانین و مواد مرتبط
• توضیح مراحل قانونی بعدی
• پیشنهاد استراتژی مناسب

📝 **خدمات تخصصی:**
• تهیه پیش‌نویس لوایح و دادخواست
• راهنمایی برای جمع‌آوری مدارک
• پاسخ به سوالات حقوقی شما

━━━━━━━━━━━━━━━━━━━━━━━

💬 **حالا چه کاری برایتان انجام دهم؟**

شما می‌توانید:
✓ از من تحلیل کامل پرونده بخواهید
✓ سوالات حقوقی خود را بپرسید
✓ راهنمایی برای اقدامات بعدی دریافت کنید

👉 **منتظر سوال شما هستم!** 😊"""
        
        return text
    
    def detect_case_type_with_ai(self, case_info: Dict) -> str:
        """
        تشخیص خودکار نوع پرونده با استفاده از هوش مصنوعی
        """
        try:
            # بررسی وجود API key
            api_key = os.getenv('DEEPSEEK_API_KEY', '').strip()
            if not api_key:
                return self._fallback_case_type_detection(case_info)
            
            # آماده‌سازی اطلاعات برای AI
            incident_desc = case_info.get('incident_description', '')
            case_title = case_info.get('case_title', '')
            opponent = case_info.get('opponent_name', '')
            actions = case_info.get('actions_taken', '')
            
            prompt = f"""بر اساس اطلاعات زیر، نوع این پرونده حقوقی را مشخص کن و فقط یک کلمه انگلیسی برگردون:

عنوان پرونده: {case_title}
طرف مقابل: {opponent}
شرح ماجرا: {incident_desc[:500]}
اقدامات: {actions}

انواع پرونده:
- civil: پرونده‌های مدنی (قرارداد، وام، وصول طلب، خسارت مالی)
- criminal: پرونده‌های کیفری (سرقت، کلاهبرداری، ضرب و جرح، توهین)
- family: پرونده‌های خانوادگی (طلاق، نفقه، حضانت، ارث)
- commercial: پرونده‌های تجاری (شرکت، تجارت، ورشکستگی، چک)
- labor: پرونده‌های کار (اخراج، حقوق کارگری، بیمه)
- property: پرونده‌های املاک (تخلیه، مالکیت، سند)
- other: سایر پرونده‌ها

فقط یکی از کلمات بالا را بنویس، بدون توضیح اضافی:"""
            
            import requests
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
                    'temperature': 0.3,
                    'max_tokens': 50
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                ai_response = data.get('choices', [{}])[0].get('message', {}).get('content', '').strip().lower()
                
                # استخراج نوع پرونده
                valid_types = ['civil', 'criminal', 'family', 'commercial', 'labor', 'property', 'other']
                for case_type in valid_types:
                    if case_type in ai_response:
                        return case_type
            
            return self._fallback_case_type_detection(case_info)
        
        except Exception as e:
            print(f"Error in AI case type detection: {e}")
            return self._fallback_case_type_detection(case_info)
    
    def _fallback_case_type_detection(self, case_info: Dict) -> str:
        """
        تشخیص نوع پرونده با روش کلاسیک (بدون AI)
        """
        text = f"{case_info.get('case_title', '')} {case_info.get('incident_description', '')}".lower()
        
        # کلمات کلیدی برای هر نوع
        if any(word in text for word in ['طلاق', 'نفقه', 'حضانت', 'مهریه', 'ازدواج', 'فرزند']):
            return 'family'
        elif any(word in text for word in ['سرقت', 'کلاهبرداری', 'ضرب', 'جرح', 'توهین', 'تهدید', 'اختلاس']):
            return 'criminal'
        elif any(word in text for word in ['شرکت', 'تجارت', 'ورشکستگی', 'چک', 'سفته', 'بانک']):
            return 'commercial'
        elif any(word in text for word in ['اخراج', 'حقوق', 'بیمه', 'کارگر', 'کارفرما', 'استخدام']):
            return 'labor'
        elif any(word in text for word in ['ملک', 'خانه', 'زمین', 'تخلیه', 'اجاره', 'سند']):
            return 'property'
        elif any(word in text for word in ['قرارداد', 'وام', 'طلب', 'دین', 'خسارت']):
            return 'civil'
        else:
            return 'other'
    
    def generate_ai_summary(self, case_info: Dict) -> str:
        """
        تولید خلاصه حرفه‌ای با استفاده از هوش مصنوعی
        """
        try:
            api_key = os.getenv('DEEPSEEK_API_KEY', '').strip()
            if not api_key:
                return None  # استفاده از خلاصه معمولی
            
            # آماده‌سازی اطلاعات
            prompt = f"""تو "دادرس هوشمند" هستی، یک شبیه‌ساز وکیل پایه یک دادگستری. یک خلاصه حرفه‌ای و صمیمی از این پرونده تهیه کن:

📁 **اطلاعات پرونده:**
• عنوان: {case_info.get('case_title', 'نامشخص')}
• نوع: {self._get_case_type_label(case_info.get('case_type', 'other'))}
• موکل: {case_info.get('client_name', 'نامشخص')}
• طرف مقابل: {case_info.get('opponent_name', 'نامشخص')}
• موقعیت: {case_info.get('complaint_side', 'نامشخص')}
• مرحله: {case_info.get('case_stage', 'نامشخص')}

📝 **شرح ماجرا:**
{case_info.get('incident_description', 'توضیح داده نشده')}

📄 **مدارک:**
{case_info.get('available_documents', 'ذکر نشده')}

📋 **اقدامات:**
{case_info.get('actions_taken', 'انجام نشده')}

🎯 **هدف:**
{case_info.get('case_goal', 'مشخص نشده')}

لطفاً یک خلاصه جذاب و کاربردی تهیه کن که شامل:
1. **خلاصه وضعیت** (2-3 جمله)
2. **نکات کلیدی و مهم** (3-4 مورد با ایموجی)
3. **ارزیابی اولیه** (شانس موفقیت + دلیل)
4. **پیشنهادات فوری** (3-4 مورد عملی)

خلاصه را فارسی، با لحن صمیمی ولی حرفه‌ای، و با ایموجی‌های مناسب بنویس.
مثل یک چت دوستانه با موکل صحبت کن."""

            import requests
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
                    'max_tokens': 1000
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                ai_summary = data.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
                
                if ai_summary and len(ai_summary) > 100:
                    return f"""🎉 **بررسی اولیه کامل شد!**

من **دادرس هوشمند** (شبیه‌ساز وکیل پایه یک دادگستری) پرونده شما را بررسی کردم:

{ai_summary}

━━━━━━━━━━━━━━━━━━━━━━━

💬 **حالا چه کار می‌توانم برایتان انجام دهم؟**

✓ تحلیل حقوقی کامل و دقیق
✓ معرفی قوانین و مواد مرتبط
✓ تهیه پیش‌نویس لوایح و دادخواست
✓ پاسخ به سوالات حقوقی شما

👉 **منتظر سوال شما هستم!** 💼"""
            
            return None  # در صورت خطا، خلاصه معمولی استفاده شود
            
        except Exception as e:
            print(f"Error in AI summary generation: {e}")
            return None
    
    def get_smart_questions(self, case_info: Dict) -> List[str]:
        """
        تولید سوالات تکمیلی هوشمند بر اساس اطلاعات موجود
        """
        try:
            api_key = os.getenv('DEEPSEEK_API_KEY', '').strip()
            if not api_key:
                return self._get_default_smart_questions(case_info)
            
            prompt = f"""بر اساس اطلاعات پرونده زیر، ۵ سوال مهم و کاربردی که باید از موکل پرسیده شود را پیشنهاد بده:

عنوان پرونده: {case_info.get('case_title', '')}
نوع: {case_info.get('case_type', '')}
شرح: {case_info.get('incident_description', '')[:300]}
مرحله: {case_info.get('case_stage', '')}

سوالات باید:
- مرتبط با نوع و مرحله پرونده باشند
- برای تکمیل اطلاعات کمک کنند
- واضح و مستقیم باشند
- فارسی باشند

فقط ۵ سوال را به صورت لیست برگردان، بدون شماره و بدون توضیح اضافی:"""

            import requests
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
                    'max_tokens': 300
                },
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
                
                # استخراج سوالات
                questions = []
                for line in content.split('\n'):
                    line = line.strip()
                    # حذف شماره‌ها و نقطه‌ها از ابتدای سوال
                    line = re.sub(r'^[\d\-\.•\*]+\s*', '', line)
                    if line and len(line) > 10:
                        questions.append(line)
                
                if len(questions) >= 3:
                    return questions[:5]
            
            return self._get_default_smart_questions(case_info)
            
        except Exception as e:
            print(f"Error generating smart questions: {e}")
            return self._get_default_smart_questions(case_info)
    
    def _get_default_smart_questions(self, case_info: Dict) -> List[str]:
        """سوالات پیش‌فرض بر اساس نوع پرونده"""
        case_type = case_info.get('case_type', 'other')
        stage = case_info.get('case_stage', '')
        
        questions = [
            'آیا شاهد یا مدارک دیگری دارید که هنوز ذکر نکرده‌اید؟',
            'آیا قبلاً با وکیل یا مشاور حقوقی مشورت کرده‌اید؟',
            'آیا محدودیت مالی برای پیگیری پرونده دارید؟',
        ]
        
        if case_type == 'criminal':
            questions.extend([
                'آیا گزارش پلیسی یا کلانتری دارید؟',
                'آیا خسارت مادی یا جسمی به شما وارد شده است؟'
            ])
        elif case_type == 'family':
            questions.extend([
                'آیا فرزند دارید و نگران حضانت هستید؟',
                'آیا توافق‌های قبلی با همسرتان داشته‌اید؟'
            ])
        elif case_type == 'civil' or case_type == 'commercial':
            questions.extend([
                'آیا قرارداد یا توافقنامه کتبی دارید؟',
                'چه مبلغی طلبکار یا بدهکار هستید؟'
            ])
        
        return questions[:5]
    
    def _get_case_type_label(self, case_type: str) -> str:
        """برچسب فارسی نوع پرونده"""
        labels = {
            'civil': '👨‍⚖️ مدنی',
            'criminal': '🔒 کیفری',
            'family': '👨‍👩‍👧‍👦 خانواده',
            'commercial': '💼 تجاری',
            'labor': '👷 کار',
            'property': '🏠 املاک',
            'other': '📋 سایر'
        }
        return labels.get(case_type, '📋 سایر')

