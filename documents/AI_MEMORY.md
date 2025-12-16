# 🧠 AI Memory - RAG-Ingest Project

**آخرین به‌روزرسانی**: 1404/09/25 (2025-12-15)

---

## 📌 خلاصه پروژه

**RAG-Ingest** سیستم مدیریت اسناد حقوقی با قابلیت:
- Embedding و Vector Search
- Chunking هوشمند فارسی
- همگام‌سازی با Core (Qdrant)
- پنل مدیریت Django

---

## 🔧 تنظیمات مهم

### Embedding
```
Model: intfloat/multilingual-e5-large
Dimension: 1024
Chunk Size: 350 tokens
Chunk Overlap: 80 tokens
Persian Numbers: تبدیل به انگلیسی
```

### مدل‌ها
- **LegalUnit**: بند قانونی (MPTT Tree)
- **LUnit**: Proxy Model برای LegalUnit (Admin ساده‌تر)
- **QAEntry**: پرسش و پاسخ
- **TextEntry**: متون آزاد
- **Chunk**: قطعه متنی (ForeignKey به هر سه مدل بالا)
- **Embedding**: بردار معنایی (GenericRelation)

---

## 📝 تغییرات اخیر (Session های قبلی)

### 1. سیستم Chunking یکپارچه
- ✅ QAEntry و TextEntry حالا chunk می‌شوند
- ✅ Chunk model دارای `unit`, `qaentry`, `textentry` ForeignKey
- ✅ سیگنال‌های post_save برای هر سه مدل

### 2. بهینه‌سازی Admin
- ✅ LegalUnit Admin: Navigation دو مرحله‌ای
- ✅ Parent Field: Autocomplete با AJAX
- ✅ حل مشکل validation فیلد parent
- ✅ حذف Core Statistics page

### 3. گزارشات Embedding
- ✅ آمار LegalUnit, QAEntry, TextEntry
- ✅ تعداد Chunks و درصد Embedding
- ✅ آمار همگام‌سازی با Core

### 4. اصلاحات فرم
- ✅ Label تاریخ: "تاریخ نسخه/تصویب"
- ✅ Parent queryset: فیلتر به manifestation
- ✅ حذف cache مشکل‌ساز

---

## 📝 تغییرات Session 1404/09/26 (2025-12-16)

### 1. دکمه حذف برچسب در LUnit Admin
**هدف**: اضافه کردن دکمه ضربدر (✕) برای حذف سریع برچسب‌ها

**فایل‌های تغییر یافته**:
- `/srv/ingest/apps/documents/admin_lunit.py` - اضافه کردن view `delete_tags_view`
- `/srv/ingest/templates/admin/documents/lunit/change_form.html` - JavaScript برای دکمه حذف

**تغییرات در admin_lunit.py**:
```python
# در get_urls اضافه شد:
path('<path:object_id>/delete-tags/', self.admin_site.admin_view(self.delete_tags_view), name='lunit_delete_tags'),

# متد جدید delete_tags_view:
def delete_tags_view(self, request, object_id):
    # POST request با JSON body: {tag_ids: [...]}
    # حذف LegalUnitVocabularyTerm با id های داده شده
    # برگرداندن JSON response
```

**تغییرات در change_form.html**:
- تابع `deleteSingleTag(tagId, row)` برای حذف AJAX
- در DOMContentLoaded: پیدا کردن inline برچسب‌ها و اضافه کردن دکمه ✕
- دکمه در ستون "حذف؟" قرار می‌گیرد (جایگزین checkbox)
- متن توضیحی در `td.original > p` مخفی می‌شود (hidden inputs حفظ می‌شوند)

### 2. نکات مهم

**⚠️ مشکل شناخته شده**:
- وقتی برچسب با AJAX حذف می‌شود، صفحه reload می‌شود
- اگر بدون reload دکمه ذخیره زده شود، خطای validation می‌دهد
- **راه‌حل فعلی**: reload صفحه بعد از هر حذف

**⚠️ td.original**:
- این td حاوی hidden input های `id` و `legal_unit` است
- **هرگز innerHTML را خالی نکنید** - فقط `<p>` را مخفی کنید
- اگر hidden inputs حذف شوند، فرم Django خطا می‌دهد

### 3. دستورات کپی به container
```bash
# کپی template
docker cp /srv/ingest/templates/admin/documents/lunit/change_form.html deployment-web-1:/app/ingest/templates/admin/documents/lunit/change_form.html

# کپی admin_lunit.py
docker cp /srv/ingest/apps/documents/admin_lunit.py deployment-web-1:/app/ingest/apps/documents/admin_lunit.py

# restart برای اعمال تغییرات template
docker restart deployment-web-1
```

