# 🔍 راهنمای Debug پنل اطلاعات پرونده

## مشکل: پنل نمایش داده نمی‌شود

### ✅ چک‌لیست اولیه

#### 1. اندازه صفحه
پنل **فقط در صفحات بزرگ‌تر از 1400px** نمایش داده می‌شود.

**بررسی:**
- کنسول مرورگر را باز کنید (F12)
- در Console تایپ کنید: `window.innerWidth`
- اگر عدد کمتر از 1400 است، پنل نمایش داده نمی‌شود

**راه حل:** نمایشگر را بزرگ‌تر کنید یا zoom را کاهش دهید (Ctrl + -)

---

#### 2. تست دستی پنل

در کنسول مرورگر این دستور را اجرا کنید:

```javascript
testCaseInfoPanel()
```

این تابع:
- یک پرونده تست ایجاد می‌کند
- پنل را نمایش می‌دهد
- اطلاعات debug را چاپ می‌کند

---

#### 3. بررسی Element در DOM

```javascript
const panel = document.getElementById('caseInfoPanel');
console.log('Panel exists:', !!panel);
if(panel) {
  console.log('Display:', window.getComputedStyle(panel).display);
  console.log('Visibility:', window.getComputedStyle(panel).visibility);
}
```

---

#### 4. بررسی localStorage

```javascript
// نمایش تمام پرونده‌ها
for(let i = 0; i < localStorage.length; i++){
  const key = localStorage.key(i);
  if(key.startsWith('case_info_')){
    console.log(key, JSON.parse(localStorage.getItem(key)));
  }
}

// نمایش پرونده فعلی
const currentCaseId = localStorage.getItem('currentChatId');
if(currentCaseId){
  const caseInfo = JSON.parse(localStorage.getItem(`case_info_${currentCaseId}`));
  console.log('Current case info:', caseInfo);
}
```

---

### 🔧 راه‌حل‌های رایج

#### مشکل 1: صفحه کوچک است
**علامت:** `Screen width < 1400`

**راه حل:**
- نمایشگر را بزرگ‌تر کنید
- Zoom را کاهش دهید (Ctrl + -)
- از نمایشگر بزرگ‌تر استفاده کنید

---

#### مشکل 2: پرونده باز نیست
**علامت:** `localStorage` خالی است یا `case_info_` وجود ندارد

**راه حل:**
1. یک پرونده جدید ایجاد کنید
2. گفتگوی اولیه را کامل کنید
3. پنل باید نمایش داده شود

---

#### مشکل 3: Element در DOM نیست
**علامت:** `document.getElementById('caseInfoPanel')` برمی‌گرداند `null`

**راه حل:**
- صفحه را refresh کنید (F5)
- Cache مرورگر را پاک کنید (Ctrl + Shift + Delete)
- سرور را restart کنید

---

### 🔥 تست سریع

**دستور یک خطی برای تست کامل:**

```javascript
// تست و نمایش اجباری
testCaseInfoPanel(); 
setTimeout(() => {
  const panel = document.getElementById('caseInfoPanel');
  if(panel && window.getComputedStyle(panel).display === 'none'){
    panel.style.display = 'block';
    console.log('✅ پنل به صورت اجباری نمایش داده شد');
  }
}, 100);
```

---

### 📞 گزارش مشکل

اگر هنوز مشکل دارید، این اطلاعات را جمع‌آوری کنید:

```javascript
// کپی کردن این اطلاعات
const debugInfo = {
  screenWidth: window.innerWidth,
  screenHeight: window.innerHeight,
  panelExists: !!document.getElementById('caseInfoPanel'),
  panelDisplay: document.getElementById('caseInfoPanel') ? 
                window.getComputedStyle(document.getElementById('caseInfoPanel')).display : 'N/A',
  currentChatId: localStorage.getItem('currentChatId'),
  hasCaseInfo: !!localStorage.getItem(`case_info_${localStorage.getItem('currentChatId')}`),
  bodyClasses: Array.from(document.body.classList)
};

console.log('📋 Debug Info:', JSON.stringify(debugInfo, null, 2));
```

---

## ✅ راه‌حل نهایی (اگر همه چیز شکست خورد)

```javascript
// نمایش اجباری با override تمام CSS
const panel = document.getElementById('caseInfoPanel');
if(panel){
  // Override CSS
  panel.style.setProperty('display', 'block', 'important');
  panel.style.setProperty('visibility', 'visible', 'important');
  panel.style.setProperty('position', 'fixed', 'important');
  panel.style.setProperty('right', '16px', 'important');
  panel.style.setProperty('top', '80px', 'important');
  panel.style.setProperty('z-index', '1000', 'important');
  
  // اضافه کلاس
  document.body.classList.add('case-info-active');
  
  // داده تست
  testCaseInfoPanel();
  
  console.log('✅ پنل به صورت کامل فعال شد');
} else {
  console.error('❌ Element پنل در DOM وجود ندارد!');
  console.log('💡 صفحه را refresh کنید');
}
```

---

**📅 آخرین به‌روزرسانی:** 2025-10-29  
**🔧 نسخه:** 1.0

