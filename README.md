# Kobe Green ERP

كوبي جرين | KOBE GREEN — ERP & CRM على Supabase PostgreSQL

## التشغيل المحلي

```bash
pip install -r requirements.txt
streamlit run app.py
```

تسجيل الدخول: `admin` / `123`

## Streamlit Cloud

- **Main file:** `app.py`
- **Secrets:** انظر `STREAMLIT_SECRETS.txt`

## الملفات الأساسية

| ملف | الوظيفة |
|-----|---------|
| `app.py` | التطبيق الرئيسي |
| `pg_compat.py` | طبقة PostgreSQL |
| `auto_migrate_kobe.py` | إنشاء الجداول على Supabase |