### 4. ساختار HTML inline برچسب‌ها
```html
<div id="unit_vocabulary_terms-group">
  <table>
    <tbody>
      <tr class="form-row has_original" id="unit_vocabulary_terms-0">
        <td class="original">
          <p>فصل 9 > ماده 114 - نماینده (وزن: 6)</p>
          <input type="hidden" name="unit_vocabulary_terms-0-id" value="...">
          <input type="hidden" name="unit_vocabulary_terms-0-legal_unit" value="...">
        </td>
        <td class="field-vocabulary_term">...</td>
        <td class="field-weight">...</td>
        <td class="delete"><input type="checkbox" name="...-DELETE"></td>
      </tr>
    </tbody>
  </table>
</div>
```

---

## ⚠️ نکات مهم

### 1. LUnit vs LegalUnit
- **LUnit** یک Proxy Model است
- هر دو به یک جدول اشاره می‌کنند
- LUnit برای Admin ساده‌تر طراحی شده
- **هرگز rename نکنید** - ریسک بالا

### 2. بعد از تغییر کد
```bash
# کپی به container
docker cp /srv/ingest/apps/documents/admin.py deployment-web-1:/app/ingest/apps/documents/admin.py

# restart
docker compose -f docker-compose.ingest.yml restart web worker
```

### 3. فایل‌های حساس
- `/srv/ingest/apps/documents/models.py` - مدل‌های اصلی
- `/srv/ingest/apps/documents/admin.py` - تنظیمات Admin
- `/srv/ingest/apps/documents/forms.py` - فرم‌ها
- `/srv/ingest/apps/documents/signals_unified.py` - سیگنال‌ها

---

## 🐛 مشکلات حل‌شده

### 1. Parent Field Validation Error
**مشکل**: "یک گزینه معتبر انتخاب کنید"
**علت**: queryset خالی یا cache شده
**راه‌حل**: 
- `formfield_for_foreignkey` در admin
- فیلتر به manifestation_id
- حذف `.all()` cache

### 2. صفحه Add کند
**علت**: load همه LegalUnit ها در parent dropdown
**راه‌حل**:
- فیلتر به manifestation
- استفاده از `.only()` برای فیلدهای لازم
- Lazy loading inlines

### 3. Embedding ایجاد نمی‌شود
**بررسی**:
```bash
docker logs deployment-worker-1 --tail 100
```
**راه‌حل**: restart worker

---

## 📊 آمار فعلی (تقریبی)

| مدل | تعداد |
|-----|-------|
| LegalUnit | ~4300 |
| QAEntry | ~500 |
| TextEntry | ~100 |
| Chunk | ~15000 |
| Embedding | ~14000 |

---

## 🔗 URL های مهم

| صفحه | URL |
|------|-----|
| Admin | `/admin/` |
| LUnit List | `/admin/documents/lunit/` |
| Embedding Reports | `/admin/embeddings/embeddingreports/` |
| Core Node Viewer | `/admin/embeddings/corenodeviewer/` |

---

## 📁 ساختار پوشه documents

```
/srv/documents/
├── PROJECT_DOCUMENTATION.md  # مستندات جامع
├── AI_MEMORY.md              # این فایل
├── ToDoList.md               # آرشیو - تحلیل performance
├── LUNIT_COMPLETE_GUIDE.md   # آرشیو - راهنمای LUnit
├── CHANGES_2025-11-22.md     # آرشیو - تغییرات
├── FIXES_2025-11-22_PARENT_FIELD.md  # آرشیو - اصلاح parent
└── LEGALUNIT_FORM_ANALYSIS.md # آرشیو - تحلیل فرم
```

---

## 🎯 کارهای باقی‌مانده

1. ⏳ بهینه‌سازی MPTT partial rebuild
2. ⏳ Cache parent options با Redis
3. ⏳ تست‌های خودکار برای Chunking
4. ⏳ Monitoring با Prometheus

---

## 💡 نکات برای AI بعدی

1. **قبل از تغییر models.py**: همیشه migration بسازید
2. **قبل از تغییر admin.py**: فایل را کامل بخوانید
3. **برای debug**: از Django shell استفاده کنید
4. **برای تست**: فایل را به container کپی کنید
5. **LegalUnit rename**: انجام ندهید - ریسک بالا

---

**تهیه‌کننده**: Cascade AI  
**نسخه**: 1.0
