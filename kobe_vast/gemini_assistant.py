# -*- coding: utf-8 -*-
"""Gemini AI + voice commands — runs inside project files."""
import base64
import json
import os
import re
from datetime import datetime
from pathlib import Path

import requests
import streamlit as st

TRAINING_FILE = Path(__file__).resolve().parent / "voice_training.json"

DEFAULT_EXAMPLES = [
    {"phrase": "سجل بيع 5 كيلو كولومبي لعميل أحمد", "intent": "sale", "note": "بيع مباشر"},
    {"phrase": "أضف 3 كيلو حبشي بليند للفاتورة", "intent": "add_cart", "note": "إضافة للسلة"},
    {"phrase": "اعرض تقرير مبيعات اليوم", "intent": "report", "note": "تقرير يومي"},
    {"phrase": "كم السيولة في الخزينة", "intent": "report", "note": "استعلام خزينة"},
    {"phrase": "حصّل 500 جنيه من محمد", "intent": "payment", "note": "تحصيل دفعة"},
]


def load_training():
    if TRAINING_FILE.exists():
        try:
            return json.loads(TRAINING_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"examples": DEFAULT_EXAMPLES.copy()}


def save_training(data):
    TRAINING_FILE.parent.mkdir(parents=True, exist_ok=True)
    TRAINING_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def add_training_example(phrase, intent, note=""):
    data = load_training()
    data.setdefault("examples", []).append({"phrase": phrase, "intent": intent, "note": note})
    save_training(data)


def _gemini_text(prompt, api_key, timeout=20):
    if not api_key:
        return None, "أضف Gemini API Key من الإعدادات"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    try:
        resp = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=timeout,
        )
        if resp.status_code != 200:
            return None, f"Gemini error {resp.status_code}"
        text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        return text.strip(), None
    except Exception as e:
        return None, str(e)


def transcribe_audio(audio_bytes, mime_type, api_key):
    if not api_key:
        return None, "أضف Gemini API Key"
    b64 = base64.b64encode(audio_bytes).decode()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": mime_type or "audio/wav", "data": b64}},
                {"text": "اكتب بالعربية المصرية ما قاله المستخدم. أرجع النص المنطوق فقط بدون شرح."},
            ]
        }]
    }
    try:
        resp = requests.post(url, json=payload, timeout=30)
        if resp.status_code != 200:
            return None, f"فشل التحويل {resp.status_code}"
        text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        return text, None
    except Exception as e:
        return None, str(e)


def _build_prompt(cmd, context, training_examples):
    examples_txt = "\n".join(f'- "{ex["phrase"]}" → {ex["intent"]}' for ex in training_examples[:15])
    return f"""أنت مساعد Kobe Green ERP بالعربية.
أمثلة تدريبية من المستخدم:
{examples_txt}

بيانات النظام:
{json.dumps(context, ensure_ascii=False)}

الأمر: "{cmd}"

أرجع JSON فقط:
{{"action":"sale|add_cart|payment|report|chat","item":"اسم الصنف","type":"أخضر|محمص|مطحون|كوبي كاب","qty":0,"price":0,"client":"اسم","amount":0,"message":"رد عربي"}}
- add_cart: إضافة للفاتورة قبل الإصدار
- report: تقرير أو استعلام
- sale: بيع مباشر
- payment: تحصيل
"""


def _parse_json_response(text):
    clean = text.replace("```json", "").replace("```", "").strip()
    m = re.search(r"\{.*\}", clean, re.DOTALL)
    if m:
        return json.loads(m.group())
    return json.loads(clean)


def run_gemini_command(cmd, api_key, context, handlers):
    """
    handlers: dict with keys execute_sale, execute_payment, execute_report, add_to_cart
    """
    training = load_training().get("examples", [])
    prompt = _build_prompt(cmd, context, training)
    text, err = _gemini_text(prompt, api_key)
    if err:
        return f"⚠️ {err}"
    try:
        data = _parse_json_response(text)
    except Exception:
        return f"🤖 {text}"

    action = data.get("action", "chat")
    if action == "chat":
        return f"🤖 {data.get('message', text)}"
    if action == "add_cart" and handlers.get("add_to_cart"):
        return handlers["add_to_cart"](data)
    if action == "sale" and handlers.get("execute_sale"):
        return handlers["execute_sale"](data)
    if action == "payment" and handlers.get("execute_payment"):
        return handlers["execute_payment"](data)
    if action == "report" and handlers.get("execute_report"):
        return handlers["execute_report"](data)
    return f"🤖 {data.get('message', 'تم')}"


def render_gemini_sidebar(cfg, handlers):
    """Sidebar UI: text, voice, training."""
    st.markdown("### 🤖 المساعد الذكي (Gemini)")
    api_key = cfg.get("gemini_key", "")
    if not api_key:
        st.caption("⚠️ أضف Gemini Key من الإعدادات")

    t_chat, t_voice, t_train = st.tabs(["💬 كتابة", "🎤 صوت", "📚 تدريب"])

    with t_chat:
        cmd = st.chat_input("اطلب فاتورة، تقرير، أو تحليل...")
        if cmd:
            with st.spinner("جاري التفكير..."):
                resp = run_gemini_command(cmd, api_key, handlers.get("context", {}), handlers)
                st.success(resp)

    with t_voice:
        st.caption("سجّل صوتك — مثال: «أضف 2 كيلو كولومبي للفاتورة»")
        audio = st.audio_input("تسجيل صوتي", key="gemini_voice_in")
        if audio is not None:
            if st.button("🎤 تحويل وتنفيذ", key="voice_run", use_container_width=True):
                with st.spinner("تحويل الصوت..."):
                    text, err = transcribe_audio(audio.getvalue(), audio.type, api_key)
                if err:
                    st.error(err)
                elif text:
                    st.info(f"سمعت: **{text}**")
                    resp = run_gemini_command(text, api_key, handlers.get("context", {}), handlers)
                    st.success(resp)

    with t_train:
        st.caption("علّم المساعد عباراتك المعتادة")
        data = load_training()
        for ex in data.get("examples", [])[-5:]:
            st.caption(f"• {ex['phrase']} → {ex['intent']}")
        new_phrase = st.text_input("عبارة جديدة", placeholder="مثال: اعمل فاتورة 10 كيلو برازيلي")
        new_intent = st.selectbox("النوع", ["add_cart", "sale", "report", "payment", "chat"])
        if st.button("💾 حفظ التدريب", use_container_width=True) and new_phrase:
            add_training_example(new_phrase, new_intent)
            st.success("تم الحفظ في voice_training.json")
            st.rerun()
