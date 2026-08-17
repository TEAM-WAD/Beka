import telebot
from telebot import types
import requests
import sqlite3
import threading
import time
from datetime import datetime, timedelta
import re
import json
import random
import os
from PIL import Image, ImageDraw, ImageFont, ImageOps
import math
import arabic_reshaper
from bidi.algorithm import get_display

# ==================== الإعدادات الأساسية ====================
BOT_TOKEN = "8892595660:AAErIF3uBxbi8_CjYJwIelpuRN__16ug-Ng"
API_URL = "https://ylafollow.com/api/v2"  
API_KEY = "2ff0c9c3dbf8db742196dd1d4215bbe2"
ADMIN_ID = 6805697054 

FREE_API_URLS = [
    "https://ylafollow.com/api/v2",
    "https://ylafollow.com/api/v2",
    "https://ylafollow.com/api/v2",
    "https://ylafollow.com/api/v2",
    "https://ylafollow.com/api/v2"
]
FREE_API_KEYS = [
    "6efadb102339622ee527a5c2740aa120",
    "5aeb07521d37edc3417dd35b2763860d",
    "4aa29f82f28c595d436789e3326d4a80",
    "1fc559a19aff27265e699a280fdf833b",
    "7241d6062cc83257e7a6eb5243c455ab"
]

bot = telebot.TeleBot(BOT_TOKEN)
conversion_lock = threading.Lock() # قفل أمني لمنع الثغرات والضغط المزدوج

def strip_html(text):
    return re.sub(r'<[^>]*>', '', str(text)) if text else ""

def clean_forbidden_text(text):
    if not text:
        return ""
    t = str(text)
    t = re.sub(r'آيدي الخدمة:?.*', '', t)
    t = re.sub(r'رقم الخدمة:?.*', '', t)
    t = re.sub(r'service_id:?.*', '', t, flags=re.IGNORECASE)
    return t

def fix_arabic(text):
    if not text:
        return ""
    try:
        reshaped_text = arabic_reshaper.reshape(str(text))
        bidi_text = get_display(reshaped_text)
        return bidi_text
    except Exception:
        return str(text)

def get_admin_link():
    try:
        chat = bot.get_chat(ADMIN_ID)
        if chat.username:
            return f"https://t.me/{chat.username}"
    except Exception:
        pass
    return f"tg://user?id={ADMIN_ID}"

def translate_status(status_str):
    if not status_str:
        return "قيد الانتظار ⏳"
    s = str(status_str).lower().strip()
    status_map = {
        "pending": "قيد الانتظار ⏳",
        "in progress": "قيد التنفيذ 🔄",
        "processing": "جاري المعالجة 🔄",
        "completed": "مكتمل بنجاح ✅",
        "partial": "مكتمل جزئياً ⚠️",
        "canceled": "ملغى وتم الإعادة ❌",
        "cancelled": "ملغى وتم الإعادة ❌"
    }
    return status_map.get(s, status_str)

user_steps = {}

PLATFORMS = [
    ("🎵 تيك توك", "tiktok"),
    ("📷 انستغرام", "instagram"),
    ("▶️ يوتيوب", "youtube"),
    ("📘 فيسبوك", "facebook"),
    ("✈️ تليغرام", "telegram"),
    ("🐦 تويتر", "twitter"),
    ("🎧 سبوتيفاي", "spotify")
]

SERVICE_TYPES = [
    ("❤️ لايكات", "likes"),
    ("👥 متابعين", "followers"),
    ("👁️ مشاهدات", "views"),
    ("💬 تعليقات", "comments")
]

PLATFORM_KEYWORDS = {
    "tiktok": ["تيك توك", "تيكتوك", "تيك", "tiktok", "tt"],
    "instagram": ["انستغرام", "انستقرام", "انستجرام", "انستا", "instagram", "insta", "ig"],
    "youtube": ["يوتيوب", "يوتیوب", "youtube", "yt"],
    "facebook": ["فيسبوك", "فيس بوك", "فيس", "facebook", "fb"],
    "telegram": ["تليغرام", "تيليجرام", "تلغرام", "تلجرام", "telegram", "tg"],
    "twitter": ["تويتر", "إكس", "x", "twitter"],
    "spotify": ["سبوتيفاي", "سبوتفاي", "spotify"]
}

TYPE_KEYWORDS = {
    "likes": ["لايكات", "لايك", "إعجاب", "اعجاب", "إعجابات", "اعجابات", "تفاعل", "تفاعلات", "like", "likes", "reaction"],
    "followers": ["متابعين", "متابع", "متابعة", "مشتركين", "مشترك", "أعضاء", "اعضاء", "عضو", "follower", "followers", "subscribers", "member", "members"],
    "views": ["مشاهدات", "مشاهدة", "مشاهده", "view", "views"],
    "comments": ["تعليقات", "تعليق", "كومنتات", "كومنت", "comment", "comments"]
}

# ==================== قاعدة البيانات (SQLite) ====================
def init_db():
    conn = sqlite3.connect("store_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance REAL DEFAULT 0.0,
            spent REAL DEFAULT 0.0,
            points INTEGER DEFAULT 0,
            referrals_count INTEGER DEFAULT 0,
            referred_by INTEGER DEFAULT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY,
            user_id INTEGER,
            service_name TEXT,
            link TEXT,
            quantity INTEGER,
            status TEXT DEFAULT 'Pending',
            price REAL DEFAULT 0.0,
            created_at TEXT,
            is_blocked INTEGER DEFAULT 0,
            warranty_days INTEGER DEFAULT 0,
            warranty_end TEXT,
            receipt_code TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS deleted_receipts (
            order_id INTEGER PRIMARY KEY,
            user_id INTEGER,
            service_name TEXT,
            link TEXT,
            quantity INTEGER,
            price REAL,
            created_at TEXT,
            deleted_at TEXT,
            receipt_code TEXT
        )
    ''')

    for col, defv in [
        ("price", "REAL DEFAULT 0.0"),
        ("created_at", "TEXT"),
        ("is_blocked", "INTEGER DEFAULT 0"),
        ("warranty_days", "INTEGER DEFAULT 0"),
        ("warranty_end", "TEXT"),
        ("receipt_code", "TEXT")
    ]:
        try: cursor.execute(f"ALTER TABLE orders ADD COLUMN {col} {defv}")
        except sqlite3.OperationalError: pass

    for col, defv in [
        ("points", "INTEGER DEFAULT 0"),
        ("referrals_count", "INTEGER DEFAULT 0"),
        ("referred_by", "INTEGER DEFAULT NULL")
    ]:
        try: cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {defv}")
        except sqlite3.OperationalError: pass

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS custom_services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT,
            stype TEXT,
            service_id TEXT,
            name TEXT,
            rate REAL,
            min_q INTEGER,
            max_q INTEGER,
            description TEXT,
            is_active INTEGER DEFAULT 1
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS auto_channel_bot (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT,
            service_id TEXT,
            service_name TEXT,
            quantity INTEGER,
            interval_minutes INTEGER,
            is_active INTEGER DEFAULT 1
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_auto_boost (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_id TEXT,
            service_name TEXT,
            link TEXT,
            quantity INTEGER,
            interval_seconds INTEGER,
            last_run TEXT,
            is_active INTEGER DEFAULT 1
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS balance_transfers (
            code TEXT PRIMARY KEY,
            sender_id INTEGER,
            amount REAL,
            created_at TEXT,
            is_used INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_subscriptions (
            user_id INTEGER PRIMARY KEY,
            platform TEXT,
            channel_id TEXT,
            start_date TEXT,
            end_date TEXT,
            is_active INTEGER DEFAULT 1
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS auto_boost_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            channel_id TEXT,
            message_id INTEGER,
            created_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def auto_clean_old_receipts():
    while True:
        try:
            conn = sqlite3.connect("store_database.db", check_same_thread=False)
            cursor = conn.cursor()
            
            now = datetime.now()
            thirty_days_ago = (now - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("SELECT order_id, user_id, service_name, link, quantity, price, created_at, receipt_code FROM orders WHERE created_at <= ?", (thirty_days_ago,))
            old_30_orders = cursor.fetchall()

            for ord_item in old_30_orders:
                oid, uid, sname, link, qty, price, c_at, r_code = ord_item
                del_at = now.strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("""
                    INSERT OR REPLACE INTO deleted_receipts 
                    (order_id, user_id, service_name, link, quantity, price, created_at, deleted_at, receipt_code)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (oid, uid, sname, link, qty, price, c_at, del_at, r_code))
                
                cursor.execute("DELETE FROM orders WHERE order_id = ?", (oid,))

            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Auto clean error: {e}")
        time.sleep(3600)

clean_thread = threading.Thread(target=auto_clean_old_receipts)
clean_thread.daemon = True
clean_thread.start()

def get_user_data(user_id):
    conn = sqlite3.connect("store_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT balance, spent FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO users (user_id, balance, spent, points, referrals_count) VALUES (?, 0.0, 0.0, 0, 0)", (user_id,))
        conn.commit()
        balance, spent = 0.0, 0.0
    else:
        balance, spent = row[0], row[1]
    conn.close()
    return balance, spent

def get_user_points_data(user_id):
    conn = sqlite3.connect("store_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT balance, spent, points, referrals_count FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO users (user_id, balance, spent, points, referrals_count) VALUES (?, 0.0, 0.0, 0, 0)", (user_id,))
        conn.commit()
        balance, spent, points, referrals_count = 0.0, 0.0, 0, 0
    else:
        balance, spent = row[0] or 0.0, row[1] or 0.0
        points = row[2] if row[2] is not None else 0
        referrals_count = row[3] if row[3] is not None else 0
    conn.close()
    return balance, spent, points, referrals_count

def process_referral(new_user_id, referrer_id):
    conn = sqlite3.connect("store_database.db", check_same_thread=False)
    cursor = conn.cursor()

    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (new_user_id,))
    if cursor.fetchone():
        conn.close()
        return False

    if new_user_id == referrer_id:
        conn.close()
        return False

    cursor.execute("SELECT points, balance FROM users WHERE user_id = ?", (referrer_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False

    cursor.execute("INSERT INTO users (user_id, balance, spent, points, referrals_count, referred_by) VALUES (?, 0.0, 0.0, 0, 0, ?)", (new_user_id, referrer_id))
    
    cursor.execute("""
        UPDATE users 
        SET points = points + 2, 
            referrals_count = referrals_count + 1 
        WHERE user_id = ?
    """, (referrer_id,))

    conn.commit()
    conn.close()
    return True

def notify_referrer_async(referrer_id):
    def send_and_delete():
        try:
            ref_msg_text = (
                "🎉 <b>إشعار جديد!</b>\n\n"
                "👤 <b>قام شخص جديد بالدخول إلى البوت عن طريق رابط الدعوة الخاص بك!</b>\n"
                "🎁 <b>حصلت على +2 نقطة بنجاح!</b> ✨\n\n"
                "⏱️ <i>(سوف تختفي هذه الرسالة تلقائياً خلال دقيقة مع الاحتفاظ بنقاطك)</i>"
            )
            sent_msg = bot.send_message(referrer_id, ref_msg_text, parse_mode="HTML")
            time.sleep(60)
            try:
                bot.delete_message(referrer_id, sent_msg.message_id)
            except Exception:
                pass
        except Exception as e:
            print(f"Error notifying referrer: {e}")

    t = threading.Thread(target=send_and_delete)
    t.daemon = True
    t.start()

def update_user_balance_spent(user_id, amount):
    conn = sqlite3.connect("store_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance - ?, spent = spent + ? WHERE user_id = ?", (amount, amount, user_id))
    conn.commit()
    conn.close()

def check_user_subscription(user_id, platform="instagram"):
    conn = sqlite3.connect("store_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT channel_id, end_date FROM user_subscriptions WHERE user_id = ? AND platform = ? AND is_active = 1", (user_id, platform))
    row = cursor.fetchone()
    conn.close()
    if row:
        try:
            end_date = datetime.strptime(row[1], "%Y-%m-%d %H:%M:%S")
            if datetime.now() < end_date:
                return True, row[0]
        except Exception:
            return True, row[0]
    return False, None

def save_order(order_id, user_id, service_name, link, quantity, price, warranty_days=0, receipt_code=None):
    conn = sqlite3.connect("store_database.db", check_same_thread=False)
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    warranty_end = None
    if warranty_days > 0:
        warranty_end = (datetime.now() + timedelta(days=warranty_days)).strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO orders (order_id, user_id, service_name, link, quantity, status, price, created_at, is_blocked, warranty_days, warranty_end, receipt_code) 
        VALUES (?, ?, ?, ?, ?, 'Pending', ?, ?, 0, ?, ?, ?)
    """, (order_id, user_id, service_name, link, quantity, price, now_str, warranty_days, warranty_end, str(receipt_code)))
    conn.commit()
    conn.close()

def get_user_orders_count(user_id):
    conn = sqlite3.connect("store_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM orders WHERE user_id = ?", (user_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_user_orders_list(user_id, offset=0, limit=10):
    conn = sqlite3.connect("store_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT order_id, service_name, quantity, created_at, price 
        FROM orders WHERE user_id = ? 
        ORDER BY order_id ASC LIMIT ? OFFSET ?
    """, (user_id, limit, offset))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_setting(key, default=1):
    conn = sqlite3.connect("store_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    if row and row[0] is not None:
        try: return int(row[0])
        except ValueError: return row[0]
    return default

def set_setting_text(key, text_val):
    conn = sqlite3.connect("store_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = ?", (key, str(text_val), str(text_val)))
    conn.commit()
    conn.close()

def get_setting_text(key, default_val):
    conn = sqlite3.connect("store_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return str(row[0]) if row and row[0] is not None else str(default_val)

def get_all_platforms():
    return [(get_setting_text(f"name_plat_{code}", default_name), code) for default_name, code in PLATFORMS]

def get_all_service_types():
    return [(get_setting_text(f"name_type_{stype}", default_name), stype) for default_name, stype in SERVICE_TYPES]

def add_custom_service(platform, stype, service_id, name, rate, min_q, max_q, description):
    conn = sqlite3.connect("store_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO custom_services (platform, stype, service_id, name, rate, min_q, max_q, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (platform, stype, str(service_id), name, rate, min_q, max_q, description))
    conn.commit()
    conn.close()

def get_custom_services(platform=None, stype=None):
    conn = sqlite3.connect("store_database.db", check_same_thread=False)
    cursor = conn.cursor()
    if platform and stype:
        cursor.execute("SELECT service_id, name, rate, min_q, max_q, description FROM custom_services WHERE platform = ? AND stype = ? AND is_active = 1", (platform, stype))
    else:
        cursor.execute("SELECT service_id, name, rate, min_q, max_q, description FROM custom_services WHERE is_active = 1")
    rows = cursor.fetchall()
    conn.close()
    return [{"service": str(r[0]), "name": r[1], "rate": adjust_api_rate(r[2]), "min": str(r[3]), "max": str(r[4]), "desc": r[5]} for r in rows]

def adjust_api_rate(raw_rate):
    try:
        r = float(raw_rate)
    except (ValueError, TypeError):
        return str(raw_rate)
    
    if r <= 0:
        return "0.00"

    c = round(r * 100, 2)

    if c <= 6: adjusted_val = 0.10
    elif c <= 10: adjusted_val = 0.15
    elif c <= 16: adjusted_val = 0.20
    elif c <= 20: adjusted_val = 0.25
    elif c <= 26: adjusted_val = 0.30
    elif c <= 30: adjusted_val = 0.35
    elif c <= 36: adjusted_val = 0.40
    elif c <= 40: adjusted_val = 0.45
    elif c <= 46: adjusted_val = 0.50
    elif c <= 50: adjusted_val = 0.55
    elif c <= 56: adjusted_val = 0.60
    elif c <= 60: adjusted_val = 0.65
    elif c <= 66: adjusted_val = 0.70
    elif c <= 70: adjusted_val = 0.75
    elif c <= 76: adjusted_val = 0.80
    elif c <= 80: adjusted_val = 0.85
    elif c <= 86: adjusted_val = 0.90
    elif c <= 90: adjusted_val = 0.95
    elif c <= 96: adjusted_val = 1.00
    elif c <= 99: adjusted_val = 1.30
    else: adjusted_val = 1.50

    try:
        discount_cents = float(get_setting_text("global_discount_cents", "0"))
    except Exception:
        discount_cents = 0.0

    if discount_cents > 0:
        discount_dollars = discount_cents / 100.0
        adjusted_val = max(0.01, adjusted_val - discount_dollars)

    return f"{adjusted_val:.2f}"

def fetch_api_services(use_free_pool=False):
    urls = FREE_API_URLS if use_free_pool else [API_URL]
    keys = FREE_API_KEYS if use_free_pool else [API_KEY]
    for url, key in zip(urls, keys):
        try:
            response = requests.post(url, data={"key": key, "action": "services"}, timeout=10)
            if response.status_code == 200:
                res_json = response.json()
                if isinstance(res_json, list):
                    for s in res_json:
                        if "rate" in s:
                            s["rate"] = adjust_api_rate(s["rate"])
                    return res_json
        except Exception:
            continue
    return []

def send_api_order_with_failover(payload, is_free=False):
    urls = FREE_API_URLS if is_free else [API_URL]
    keys = FREE_API_KEYS if is_free else [API_KEY]
    for url, key in zip(urls, keys):
        try:
            p = payload.copy()
            p["key"] = key
            response = requests.post(url, data=p, timeout=10)
            if response.status_code == 200:
                res_json = response.json()
                if isinstance(res_json, dict) and "order" in res_json and res_json["order"] and "error" not in res_json:
                    return res_json
                elif isinstance(res_json, dict) and "error" in res_json:
                    return res_json
        except Exception:
            continue
    return {"error": "فشل الاتصال بجميع البوابات المتاحة"}

# ==================== توليد الفاتورة الاحترافية بدون ختم أو توقيع معتمد ====================

def generate_invoice_image(order_id, user_id, service_name, quantity, total_cost, rate_val, warranty_text="", invoice_no_arg=None):
    invoice_no = invoice_no_arg if invoice_no_arg else str(random.randint(100000, 999999))
    now = datetime.now()
    date_formatted = f"{now.year}/{now.month}/{now.day}"
    hour_12 = now.strftime("%I:%M:%S")
    ampm = "م" if now.hour >= 12 else "ص"
    time_formatted = f"{hour_12} {ampm}"
    
    if total_cost <= 0 or rate_val <= 0:
        price_str = "خدمة مجانية"
        unit_price_str = "خدمة مجانية"
    else:
        price_str = f"{total_cost:.3f} $"
        unit_price_str = f"{rate_val} $"

    img_w, img_h = 1200, 2150 if warranty_text else 2050
    img = Image.new("RGB", (img_w, img_h), "#F1F5F9")
    draw = ImageDraw.Draw(img)

    font_paths = ["/system/fonts/NotoNaskhArabic-Regular.ttf", "/system/fonts/DroidArabicKufi.ttf", "arial.ttf", "DejaVuSans.ttf"]
    font_path = "arial.ttf"
    for p in font_paths:
        if os.path.exists(p):
            font_path = p
            break

    try:
        font_title = ImageFont.truetype(font_path, 68)
        font_badge = ImageFont.truetype(font_path, 34)
        font_label = ImageFont.truetype(font_path, 36)
        font_val = ImageFont.truetype(font_path, 36)
        font_note = ImageFont.truetype(font_path, 28)
        font_note_title = ImageFont.truetype(font_path, 32)
        font_footer = ImageFont.truetype(font_path, 42)
    except Exception:
        font_title = font_badge = font_label = font_val = font_note = font_note_title = font_footer = ImageFont.load_default()

    card_x1, card_y1, card_x2, card_y2 = 60, 60, 1140, img_h - 60
    draw.rounded_rectangle([card_x1, card_y1, card_x2, card_y2], radius=35, fill="white", outline="#CBD5E1", width=3)

    header_h = 260
    draw.rounded_rectangle([card_x1, card_y1, card_x2, card_y1 + header_h], radius=35, fill="#0F172A")
    draw.rectangle([card_x1, card_y1 + 180, card_x2, card_y1 + header_h], fill="#0F172A")

    draw.text((card_x1 + 50, card_y1 + 40), fix_arabic("𓆩 𓊈 فاتورة 𓉇 𓆪"), fill="white", font=font_title)
    draw.text((card_x1 + 50, card_y1 + 150), fix_arabic("حالة الطلب: تم بنجاح"), fill="#94A3B8", font=font_badge)
    
    badge_w, badge_h = 360, 80
    badge_x1 = card_x2 - badge_w - 50
    badge_y1 = card_y1 + 80
    draw.rounded_rectangle([badge_x1, badge_y1, card_x2 - 50, badge_y1 + badge_h], radius=20, fill="#10B981")
    
    badge_text = fix_arabic(invoice_no)
    bbox_b = draw.textbbox((0, 0), badge_text, font=font_badge)
    bw = bbox_b[2] - bbox_b[0]
    bh = bbox_b[3] - bbox_b[1]
    bx = badge_x1 + (badge_w - bw) // 2
    by = badge_y1 + (badge_h - bh) // 2 - 4
    draw.text((bx, by), badge_text, fill="white", font=font_badge)

    clean_service_name = clean_forbidden_text(service_name)
    clean_service_name = clean_service_name[:32] + "..." if len(clean_service_name) > 32 else clean_service_name
    ar_service_name = fix_arabic(clean_service_name)

    items = [
        ("رقم الفاتورة", fix_arabic(invoice_no), "#0F172A"),
        ("التاريخ", fix_arabic(date_formatted), "#0F172A"),
        ("الوقت", fix_arabic(time_formatted), "#0F172A"),
        ("اسم الخدمة", ar_service_name, "#0F172A"),
        ("الكمية المطلوبة", fix_arabic(f"{quantity:,}"), "#0F172A"),
        ("السعر", fix_arabic(unit_price_str), "#0F172A"),
        ("إجمالي المبلغ", fix_arabic(price_str), "#059669")
    ]
    if warranty_text:
        items.insert(4, ("تفاصيل الضمان", fix_arabic(warranty_text), "#D97706"))

    start_y = card_y1 + 320
    row_height = 100

    for label, val, val_color in items:
        draw.text((card_x1 + 50, start_y), fix_arabic(label), fill="#334155", font=font_label)
        bbox = draw.textbbox((0, 0), val, font=font_val)
        val_w = bbox[2] - bbox[0]
        draw.text((card_x2 - 50 - val_w, start_y), val, fill=val_color, font=font_val)
        draw.line([card_x1 + 50, start_y + 70, card_x2 - 50, start_y + 70], fill="#E2E8F0", width=2)
        start_y += row_height

    note_box_y1 = start_y + 10
    note_box_y2 = note_box_y1 + 200
    draw.rounded_rectangle([card_x1 + 50, note_box_y1, card_x2 - 50, note_box_y2], radius=20, fill="#FEF2F2", outline="#FCA5A5", width=2)
    draw.text((card_x1 + 75, note_box_y1 + 15), fix_arabic("ملاحظة مهمة جداً:"), fill="#DC2626", font=font_note_title)
    draw.text((card_x1 + 75, note_box_y1 + 65), fix_arabic("لأي استفسار أو مراجعه الدعم أو لأي مشكلة في الطلب"), fill="#1E293B", font=font_note)
    draw.text((card_x1 + 75, note_box_y1 + 105), fix_arabic("يرجى الاحتفاظ بهذا الوصل عند مراسلة الدعم."), fill="#1E293B", font=font_note)
    draw.text((card_x1 + 75, note_box_y1 + 145), fix_arabic("بدون هذا الوصل يسقط حقك تماماً ولا نقبل بأي دليل آخر."), fill="#DC2626", font=font_note)

    footer_y = card_y2 - 110
    footer_text = fix_arabic("𓆩 𓊈 شكراً لاستخدامك خدماتنا 𓉇 𓆪")
    bbox_f = draw.textbbox((0, 0), footer_text, font=font_footer)
    fw = bbox_f[2] - bbox_f[0]
    fx = card_x1 + (card_x2 - card_x1 - fw) // 2
    draw.text((fx, footer_y), footer_text, fill="#DC2626", font=font_footer)
    draw.line([card_x1 + 150, footer_y + 65, card_x2 - 150, footer_y + 65], fill="#DC2626", width=6)

    file_name = f"invoice_{order_id}.png"
    img.save(file_name, quality=100)
    return file_name, invoice_no

def send_animated_progress(chat_id, total_seconds, final_text, markup=None):
    msg = bot.send_message(chat_id, "⏳ <b>جاري معالجة طلبك وتجهيز الوصل...</b>\n\n<code>[▒▒▒▒▒▒▒▒▒▒] 0%</code>", parse_mode="HTML")
    steps = 10
    sleep_interval = total_seconds / steps
    for i in range(1, steps + 1):
        time.sleep(sleep_interval)
        filled = "█" * i
        empty = "▒" * (10 - i)
        percent = i * 10
        try:
            bot.edit_message_text(
                f"⏳ <b>جاري معالجة طلبك وتجهيز الوصل...</b>\n\n<code>[{filled}{empty}] {percent}%</code>",
                chat_id=chat_id,
                message_id=msg.message_id,
                parse_mode="HTML"
            )
        except Exception:
            pass
    try:
        bot.delete_message(chat_id, msg.message_id)
    except Exception:
        pass

def broadcast_order_to_channel(order_id, service_name, quantity, price, user_id, warranty_str=""):
    channel_id = get_setting_text("orders_channel_id", "")
    if not channel_id:
        return
    clean_sname = clean_forbidden_text(service_name)
    price_txt = "خدمة مجانية 🎁" if price == 0 else f"${price:.3f}"
    
    text = (
        f"🚨 <b>إشعار طلب جديد مكتمل!</b>\n\n"
        f"🏷️ <b>الخدمة المطلوبة:</b> {clean_sname}\n"
        f"🔢 <b>الكمية المطلوبة:</b> <code>{quantity:,}</code>\n"
        f"💰 <b>التكلفة الإجمالية:</b> {price_txt}\n"
        f"👤 <b>آيدي الزبون:</b> <code>{user_id}</code>\n"
        f"🆔 <b>رقم الطلب:</b> <code>{order_id}</code>\n"
    )
    if warranty_str:
        text += f"🛡️ <b>تفاصيل الضمان:</b> {warranty_str}\n"
    
    markup = types.InlineKeyboardMarkup()
    bot_username = bot.get_me().username
    markup.add(types.InlineKeyboardButton("🚀 دخول للبوت / القناة", url=f"https://t.me/{bot_username}"))
    try:
        bot.send_message(channel_id, text, parse_mode="HTML", reply_markup=markup)
    except Exception as e:
        print(f"Broadcast error: {e}")

# ==================== الواجهة الرئيسية للمستخدم ====================

@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    text_args = message.text.split()
    
    was_referred = False
    referrer_id = None
    if len(text_args) > 1 and text_args[1].isdigit():
        ref_candidate = int(text_args[1])
        if ref_candidate != user_id:
            if process_referral(user_id, ref_candidate):
                was_referred = True
                referrer_id = ref_candidate

    get_user_data(user_id)

    if was_referred and referrer_id:
        welcome_ref_msg = (
            "🎉 <b>أهلاً بك! لقد انضممت إلى البوت عن طريق رابط دعوة صديقك.</b>\n"
            "مرحباً بك في بوت الخدمات الرقمية، يمكنك استخدام كافة الميزات والأقسام المتاحة أدناه! ✨"
        )
        bot.send_message(message.chat.id, welcome_ref_msg, parse_mode="HTML")
        notify_referrer_async(referrer_id)

    send_main_menu(message.chat.id, user_id)

def send_main_menu(chat_id, user_id):
    balance, spent = get_user_data(user_id)
    user_orders_cnt = get_user_orders_count(user_id)
    reward_enabled = get_setting("reward_enabled", 0)
    target_count = get_setting("reward_target_count", 50)

    text_message = (
        f"👋 <b>أهلاً بك في بوت الخدمات الرقمية السريعة!</b>\n\n"
        f"💰 <b>رصيدك داخل البوت:</b> <code>${balance:.3f}</code>\n"
        f"💸 <b>إجمالي إنفاقك:</b> <code>${spent:.3f}</code>\n"
        f"📦 <b>عدد طلباتي الشخصية:</b> <code>{user_orders_cnt}</code> طلب\n"
    )

    if reward_enabled == 1:
        text_message += f"\n📝 <b>ملاحظة:</b> عند إكمال كل <code>{target_count}</code> طلب تحصل على هدية مميزة!\n"

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🛍️ الخدمات", callback_data="main_services"),
        types.InlineKeyboardButton("🇮🇶 دعم ممول حقيقي (عراقيين عرب)", callback_data="funded_support")
    )
    markup.add(
        types.InlineKeyboardButton("🔥 عروض خاصه", callback_data="special_offers"),
        types.InlineKeyboardButton("🎁 خدمات مجانية", callback_data="free_services")
    )
    markup.add(
        types.InlineKeyboardButton("📦 الطلبات", callback_data="my_orders"),
        types.InlineKeyboardButton("💳 إضافة أموال", callback_data="add_funds")
    )
    markup.add(
        types.InlineKeyboardButton("🎯 تجميع نقاط", callback_data="collect_points_info"),
        types.InlineKeyboardButton("💼 باقات الترويج (البيجات)", callback_data="promo_packages")
    )
    markup.add(
        types.InlineKeyboardButton("🎟️ بكجات وخصومات", callback_data="discounts_packages"),
        types.InlineKeyboardButton("🤝 صير وكيل (تاجر)", callback_data="become_agent")
    )

    markup.add(
        types.InlineKeyboardButton("🔄 تحويل نقاطي", callback_data="convert_my_points")
    )

    if reward_enabled == 1:
        markup.add(types.InlineKeyboardButton("🔍 للاستعلام أكثر عن نوع الهدية المقدمة اضغط هنا", callback_data="show_reward_info"))

    if user_id == ADMIN_ID:
        markup.add(types.InlineKeyboardButton("🛠️ لوحة الأدمن", callback_data="admin_panel"))

    bot.send_message(chat_id, text_message, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "back_to_main")
def back_to_main_menu(call):
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass
    send_main_menu(call.message.chat.id, call.from_user.id)

@bot.callback_query_handler(func=lambda call: call.data == "show_reward_info")
def show_reward_info_callback(call):
    reward_type = get_setting_text("reward_type", "money")
    target_count = get_setting("reward_target_count", 50)
    if reward_type == "money":
        money_val = get_setting_text("reward_money_amount", "1$")
        msg = f"🎁 <b>تفاصيل الهدية:</b> عند وصولك إلى <b>{target_count} طلبات</b> تحصل على رصيد مالي بقيمة ({money_val})!"
    else:
        msg = f"🎁 <b>تفاصيل الهدية:</b> عند وصولك إلى <b>{target_count} طلبات</b> تحصل على خدمات رشق مجانية!"
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, msg, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "collect_points_info")
def collect_points_info_callback(call):
    user_id = call.from_user.id
    balance, spent, points, referrals_count = get_user_points_data(user_id)
    
    bot_username = bot.get_me().username
    ref_link = f"https://t.me/{bot_username}?start={user_id}"
    
    points_value_usd = (points // 50) * 0.01

    caption_text = (
        f"🎯 <b>قسم تجميع النقاط والأرباح المجانية:</b>\n\n"
        f"✨ ════════════════════ ✨\n"
        f"🌟 <b>عدد نقاطك الحالي:</b> <code>{points}</code> نقطة\n"
        f"👥 <b>عدد مشاركاتك للرابط (المسجلين عبرك):</b> <code>{referrals_count}</code> شخص\n"
        f"💵 <b>القيمة المتاحة للتحويل الآن:</b> <code>${points_value_usd:.2f}</code>\n"
        f"✨ ════════════════════ ✨\n\n"
        f"📌 <b>شروط ونظام تجميع النقاط:</b>\n"
        f"• عند مشاركتك للرابط أدناه لكل شخص يدخل البوت عن طريقك تحصل على <b>(2) نقاط</b>.\n\n"
        f"• لكل <b>50 نقطة</b> تجمعها يمكنك تحويلها إلى <b>0.01$ (سنت واحد)</b> أو استخدامها لتمويل قناتك (50 عضو لكل 50 نقطة)!\n\n"
        f"🔗 <b>رابط الدعوة الخاص بك (ثابت ومباشر):</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"📢 <i>قم بنسخ الرابط وأرسله لأصدقائك وفي المجموعات لتبدأ بتجميع النقاط فوراً!</i>"
    )
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🔄 تحويل نقاطي الآن", callback_data="convert_my_points"),
        types.InlineKeyboardButton("🔄 تحديث النقاط", callback_data="collect_points_info"),
        types.InlineKeyboardButton("🔙 الصفحة الرئيسية", callback_data="back_to_main")
    )
    
    try:
        bot.edit_message_text(caption_text, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=markup, disable_web_page_preview=True)
    except Exception:
        bot.answer_callback_query(call.id, "✅ تم تحديث قائمة نقاطك!")

@bot.callback_query_handler(func=lambda call: call.data == "convert_my_points")
def convert_my_points_menu(call):
    user_id = call.from_user.id
    _, _, points, _ = get_user_points_data(user_id)
    
    text_msg = (
        f"🔄 <b>خيارات تحويل النقاط:</b>\n\n"
        f"🌟 <b>عدد نقاطك الحالي:</b> <code>{points}</code> نقطة\n\n"
        f"👇 يرجى اختيار الميزة المراد تحويل نقاطك إليها من الأزرار أدناه:"
    )
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📢 تحويل لـ تمويل قناتي", callback_data="promo_channel_points"),
        types.InlineKeyboardButton("💵 تحويل النقاط إلى (فلوس)", callback_data="do_convert_points_money"),
        types.InlineKeyboardButton("🔙 الصفحة الرئيسية", callback_data="back_to_main")
    )
    
    try:
        bot.edit_message_text(text_msg, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=markup)
    except Exception:
        bot.send_message(call.message.chat.id, text_msg, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "do_convert_points_money")
def convert_points_to_money_handler(call):
    user_id = call.from_user.id
    
    with conversion_lock:
        conn = sqlite3.connect("store_database.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT points, balance FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        
        if not row:
            bot.answer_callback_query(call.id, "❌ لم يتم العثور على حسابك في قاعدة البيانات!", show_alert=True)
            conn.close()
            return

        current_points = row[0] if row[0] is not None else 0

        if current_points < 50:
            alert_msg = f"⚠️ لديك الان ({current_points}) نقطة فقط!\n\nلا يمكنك تحويل النقاط حالياً، الحد الأدنى للتحويل هو 50 نقطة."
            bot.answer_callback_query(call.id, alert_msg, show_alert=True)
            conn.close()
            return

        convertible_units = current_points // 50
        points_to_deduct = convertible_units * 50
        remaining_points = current_points % 50
        added_money = round(convertible_units * 0.01, 4)

        cursor.execute("""
            UPDATE users 
            SET points = ?, 
                balance = balance + ? 
            WHERE user_id = ?
        """, (remaining_points, added_money, user_id))
        
        conn.commit()
        conn.close()

    success_pop_text = (
        f"✅ تم تحويل نقاطك بنجاح!\n\n"
        f"🔹 تم تحويل: {points_to_deduct} نقطة\n"
        f"💵 المبلغ المضاف لرصيدك: +${added_money:.2f}\n"
        f"🔹 النقاط المسترجعة (المتبقية): {remaining_points} نقطة"
    )
    bot.answer_callback_query(call.id, success_pop_text, show_alert=True)

    def send_pinned_and_delete_money():
        try:
            msg_text = (
                f"🎉 <b>تم تحويل النقاط إلى رصيد بنجاح!</b>\n\n"
                f"💵 <b>المبلغ المضاف:</b> +${added_money:.2f}\n"
                f"🎯 <b>النقاط المحولة:</b> {points_to_deduct}\n"
                f"⏱️ <i>(سوف تختفي هذه الرسالة تلقائياً خلال دقيقة واحدة)</i>"
            )
            sent_msg = bot.send_message(call.message.chat.id, msg_text, parse_mode="HTML")
            try: bot.pin_chat_message(call.message.chat.id, sent_msg.message_id)
            except Exception: pass
            time.sleep(60)
            try: bot.unpin_chat_message(call.message.chat.id, sent_msg.message_id)
            except Exception: pass
            try: bot.delete_message(call.message.chat.id, sent_msg.message_id)
            except Exception: pass
        except Exception as e:
            print(f"Error in money notification thread: {e}")

    t = threading.Thread(target=send_pinned_and_delete_money)
    t.daemon = True
    t.start()

    try: bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception: pass

    send_main_menu(call.message.chat.id, user_id)

@bot.callback_query_handler(func=lambda call: call.data == "promo_channel_points")
def promo_channel_points_handler(call):
    user_id = call.from_user.id
    _, _, points, _ = get_user_points_data(user_id)
    
    if points < 50:
        alert_text = f"⚠️ أقل تمويل للقناة 50 نقطة فما فوق!\nنقاطك الحالية: ({points}) نقطة."
        bot.answer_callback_query(call.id, alert_text, show_alert=True)
        return

    calc_members = (points // 50) * 50
    
    text = (
        f"📢 <b>طلب تمويل قناة عبر النقاط:</b>\n\n"
        f"🌟 <b>نقاطك المتاحة:</b> <code>{points}</code> نقطة\n"
        f"👥 <b>عدد الأعضاء المتاح لك:</b> <code>{calc_members}</code> عضو\n\n"
        f"💡 <i>ملاحظة: كل 50 نقطة تمنحك 50 عضو للقناة.</i>\n\n"
        f"⚠️ <b>تنبيه هام جداً:</b> يرجى رفع البوت مشرف في قناتك وإعطائه صلاحية <b>(إضافة مستخدمين / أعضاء)</b> قبل إرسال الرابط لضمان نجاح التمويل!\n\n"
        f"✍️ <b>أرسل الآن رابط قناتك أو معرفها هنا (مثال: @channel أو رابط القناة):</b>"
    )
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❌ إلغاء", callback_data="back_to_main"))
    
    msg = bot.send_message(call.message.chat.id, text, parse_mode="HTML", reply_markup=markup)
    bot.register_next_step_handler(msg, process_channel_promo_link_step)
    bot.answer_callback_query(call.id)

def process_channel_promo_link_step(message):
    user_id = message.from_user.id
    link = message.text.strip()
    
    if not link or len(link) < 3 or ("t.me/" not in link and not link.startswith("@")):
        bot.send_message(message.chat.id, "❌ رابط أو معرف غير صالح! تم إلغاء الطلب.")
        return

    with conversion_lock:
        conn = sqlite3.connect("store_database.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT points FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        
        if not row or (row[0] or 0) < 50:
            bot.send_message(message.chat.id, "❌ نقاطك غير كافية لطلب تمويل القناة (الحد الأدنى 50 نقطة).")
            conn.close()
            return

        current_points = row[0]
        convertible_units = current_points // 50
        used_points = convertible_units * 50
        members_count = convertible_units * 50
        remaining_points = current_points % 50

        cursor.execute("UPDATE users SET points = ? WHERE user_id = ?", (remaining_points, user_id))
        conn.commit()
        conn.close()

    def notify_user_promo():
        try:
            pop_text = (
                f"✅ <b>تم تسجيل طلب تمويل القناة بنجاح!</b>\n\n"
                f"🔗 <b>القناة:</b> {link}\n"
                f"👥 <b>عدد الأعضاء المطلوب:</b> {members_count} عضو\n"
                f"🎯 <b>النقاط المستعملة:</b> {used_points} نقطة\n\n"
                f"⚠️ <b>تذكر:</b> تأكد من رفع البوت مشرف في قناتك وإعطائه صلاحية إضافة مستخدمين.\n"
                f"⏳ سيتم مراجعة الطلب وبدء التمويل قريباً وسيتم إشعارك فوراً عند بدء التنفيذ!\n\n"
                f"⏱️ <i>(سوف تختفي هذه الرسالة تلقائياً خلال دقيقة واحدة)</i>"
            )
            sent_m = bot.send_message(message.chat.id, pop_text, parse_mode="HTML")
            try: bot.pin_chat_message(message.chat.id, sent_m.message_id)
            except Exception: pass
            time.sleep(60)
            try: bot.unpin_chat_message(message.chat.id, sent_m.message_id)
            except Exception: pass
            try: bot.delete_message(message.chat.id, sent_m.message_id)
            except Exception: pass
        except Exception as e:
            print(f"Error in notify_user_promo thread: {e}")

    t_user = threading.Thread(target=notify_user_promo)
    t_user.daemon = True
    t_user.start()

    admin_text = (
        f"🚨 <b>هنالك طلب تمويل جديد للقناة!</b>\n\n"
        f"👤 <b>آيدي المستخدم:</b> <code>{user_id}</code>\n"
        f"🔗 <b>رابط/معرف القناة:</b> <code>{link}</code>\n"
        f"🎯 <b>عدد النقاط الخصومة:</b> <code>{used_points}</code> نقطة\n"
        f"👥 <b>عدد الأعضاء المطلوب:</b> <code>{members_count}</code> عضو"
    )
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ قبول الطلب", callback_data=f"app_promo_{user_id}_{members_count}_{used_points}"),
        types.InlineKeyboardButton("❌ رفض الطلب", callback_data=f"rej_promo_{user_id}_{used_points}")
    )
    try:
        bot.send_message(ADMIN_ID, admin_text, parse_mode="HTML", reply_markup=markup)
    except Exception as e:
        print(f"Admin promo notify error: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("app_promo_"))
def handle_approve_promo(call):
    if call.from_user.id != ADMIN_ID: return
    parts = call.data.split("_")
    target_uid = int(parts[2])
    members_count = int(parts[3])
    
    bot.answer_callback_query(call.id, "✅ تم قبول طلب التمويل وبدء الرشقة!", show_alert=True)
    bot.edit_message_text(f"{call.message.text}\n\n<b>✅ [تم قبول الطلب وجاري تمويل القناة الآن]</b>", chat_id=ADMIN_ID, message_id=call.message.message_id, parse_mode="HTML")
    
    def notify_target_user_approval():
        try:
            user_msg = (
                f"🚀 <b>سيتم بدء الرشقة، سيتم تمويل قناتك الآن!</b>\n\n"
                f"👥 تم قبول طلب إضافة (<b>{members_count}</b>) عضو إلى قناتك بنجاح.\n\n"
                f"⏱️ <i>(سوف تختفي هذه الرسالة تلقائياً خلال دقيقة واحدة)</i>"
            )
            sent_m = bot.send_message(target_uid, user_msg, parse_mode="HTML")
            try: bot.pin_chat_message(target_uid, sent_m.message_id)
            except Exception: pass
            time.sleep(60)
            try: bot.unpin_chat_message(target_uid, sent_m.message_id)
            except Exception: pass
            try: bot.delete_message(target_uid, sent_m.message_id)
            except Exception: pass
        except Exception as e:
            print(f"Error notifying user on approval: {e}")

    t = threading.Thread(target=notify_target_user_approval)
    t.daemon = True
    t.start()

@bot.callback_query_handler(func=lambda call: call.data.startswith("rej_promo_"))
def handle_reject_promo(call):
    if call.from_user.id != ADMIN_ID: return
    parts = call.data.split("_")
    target_uid = int(parts[2])
    used_points = int(parts[3])
    
    conn = sqlite3.connect("store_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (used_points, target_uid))
    conn.commit()
    conn.close()
    
    bot.answer_callback_query(call.id, "❌ تم رفض الطلب وإعادة النقاط للمستخدم.", show_alert=True)
    bot.edit_message_text(f"{call.message.text}\n\n<b>❌ [تم رفض الطلب وإعادة النقاط إلى الزبون]</b>", chat_id=ADMIN_ID, message_id=call.message.message_id, parse_mode="HTML")

def check_account_status(link):
    link_clean = link.strip().rstrip('/')
    if "instagram.com" not in link_clean.lower() and "instagr.am" not in link_clean.lower():
        return True, "عام"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9,ar;q=0.8"
    }
    
    try:
        req = requests.get(link_clean, headers=headers, timeout=8, allow_redirects=True)
        if req.status_code == 200:
            html = req.text.lower()
            if '"is_private":true' in html or 'this account is private' in html or 'حساب خاص' in html or 'private account' in html:
                return False, "الحساب خاص (Private)"
        elif req.status_code == 404:
            return False, "الرابط غير صالح أو غير موجود"
    except Exception as e:
        print(f"Check status exception: {e}")

    if "/private/" in link_clean.lower():
        return False, "الحساب خاص (Private)"

    return True, "عام"

# ==================== معالجة الروابط المرسلة (الرشق التلقائي حصرياً للمشتركين / الأدمن، وإلغاء الرد العشوائي) ====================

@bot.message_handler(func=lambda message: bool(message.text and ("instagram.com" in message.text.lower() or "instagr.am" in message.text.lower())))
def handle_instagram_link(message):
    user_id = message.from_user.id
    
    # التأكد ما إذا كان المستخدم أدمن أو مشترك رسمي في باقة الرشق التلقائي
    is_sub, _ = check_user_subscription(user_id, "instagram")
    if user_id != ADMIN_ID and not is_sub:
        # إذا كان مستخدماً عشوائياً أرسل الرابط بدون طلب خدمة، فلن يرد البوت نهائياً (تجاهل تام صامت)
        return

    link = message.text.strip()
    
    is_public, reason = check_account_status(link)
    if not is_public:
        bot.reply_to(message, f"⚠️ <b>تنبيه هام للغاية!</b>\n\nملاحظه / اغلق ميزه تميز للمراجعه اذا لم تغلقها ف لا يمكن اصلاح طلبك ويعتبر مكتمل ولا يمكن تعويض طلبك ، يجب ان يكون الحساب عام\n\n📌 <b>سبب الرفض:</b> {reason}\nيرجى تحويل حسابك ليكون عاماً ثم إعادة المحاولة.", parse_mode="HTML")
        return

    bot.reply_to(message, "🚀 <b>تم استلام رابط الإنستغرام بنجاح! جاري بدء عملية الرشق التلقائي للخدمة 3396...</b>", parse_mode="HTML")
    
    t = threading.Thread(target=process_free_boost_for_ig_link, args=(user_id, message.chat.id, link))
    t.daemon = True
    t.start()

def process_free_boost_for_ig_link(user_id, chat_id, link):
    status_msg = None
    try:
        initial_text = (
            f"⏳ <b>جاري بدء عملية الرشق التلقائي لإنستغرام عبر الآبيات الـ 5...</b>\n\n"
            f"🔗 <b>الرابط:</b> {link}\n"
            f"🚀 <b>الطلبات الناجحة المؤكدة حتى الآن:</b> <code>0/40</code>"
        )
        status_msg = bot.send_message(chat_id, initial_text, parse_mode="HTML")
    except Exception as e:
        print(f"Error sending IG start message: {e}")

    target_srv = "3396"
    success_count = 0
    target_successes = 40
    fixed_quantity = 50
    attempts = 0

    while success_count < target_successes:
        api_index = attempts % len(FREE_API_URLS)
        url = FREE_API_URLS[api_index]
        key = FREE_API_KEYS[api_index]
        attempts += 1

        payload = {
            "key": key,
            "action": "add",
            "service": target_srv,
            "link": link,
            "quantity": fixed_quantity
        }

        try:
            response = requests.post(url, data=payload, timeout=12)
            res = response.json() if response.status_code == 200 else {}
            
            if isinstance(res, dict) and "order" in res and res["order"] and "error" not in res:
                order_id_from_site = res["order"]
                success_count += 1
                if status_msg:
                    try:
                        update_text = (
                            f"🚀 <b>جاري إرسال طلبات الرشق لإنستغرام (الخدمة 3396)...</b>\n\n"
                            f"🔗 <b>الرابط:</b> {link}\n"
                            f"✅ <b>الطلبات المقبولة بالموقع:</b> <code>{success_count}/{target_successes}</code>\n"
                            f"🆔 <b>رقم أحدث طلب:</b> <code>{order_id_from_site}</code>"
                        )
                        bot.edit_message_text(update_text, chat_id=chat_id, message_id=status_msg.message_id, parse_mode="HTML")
                    except Exception:
                        pass
            else:
                error_reason = res.get("error", f"رمز الاستجابة: {response.status_code}") if isinstance(res, dict) else "استجابة غير صالحة"
                if status_msg:
                    try:
                        update_text = (
                            f"⚠️ <b>الموقع رفض الطلب وسيعيد المحاولة:</b> {error_reason}\n\n"
                            f"🔗 <b>الرابط:</b> {link}\n"
                            f"📊 <b>العدد الناجح الفعلي:</b> <code>{success_count}/{target_successes}</code>"
                        )
                        bot.edit_message_text(update_text, chat_id=chat_id, message_id=status_msg.message_id, parse_mode="HTML")
                    except Exception:
                        pass

        except Exception as e:
            if status_msg:
                try:
                    update_text = (
                        f"❌ <b>خطأ اتصال بالسيرفر:</b> {e}\n\n"
                        f"🔗 <b>الرابط:</b> {link}\n"
                        f"📊 <b>العدد الناجح الفعلي:</b> <code>{success_count}/{target_successes}</code>"
                    )
                    bot.edit_message_text(update_text, chat_id=chat_id, message_id=status_msg.message_id, parse_mode="HTML")
                except Exception:
                    pass

        time.sleep(30)

    if status_msg:
        try:
            final_text = (
                f"🎉 <b>تم توقف الرشق تلقائياً للرابط بعد اكتمال (40) طلب بنجاح!</b>\n\n"
                f"🔗 <b>الرابط:</b> {link}\n"
                f"✅ <b>إجمالي الطلبات المقبولة:</b> <code>{success_count}/{target_successes}</code>\n"
                f"❤️ <b>إجمالي التفاعلات المرسلة:</b> <code>{success_count * fixed_quantity}</code>"
            )
            bot.edit_message_text(final_text, chat_id=chat_id, message_id=status_msg.message_id, parse_mode="HTML")
        except Exception:
            pass

@bot.callback_query_handler(func=lambda call: call.data == "promo_packages")
def promo_packages(call):
    text = "💼 <b>بقات الترويج (البيجات):</b>\n\nنقدم لك أفضل باقات الترويج المخصصة لصفحات السوشيال ميديا لزيادة التفاعل الحقيقي والانتشار الواسع.\n\nتواصل مع الدعم الفني لااختيار الباقة المناسبة."
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📩 مراسلة الدعم", url=get_admin_link()))
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
    bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "discounts_packages")
def discounts_packages(call):
    text = "🎟️ <b>بكجات وخصومات حصرية:</b>\n\nاستفد من العروض الأسبوعية والخصومات الكبرى على جميع خدمات الرشق والتليجرام والإنستغرام.\n\nتابع القناة الرسمية للبوت دائماً لمعرفة الكوبونات الجديدة!"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
    bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "become_agent")
def become_agent(call):
    text = (
        "🤝 <b>برنامج الوكلاء والتجار:</b>\n\n"
        "تتيح لك هذه الميزة الحصول على صلاحيات خاصة وأسعار مخفضة جداً لتكون تاجراً معتمداً.\n"
        "💵 <b>سعر الاشتراك الشهري:</b> <code>25$</code>\n\n"
        "اضغط على زر (فهمت وأريد الاشتراك) أدناه للمتابعة."
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ فهمت وأريد الاشتراك", callback_data="confirm_agent_sub"))
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
    bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "confirm_agent_sub")
def confirm_agent_sub(call):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📩 راسل الإدارة للتقدم في طلبك", url=get_admin_link()))
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
    bot.edit_message_text("📌 <b>يرجى مراسلة الإدارة مباشرة عبر الزر أدناه لإتمام اشتراك الوكيل ودفع الرسوم:</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "funded_support")
def show_funded_support(call):
    all_services = fetch_api_services() + get_custom_services()
    keywords = ["دعم ممول", "ممول", "عراقيين", "عرب", "عراقي"]
    matched_services = [s for s in all_services if any(k in f"{str(s.get('name','')).lower()} {str(s.get('category','')).lower()}" for k in keywords)]

    if not matched_services:
        bot.answer_callback_query(call.id, "❌ لا توجد خدمات دعم ممول متاحة حالياً.", show_alert=True)
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    for s in matched_services[:25]:
        sname = clean_forbidden_text(strip_html(s.get('name')))
        markup.add(types.InlineKeyboardButton(f"🇮🇶 {sname} - (${s.get('rate')})", callback_data=f"info_{s.get('service')}"))
    markup.add(types.InlineKeyboardButton("🔙 الصفحة الرئيسية", callback_data="back_to_main"))
    bot.edit_message_text("🇮🇶 <b>خدمات الدعم الممول الحقيقي:</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "special_offers")
def show_special_offers(call):
    all_services = fetch_api_services() + get_custom_services()
    keywords = ["ارخص الخدمات", "ارخص الاسعار", "أرخص الخدمات", "أرخص الأسعار", "ارخص", "أرخص", "عروض"]
    matched_services = [s for s in all_services if any(k in f"{str(s.get('name','')).lower()} {str(s.get('category','')).lower()}" for k in keywords)]

    if not matched_services:
        matched_services = sorted(all_services, key=lambda x: float(x.get("rate", 999)))[:20]

    markup = types.InlineKeyboardMarkup(row_width=1)
    for s in matched_services[:25]:
        sname = clean_forbidden_text(strip_html(s.get('name')))
        markup.add(types.InlineKeyboardButton(f"🔥 {sname} - (${s.get('rate')})", callback_data=f"info_{s.get('service')}"))
    markup.add(types.InlineKeyboardButton("🔙 الصفحة الرئيسية", callback_data="back_to_main"))
    bot.edit_message_text("🔥 <b>العروض الخاصة والأرخص:</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "main_services")
def show_platforms(call):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btns = [types.InlineKeyboardButton(strip_html(name), callback_data=f"plat_{code}") for name, code in get_all_platforms() if get_setting(f"plat_{code}", 1) == 1]
    if not btns:
        bot.answer_callback_query(call.id, "❌ جميع المنصات معطلة حالياً.", show_alert=True)
        return
    markup.add(*btns)
    markup.add(types.InlineKeyboardButton("🔙 الصفحة الرئيسية", callback_data="back_to_main"))
    bot.edit_message_text("👇 <b>اختر المنصة:</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("plat_"))
def show_service_types(call):
    platform = call.data.split("_")[1]
    markup = types.InlineKeyboardMarkup(row_width=2)
    btns = [types.InlineKeyboardButton(strip_html(name), callback_data=f"type_{platform}_{stype}") for name, stype in get_all_service_types() if get_setting(f"type_{platform}_{stype}", 1) == 1]
    if not btns:
        bot.answer_callback_query(call.id, "❌ أقسام هذه المنصة معطلة.", show_alert=True)
        return
    markup.add(*btns)
    markup.add(types.InlineKeyboardButton("🔙 رجوع للمنصات", callback_data="main_services"))
    bot.edit_message_text("👇 <b>اختر نوع الخدمة:</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("type_") or call.data.startswith("srvpage_"))
def list_filtered_services(call):
    parts = call.data.split("_")
    if call.data.startswith("type_"):
        platform = parts[1]
        stype = parts[2]
        page = 0
    else:
        platform = parts[1]
        stype = parts[2]
        page = int(parts[3])

    all_services = fetch_api_services() + get_custom_services(platform, stype)
    plat_keys = PLATFORM_KEYWORDS.get(platform, [platform])
    type_keys = TYPE_KEYWORDS.get(stype, [stype])

    matched_services = []
    for s in all_services:
        full_text = f"{str(s.get('name','')).lower()} {str(s.get('category','')).lower()}"
        if any(k in full_text for k in plat_keys) and any(k in full_text for k in type_keys):
            matched_services.append(s)

    if not matched_services:
        bot.answer_callback_query(call.id, "❌ لا توجد خدمات متاحة لهذا القسم.", show_alert=True)
        return

    limit = 10
    start_idx = page * limit
    end_idx = start_idx + limit
    page_services = matched_services[start_idx:end_idx]

    markup = types.InlineKeyboardMarkup(row_width=1)
    for s in page_services:
        sname = clean_forbidden_text(strip_html(s.get('name')))
        markup.add(types.InlineKeyboardButton(f"{sname} - (${s.get('rate')})", callback_data=f"info_{s.get('service')}"))

    nav_btns = []
    if page > 0:
        nav_btns.append(types.InlineKeyboardButton("⬅️ السابق", callback_data=f"srvpage_{platform}_{stype}_{page-1}"))
    if end_idx < len(matched_services):
        nav_btns.append(types.InlineKeyboardButton("التالي ➡️", callback_data=f"srvpage_{platform}_{stype}_{page+1}"))

    if nav_btns:
        markup.row(*nav_btns)

    markup.add(types.InlineKeyboardButton("🔙 رجوع الأقسام", callback_data=f"plat_{platform}"))
    
    total_pages = (len(matched_services) + limit - 1) // limit
    bot.edit_message_text(f"📋 <b>الخدمات المتاحة (الصفحة {page + 1} من {total_pages}):</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "free_services")
def show_free_services(call):
    all_services = fetch_api_services(use_free_pool=True) + get_custom_services()
    free_services = []
    for s in all_services:
        try: rate = float(s.get("rate", 999))
        except Exception: rate = 999.0
        name_cat = f"{str(s.get('name','')).lower()} {str(s.get('category','')).lower()}"
        if rate == 0.0 or "مجاني" in name_cat or "free" in name_cat:
            free_services.append(s)

    if not free_services:
        bot.answer_callback_query(call.id, "🎁 لا توجد خدمات مجانية حالياً.", show_alert=True)
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    for s in free_services[:20]:
        sname = clean_forbidden_text(strip_html(s.get('name')))
        markup.add(types.InlineKeyboardButton(f"🎁 {sname} - (${s.get('rate')})", callback_data=f"info_{s.get('service')}"))
    markup.add(types.InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="back_to_main"))
    bot.edit_message_text("🎁 <b>الخدمات المجانية المتاحة:</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("info_"))
def show_service_info(call):
    service_id = call.data.split("_")[1]
    all_services = fetch_api_services() + get_custom_services()
    selected_service = next((s for s in all_services if str(s.get("service")) == str(service_id)), None)
    
    if not selected_service:
        bot.answer_callback_query(call.id, "❌ الخدمة غير متاحة.", show_alert=True)
        return

    clean_name = clean_forbidden_text(selected_service.get('name'))
    desc = clean_forbidden_text(selected_service.get("desc", selected_service.get("description", "لا يوجد وصف متوفر.")))
    
    required_note = "\n\n⚠️ <b>ملاحظه / اغلق ميزه تميز للمراجعه اذا لم تغلقها ف لا يمكن اصلاح طلبك ويعتبر مكتمل ولا يمكن تعويض طلبك ، يجب ان يكون الحساب عام</b>"

    text_info = (
        f"📌 <b>اسم الخدمة:</b> {clean_name}\n"
        f"💵 <b>السعر لكل 1000:</b> <code>${selected_service.get('rate')}</code>\n"
        f"📉 <b>الحد الأدنى:</b> <code>{selected_service.get('min')}</code>\n"
        f"📈 <b>الحد الأقصى:</b> <code>{selected_service.get('max')}</code>\n\n"
        f"📝 <b>الوصف:</b>\n{desc}{required_note}"
    )

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🛒 شراء الآن", callback_data=f"buy_{service_id}"))
    markup.add(types.InlineKeyboardButton("❌ إلغاء العملية", callback_data="back_to_main"))
    markup.add(types.InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="back_to_main"))
    bot.edit_message_text(text_info, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def start_buy_process(call):
    service_id = call.data.split("_")[1]
    all_services = fetch_api_services() + get_custom_services()
    selected_service = next((s for s in all_services if str(s.get("service")) == str(service_id)), None)
    
    if not selected_service:
        bot.answer_callback_query(call.id, "❌ الخدمة غير متاحة.")
        return

    user_steps[call.from_user.id] = {"service": selected_service}
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❌ إلغاء الطلب", callback_data="back_to_main"))
    msg = bot.send_message(call.message.chat.id, "🔗 <b>يرجى إرسال الرابط المطلوب:</b>", parse_mode="HTML", reply_markup=markup)
    bot.register_next_step_handler(msg, process_link_step)

def process_link_step(message):
    user_id = message.from_user.id
    link = message.text.strip()
    if not link.startswith("http"):
        bot.send_message(message.chat.id, "❌ الرابط غير صالح، يرجى إرسال رابط يحتوي http/https.")
        return

    if "instagram.com" in link.lower() or "instagr.am" in link.lower():
        is_public, reason = check_account_status(link)
        if not is_public:
            warning_msg = (
                f"⚠️ <b>تنبيه هام جداً: حسابك خاص ({reason})!</b>\n\n"
                f"ملاحظه / اغلق ميزه تميز للمراجعه اذا لم تغلقها ف لا يمكن اصلاح طلبك ويعتبر مكتمل ولا يمكن تعويض طلبك ، يجب ان يكون الحساب عام.\n\n"
                f"يابا حسابك خاص وتجنباً لحدوث الأخطاء وعدم تعويض الطلب، روح حول حسابك وسويه عام وارجع اطلب الخدمة من جديد!"
            )
            bot.send_message(message.chat.id, warning_msg, parse_mode="HTML")
            return

    user_steps[user_id]["link"] = link
    s_info = user_steps[user_id]["service"]
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❌ إلغاء الطلب", callback_data="back_to_main"))
    msg = bot.send_message(
        message.chat.id,
        f"🔢 <b>أدخل الكمية المطلوبة:</b>\n📌 أدنى: <code>{s_info.get('min')}</code> | أقصى: <code>{s_info.get('max')}</code>",
        parse_mode="HTML",
        reply_markup=markup
    )
    bot.register_next_step_handler(msg, process_quantity_step)

def process_quantity_step(message):
    user_id = message.from_user.id
    try:
        quantity = int(message.text.strip())
        if quantity <= 0: raise ValueError()
    except ValueError:
        bot.send_message(message.chat.id, "❌ يرجى إدخال رقم صحيح أكبر من الصفر.")
        return

    if user_id not in user_steps or "service" not in user_steps[user_id] or "link" not in user_steps[user_id]:
        bot.send_message(message.chat.id, "❌ حدث خطأ في البيانات، يرجى إعادة محاولة الطلب.")
        return

    s_info = user_steps[user_id]["service"]
    min_q, max_q = int(s_info.get("min", 1)), int(s_info.get("max", 100000))
    try:
        rate = float(s_info.get("rate", 0))
    except Exception:
        rate = 0.0

    if quantity < min_q or quantity > max_q:
        bot.send_message(message.chat.id, f"❌ الكمية خارج النطاق المسموح ({min_q} - {max_q}).")
        return

    total_cost = round((quantity / 1000.0) * rate, 4)

    with conversion_lock:
        balance, _ = get_user_data(user_id)
        if balance < total_cost and rate > 0:
            bot.send_message(message.chat.id, f"❌ <b>رصيدك غير كافٍ!</b>\nتكلفة الطلب: <code>${total_cost:.3f}</code>\nرصيدك الحالي: <code>${balance:.3f}</code>", parse_mode="HTML")
            return

    link = user_steps[user_id]["link"]
    is_free = (total_cost == 0.0 or rate == 0.0)

    payload = {
        "action": "add",
        "service": s_info.get("service"),
        "link": link,
        "quantity": quantity
    }
    
    progress_seconds = random.randint(15, 25) if is_free else 10
    send_animated_progress(message.chat.id, progress_seconds, "جاري التنفيذ...")

    try:
        res = send_api_order_with_failover(payload, is_free=is_free)
        if "order" in res and res["order"] and "error" not in res:
            order_id = res["order"]
            
            if total_cost > 0:
                with conversion_lock:
                    update_user_balance_spent(user_id, total_cost)
            
            warranty_days = 365 if "ضمان" in str(s_info.get("name","")) else 0
            warranty_str = "ضمان لمدة سنة من الآن" if warranty_days > 0 else ""

            image_path, receipt_code = generate_invoice_image(
                order_id=order_id,
                user_id=user_id,
                service_name=s_info.get("name"),
                quantity=quantity,
                total_cost=total_cost,
                rate_val=rate,
                warranty_text=warranty_str
            )

            save_order(order_id, user_id, s_info.get("name"), link, quantity, total_cost, warranty_days=warranty_days, receipt_code=receipt_code)

            try:
                prediction_text = ""
                sname_lower = str(s_info.get("name","")).lower()
                if "لايكات" in sname_lower or "likes" in sname_lower:
                    prediction_text = f"📊 <b>فحص الحساب:</b> سيصبح عدد لايكات منشورك الحالي مضافاً إليه {quantity:,} لايك."
                elif "متابعين" in sname_lower or "followers" in sname_lower:
                    prediction_text = f"📊 <b>فحص الحساب:</b> سيصبح عدد متابعيك مضافاً إليه {quantity:,} متابع."
                elif "مشاهدات" in sname_lower or "views" in sname_lower:
                    prediction_text = f"📊 <b>فحص الحساب:</b> ستصبح مشاهدات منشورك مضافة بـ {quantity:,} مشاهدة."

                caption = f"✅ <b>تم إرسال طلبك بنجاح وإصدار الفاتورة الرسمية!</b>\n{prediction_text}"
                if warranty_str:
                    caption += f"\n🛡️ <b>هذه الخدمة مشمولة بـ:</b> {warranty_str}"

                with open(image_path, 'rb') as photo:
                    bot.send_photo(
                        chat_id=message.chat.id,
                        photo=photo,
                        caption=caption,
                        parse_mode="HTML"
                    )
                
                if os.path.exists(image_path):
                    os.remove(image_path)
                    
            except Exception as e_img:
                print(f"Error generating invoice image: {e_img}")
                bot.send_message(
                    message.chat.id,
                    "✅ <b>تم إرسال طلبك بنجاح!</b>",
                    parse_mode="HTML"
                )

            broadcast_order_to_channel(order_id, s_info.get("name"), quantity, total_cost, user_id, warranty_str)
            notify_admin_new_order(order_id, user_id, s_info.get("name"), quantity, total_cost)

            user_orders_cnt = get_user_orders_count(user_id)
            target_count = get_setting("reward_target_count", 50)
            reward_enabled = get_setting("reward_enabled", 0)

            if reward_enabled == 1 and target_count > 0 and (user_orders_cnt % target_count == 0):
                try:
                    bot.send_message(
                        user_id,
                        f"🎉 <b>تهانينا! لقد أكملت {user_orders_cnt} طلب بنجاح!</b>\n🎁 لقد وصلت للحد المطلوب وتستحق الهدية!",
                        parse_mode="HTML"
                    )
                except Exception: pass
                notify_admin_reward_winner(user_id, page=0)

        else:
            bot.send_message(message.chat.id, f"❌ فشل الطلب: {res.get('error', 'خطأ غير معروف أو لم يتم إسناد طلب جديد')}")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطأ أثناء الاتصال بالموقع: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "my_orders")
def show_my_orders(call):
    user_id = call.from_user.id
    orders = get_user_orders_list(user_id, offset=0, limit=10)
    if not orders:
        bot.answer_callback_query(call.id, "❌ لا توجد لديك طلبات سابقة.", show_alert=True)
        return
    
    text = "📦 <b>قائمة طلباتك الأخيرة:</b>\n\n"
    for o in orders:
        oid, sname, qty, created_at, price = o
        clean_name = clean_forbidden_text(sname)
        price_txt = "مجاني" if price == 0 else f"${price:.3f}"
        text += (
            f"🔹 <b>رقم الطلب:</b> <code>{oid}</code>\n"
            f"🏷️ <b>الخدمة:</b> {clean_name}\n"
            f"🔢 <b>الكمية:</b> {qty:,}\n"
            f"💰 <b>السعر:</b> {price_txt}\n"
            f"📅 <b>التاريخ:</b> <code>{created_at}</code>\n"
            f"✨ ────────────────── ✨\n"
        )
        
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 الصفحة الرئيسية", callback_data="back_to_main"))
    bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "add_funds")
def add_funds_callback(call):
    text = (
        "💳 <b>شحن الرصيد:</b>\n\n"
        "لإضافة رصيد إلى حسابك، يرجى التواصل مع الدعم الفني والإدارة مباشرة عبر الزر أدناه."
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📩 مراسلة الدعم لشحن الرصيد", url=get_admin_link()))
    markup.add(types.InlineKeyboardButton("🔙 الصفحة الرئيسية", callback_data="back_to_main"))
    bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=markup)

def notify_admin_new_order(order_id, user_id, service_name, quantity, price):
    is_free = (price == 0.0)
    service_type_tag = "(الخدمة مجانية)" if is_free else "(خدمة مدفوعة)"
    price_text = "$0.000" if is_free else f"${price:.3f}"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    clean_sname = clean_forbidden_text(service_name)

    admin_msg = (
        f"📥 <b>طلب جديد وارد من البوت</b>\n"
        f"<b>{service_type_tag}</b>\n\n"
        f"💰 <b>السعر:</b> <code>{price_text}</code>\n"
        f"🏷️ <b>اسم الخدمة:</b> {clean_sname}\n"
        f"🔢 <b>الكمية:</b> {quantity}\n"
        f"👤 <b>آيدي الزبون:</b> <code>{user_id}</code>\n"
        f"📅 <b>التاريخ:</b> <code>{now_str}</code>"
    )

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🚫 حظر الطلب", callback_data=f"block_order_{order_id}_{user_id}"))

    try:
        bot.send_message(ADMIN_ID, admin_msg, parse_mode="HTML", reply_markup=markup)
    except Exception as e:
        print(f"Admin notify error: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("block_order_"))
def handle_block_order(call):
    if call.from_user.id != ADMIN_ID: return
    parts = call.data.split("_")
    order_id, user_id = parts[2], int(parts[3])

    conn = sqlite3.connect("store_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET status = 'حظر الطلب ❌', is_blocked = 1 WHERE order_id = ?", (order_id,))
    cursor.execute("SELECT service_name, quantity FROM orders WHERE order_id = ?", (order_id,))
    row = cursor.fetchone()
    conn.commit()
    conn.close()

    sname = clean_forbidden_text(row[0]) if row else "خدمة"
    qty = row[1] if row else 0

    bot.answer_callback_query(call.id, "✅ تم حظر الطلب.", show_alert=True)
    bot.edit_message_text(f"{call.message.text}\n\n<b>❌ [تم حظر الطلب من قبل الأدمن]</b>", chat_id=ADMIN_ID, message_id=call.message.message_id, parse_mode="HTML")

    user_msg = f"❌ <b>تم حظر طلبك!</b>\n📌 <b>الخدمة:</b> {sname}\n🔢 <b>الكمية:</b> {qty}"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📩 مراسلة المطور", url=get_admin_link()))
    try: bot.send_message(user_id, user_msg, parse_mode="HTML", reply_markup=markup)
    except Exception: pass

def notify_admin_reward_winner(user_id, page=0):
    total_orders = get_user_orders_count(user_id)
    limit = 10
    offset = page * limit
    orders = get_user_orders_list(user_id, offset, limit)

    orders_text = "".join([f"<b>{idx}.</b> {clean_forbidden_text(o[1])} (<code>${o[4]:.2f}</code>) - <code>{o[3]}</code>\n" for idx, o in enumerate(orders, start=offset + 1)])

    msg_text = (
        f"🎉 <b>زبون فاز بالهدية!</b>\n\n"
        f"👤 <b>آيدي الزبون:</b> <code>{user_id}</code>\n"
        f"📦 <b>إجمالي الطلبات:</b> {total_orders} طلب\n"
        f"📋 <b>تفاصيل الطلبات:</b>\n{orders_text}"
    )

    markup = types.InlineKeyboardMarkup(row_width=1)
    if offset + limit < total_orders:
        markup.add(types.InlineKeyboardButton("➡️ التالي", callback_data=f"rew_page_{user_id}_{page + 1}"))

    markup.add(types.InlineKeyboardButton("🎁 إعطاء الهدية الآن", callback_data=f"give_reward_now_{user_id}"))
    try: bot.send_message(ADMIN_ID, msg_text, parse_mode="HTML", reply_markup=markup)
    except Exception: pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("rew_page_"))
def handle_reward_page(call):
    if call.from_user.id != ADMIN_ID: return
    parts = call.data.split("_")
    notify_admin_reward_winner(int(parts[2]), int(parts[3]))

@bot.callback_query_handler(func=lambda call: call.data.startswith("give_reward_now_"))
def handle_give_reward(call):
    if call.from_user.id != ADMIN_ID: return
    target_uid = int(call.data.split("_")[3])
    reward_type = get_setting_text("reward_type", "money")

    if reward_type == "money":
        val_num = float(get_setting_text("reward_money_amount", "1$").replace("$", ""))
        conn = sqlite3.connect("store_database.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (val_num, target_uid))
        conn.commit()
        conn.close()
        user_msg = f"🎁 <b>تم إضافة هدية رصيد بقيمة <code>${val_num:.2f}</code> لحسابك!</b>"
    else:
        user_msg = "🎁 <b>تم تفعيل خدمة الهدية المجانية لك بنجاح!</b>"

    bot.answer_callback_query(call.id, "✅ تم تسليم الهدية!", show_alert=True)
    bot.edit_message_text(f"{call.message.text}\n\n<b>✅ [تم منح الهدية]</b>", chat_id=ADMIN_ID, message_id=call.message.message_id, parse_mode="HTML")
    try: bot.send_message(target_uid, user_msg, parse_mode="HTML")
    except Exception: pass

@bot.message_handler(commands=['admin'])
def admin_command(message):
    if message.from_user.id == ADMIN_ID: show_admin_menu(message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data == "admin_panel")
def admin_panel_callback(call):
    if call.from_user.id == ADMIN_ID: show_admin_menu(call.message.chat.id, message_id=call.message.message_id)

def show_admin_menu(chat_id, message_id=None):
    reward_enabled = get_setting("reward_enabled", 0)
    rew_icon = "✅" if reward_enabled == 1 else "❌"
    target_count = get_setting("reward_target_count", 50)
    current_discount = get_setting_text("global_discount_cents", "0")

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📥 جلب وصل", callback_data="admin_fetch_receipt"),
        types.InlineKeyboardButton("🌐 تفعيل المنصات", callback_data="admin_toggle_platforms")
    )
    markup.add(
        types.InlineKeyboardButton("🛠️ تفعيل الأقسام", callback_data="admin_toggle_types"),
        types.InlineKeyboardButton("✏️ تعديل أسماء المنصات", callback_data="admin_edit_platforms_menu")
    )
    markup.add(
        types.InlineKeyboardButton("✏️ تعديل أسماء الأقسام", callback_data="admin_edit_types_menu"),
        types.InlineKeyboardButton("📉 تخفيض الأسعار", callback_data="admin_discount_prices")
    )
    markup.add(
        types.InlineKeyboardButton("🔄 ارجع على الأسعار الأصلية", callback_data="admin_reset_prices"),
        types.InlineKeyboardButton(f"🎁 تفعيل الهدية ({rew_icon})", callback_data="admin_toggle_reward")
    )
    markup.add(
        types.InlineKeyboardButton("➕ إضافة خدمة يدوياً", callback_data="admin_add_service_start"),
        types.InlineKeyboardButton("📢 تعيين قناة الطلبات", callback_data="admin_set_channel")
    )
    markup.add(
        types.InlineKeyboardButton("🛡️ تسعير الضمانات", callback_data="admin_warranty_pricing"),
        types.InlineKeyboardButton("⚡ رشق تلقائي مجاني (أدمن)", callback_data="admin_auto_free_boost")
    )
    markup.add(types.InlineKeyboardButton("🔙 الخروج من اللوحة", callback_data="back_to_main"))
    
    text = (
        f"⚙️ <b>لوحة تحكم الأدمن:</b>\n"
        f"• التخفيض الحالي على الأسعار: <code>{current_discount} سنت</code>\n"
        f"• حالة الهدية: {rew_icon}\n"
        f"• الهدف: <code>{target_count}</code> طلب"
    )
    
    if message_id: bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, parse_mode="HTML", reply_markup=markup)
    else: bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "admin_fetch_receipt")
def admin_fetch_receipt_callback(call):
    if call.from_user.id != ADMIN_ID: return
    msg = bot.send_message(
        call.message.chat.id,
        "📥 <b>أرسل رقم الوصل الآن:</b>\n\n(الموجود في أعلى الصورة الفاتورة باللون الأخضر أو رقم الطلب)",
        parse_mode="HTML"
    )
    bot.register_next_step_handler(msg, process_fetch_receipt_step)

def process_fetch_receipt_step(message):
    if message.from_user.id != ADMIN_ID: return
    code_input = message.text.strip()

    conn = sqlite3.connect("store_database.db", check_same_thread=False)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT order_id, user_id, service_name, link, quantity, price, created_at, deleted_at, receipt_code 
        FROM deleted_receipts 
        WHERE receipt_code = ? OR order_id = ?
    """, (code_input, code_input))
    deleted_row = cursor.fetchone()

    if deleted_row:
        oid, uid, sname, link, qty, price, c_at, d_at, r_code = deleted_row
        
        try:
            created_dt = datetime.strptime(c_at, "%Y-%m-%d %H:%M:%S")
            days_passed = (datetime.now() - created_dt).days
        except Exception:
            days_passed = 30

        reply_txt = (
            f"⚠️ <b>هذا الكود هذا الوصل مستخدم من ذا {days_passed} ايام صار له وتم حذفه تلقائياً من قاعدة بيانات</b>\n\n"
            f"📄 <b>تفاصيل الكود والوصل كاملاً ومكملاً:</b>\n"
            f"🆔 <b>رقم الطلب الأصلي:</b> <code>{oid}</code>\n"
            f"🧾 <b>رقم الوصل:</b> <code>{r_code or oid}</code>\n"
            f"👤 <b>آيدي المستخدم:</b> <code>{uid}</code>\n"
            f"🏷️ <b>اسم الخدمة:</b> {clean_forbidden_text(sname)}\n"
            f"🔗 <b>الرابط:</b> <code>{link}</code>\n"
            f"🔢 <b>الكمية:</b> <code>{qty:,}</code>\n"
            f"💰 <b>السعر:</b> <code>${price:.3f}</code>\n"
            f"📅 <b>تاريخ الطلب:</b> <code>{c_at}</code>\n"
            f"🗑️ <b>تاريخ الحذف التلقائي:</b> <code>{d_at}</code>"
        )
        bot.send_message(message.chat.id, reply_txt, parse_mode="HTML")
        conn.close()
        return

    cursor.execute("""
        SELECT order_id, user_id, service_name, link, quantity, price, created_at, receipt_code 
        FROM orders 
        WHERE receipt_code = ? OR order_id = ?
    """, (code_input, code_input))
    row = cursor.fetchone()

    if row:
        oid, uid, sname, link, qty, price, c_at, r_code = row
        try:
            created_dt = datetime.strptime(c_at, "%Y-%m-%d %H:%M:%S")
            days_passed = (datetime.now() - created_dt).days
        except Exception:
            days_passed = 0

        if days_passed >= 30:
            del_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                INSERT OR REPLACE INTO deleted_receipts 
                (order_id, user_id, service_name, link, quantity, price, created_at, deleted_at, receipt_code)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (oid, uid, sname, link, qty, price, c_at, del_at, r_code or oid))
            cursor.execute("DELETE FROM orders WHERE order_id = ?", (oid,))
            conn.commit()

            reply_txt = (
                f"⚠️ <b>هذا الكود هذا الوصل مستخدم من ذا {days_passed} ايام صار له وتم حذفه تلقائياً من قاعدة بيانات</b>\n\n"
                f"📄 <b>تفاصيل الكود والوصل كامل ومكمل:</b>\n"
                f"🆔 <b>رقم الطلب الأصلي:</b> <code>{oid}</code>\n"
                f"🧾 <b>رقم الوصل:</b> <code>{r_code or oid}</code>\n"
                f"👤 <b>آيدي المستخدم:</b> <code>{uid}</code>\n"
                f"🏷️ <b>اسم الخدمة:</b> {clean_forbidden_text(sname)}\n"
                f"🔗 <b>الرابط:</b> <code>{link}</code>\n"
                f"🔢 <b>الكمية:</b> <code>{qty:,}</code>\n"
                f"💰 <b>السعر:</b> <code>${price:.3f}</code>\n"
                f"📅 <b>تاريخ الطلب:</b> <code>{c_at}</code>"
            )
        else:
            reply_txt = (
                f"🟢 <b>تم جلب الوصل بنجاح وهو ضمن الصلاحية ({days_passed} يوم):</b>\n\n"
                f"🆔 <b>رقم الطلب:</b> <code>{oid}</code>\n"
                f"🧾 <b>رقم الوصل (بالأخضر):</b> <code>{r_code or oid}</code>\n"
                f"👤 <b>آيدي الزبون:</b> <code>{uid}</code>\n"
                f"🏷️ <b>الخدمة:</b> {clean_forbidden_text(sname)}\n"
                f"🔗 <b>الرابط:</b> <code>{link}</code>\n"
                f"🔢 <b>الكمية:</b> <code>{qty:,}</code>\n"
                f"💰 <b>السعر:</b> <code>${price:.3f}</code>\n"
                f"📅 <b>التاريخ:</b> <code>{c_at}</code>"
            )

        bot.send_message(message.chat.id, reply_txt, parse_mode="HTML")
    else:
        bot.send_message(message.chat.id, "❌ لم يتم العثور على أي وصل أو كود بهذا الرقم!", parse_mode="HTML")

    conn.close()

@bot.callback_query_handler(func=lambda call: call.data == "admin_discount_prices")
def admin_discount_prices_callback(call):
    if call.from_user.id != ADMIN_ID: return
    msg = bot.send_message(
        call.message.chat.id,
        "📉 <b>أرسل لي كم سنت تريد التخفيض للخدمات المدفوعة:</b>\n\n"
        "💡 <i>مثال:</i> أرسل <code>1</code> لإنقاص سنت واحد (1 سنت) من كل الخدمات، أو <code>2</code> لإنقاص سنتين (2 سنت)، أو <code>5</code> لإنقاص 5 سنتات.",
        parse_mode="HTML"
    )
    bot.register_next_step_handler(msg, save_discount_cents_step)

def save_discount_cents_step(message):
    if message.from_user.id != ADMIN_ID: return
    clean_txt = message.text.strip().replace("سنت", "").strip()
    try:
        val = float(clean_txt)
        if val < 0:
            raise ValueError()
        set_setting_text("global_discount_cents", str(val))
        bot.send_message(message.chat.id, f"✅ <b>تم تطبيق تخفيض بقيمة ({val} سنت) على كافة الأسعار بنجاح!</b>", parse_mode="HTML")
    except Exception:
        bot.send_message(message.chat.id, "❌ رقم غير صالح، تم إلغاء التعديل.")
    show_admin_menu(message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data == "admin_reset_prices")
def admin_reset_prices_callback(call):
    if call.from_user.id != ADMIN_ID: return
    set_setting_text("global_discount_cents", "0")
    bot.answer_callback_query(call.id, "✅ تم إلغاء الخصومات وإرجاع كافة الأسعار إلى قيمتها الأصلية بنجاح!", show_alert=True)
    show_admin_menu(call.message.chat.id, message_id=call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "admin_add_service_start")
def admin_add_service_start(call):
    if call.from_user.id != ADMIN_ID: return
    msg = bot.send_message(call.message.chat.id, "➕ <b>أرسل تفاصيل الخدمة الجديدة بالترتيب:</b>\n\n(منصة, نوع, آيدي الخدمة, الاسم, السعر, أدنى, أقصى, الوصف)", parse_mode="HTML")
    bot.register_next_step_handler(msg, process_add_custom_service_step)

def process_add_custom_service_step(message):
    if message.from_user.id != ADMIN_ID: return
    parts = message.text.split(",")
    if len(parts) < 8:
        bot.send_message(message.chat.id, "❌ الصيغة غير صحيحة. يرجى التأكد من إدخال 8 حقول مفصولة بفاصلة (,).")
        return
    try:
        plat = parts[0].strip()
        stype = parts[1].strip()
        sid = parts[2].strip()
        name = parts[3].strip()
        rate = float(parts[4].strip())
        min_q = int(parts[5].strip())
        max_q = int(parts[6].strip())
        desc = parts[7].strip()

        add_custom_service(plat, stype, sid, name, rate, min_q, max_q, desc)
        bot.send_message(message.chat.id, "✅ <b>تم إضافة الخدمة اليدوية بنجاح!</b>", parse_mode="HTML")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ حدث خطأ أثناء إضافة الخدمة: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "admin_toggle_reward")
def admin_toggle_reward_callback(call):
    if call.from_user.id != ADMIN_ID: return
    current = get_setting("reward_enabled", 0)
    new_val = 0 if current == 1 else 1
    set_setting_text("reward_enabled", str(new_val))
    bot.answer_callback_query(call.id, f"✅ تم تغيير حالة الهدية إلى: {'تفعيل' if new_val == 1 else 'تعطيل'}", show_alert=True)
    show_admin_menu(call.message.chat.id, message_id=call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "admin_set_channel")
def admin_set_channel_callback(call):
    if call.from_user.id != ADMIN_ID: return
    msg = bot.send_message(call.message.chat.id, "📢 <b>أرسل معرف قناة الطلبات الجديد (مثال: @channel):</b>", parse_mode="HTML")
    bot.register_next_step_handler(msg, process_set_channel_step)

def process_set_channel_step(message):
    if message.from_user.id != ADMIN_ID: return
    channel_id = message.text.strip()
    set_setting_text("orders_channel_id", channel_id)
    bot.send_message(message.chat.id, f"✅ <b>تم تعيين قناة الطلبات بنجاح إلى:</b> <code>{channel_id}</code>", parse_mode="HTML")
    show_admin_menu(message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data == "admin_toggle_platforms")
def admin_toggle_platforms_callback(call):
    if call.from_user.id != ADMIN_ID: return
    markup = types.InlineKeyboardMarkup(row_width=2)
    for name, code in PLATFORMS:
        st = get_setting(f"plat_{code}", 1)
        icon = "✅" if st == 1 else "❌"
        markup.add(types.InlineKeyboardButton(f"{strip_html(name)} {icon}", callback_data=f"toggleplat_{code}"))
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel"))
    bot.edit_message_text("🌐 <b>تفعيل/تعطيل المنصات:</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("toggleplat_"))
def handle_toggle_plat(call):
    if call.from_user.id != ADMIN_ID: return
    code = call.data.split("_")[1]
    curr = get_setting(f"plat_{code}", 1)
    new_st = 0 if curr == 1 else 1
    set_setting_text(f"plat_{code}", str(new_st))
    admin_toggle_platforms_callback(call)

@bot.callback_query_handler(func=lambda call: call.data == "admin_toggle_types")
def admin_toggle_types_callback(call):
    if call.from_user.id != ADMIN_ID: return
    markup = types.InlineKeyboardMarkup(row_width=2)
    for name, code in PLATFORMS:
        markup.add(types.InlineKeyboardButton(f"📁 قسم {strip_html(name)}", callback_data=f"toggletypesplat_{code}"))
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel"))
    bot.edit_message_text("🛠️ <b>اختر المنصة لتفعيل أو تعطيل أنواع الخدمات فيها:</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("toggletypesplat_"))
def handle_toggle_types_plat(call):
    if call.from_user.id != ADMIN_ID: return
    code = call.data.split("_")[1]
    markup = types.InlineKeyboardMarkup(row_width=2)
    for name, stype in SERVICE_TYPES:
        st = get_setting(f"type_{code}_{stype}", 1)
        icon = "✅" if st == 1 else "❌"
        markup.add(types.InlineKeyboardButton(f"{strip_html(name)} {icon}", callback_data=f"toggletypestep_{code}_{stype}"))
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_toggle_types"))
    bot.edit_message_text(f"🛠️ <b>تفعيل/تعطيل أنواع الخدمات لمنصة {code}:</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("toggletypestep_"))
def handle_toggle_type_step(call):
    if call.from_user.id != ADMIN_ID: return
    parts = call.data.split("_")
    code, stype = parts[1], parts[2]
    curr = get_setting(f"type_{code}_{stype}", 1)
    new_st = 0 if curr == 1 else 1
    set_setting_text(f"type_{code}_{stype}", str(new_st))
    
    call.data = f"toggletypesplat_{code}"
    handle_toggle_types_plat(call)

@bot.callback_query_handler(func=lambda call: call.data == "admin_edit_platforms_menu")
def admin_edit_platforms_menu(call):
    if call.from_user.id != ADMIN_ID: return
    markup = types.InlineKeyboardMarkup(row_width=2)
    for name, code in get_all_platforms():
        markup.add(types.InlineKeyboardButton(f"✏️ {strip_html(name)}", callback_data=f"editplat_{code}"))
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel"))
    bot.edit_message_text("✏️ <b>اختر المنصة لتعديل اسمها:</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("editplat_"))
def handle_edit_plat_start(call):
    if call.from_user.id != ADMIN_ID: return
    code = call.data.split("_")[1]
    msg = bot.send_message(call.message.chat.id, f"✏️ <b>أرسل الاسم الجديد للمنصة ({code}):</b>", parse_mode="HTML")
    bot.register_next_step_handler(msg, lambda m: save_new_platform_name(m, code))

def save_new_platform_name(message, code):
    if message.from_user.id != ADMIN_ID: return
    new_name = message.text.strip()
    set_setting_text(f"name_plat_{code}", new_name)
    bot.send_message(message.chat.id, f"✅ <b>تم تعديل اسم المنصة بنجاح إلى:</b> {new_name}", parse_mode="HTML")
    show_admin_menu(message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data == "admin_edit_types_menu")
def admin_edit_types_menu(call):
    if call.from_user.id != ADMIN_ID: return
    markup = types.InlineKeyboardMarkup(row_width=2)
    for name, stype in get_all_service_types():
        markup.add(types.InlineKeyboardButton(f"✏️ {strip_html(name)}", callback_data=f"edittype_{stype}"))
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel"))
    bot.edit_message_text("✏️ <b>اختر نوع الخدمة لتعديل اسمها:</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("edittype_"))
def handle_edit_type_start(call):
    if call.from_user.id != ADMIN_ID: return
    stype = call.data.split("_")[1]
    msg = bot.send_message(call.message.chat.id, f"✏️ <b>أرسل الاسم الجديد لنوع الخدمة ({stype}):</b>", parse_mode="HTML")
    bot.register_next_step_handler(msg, lambda m: save_new_type_name(m, stype))

def save_new_type_name(message, stype):
    if message.from_user.id != ADMIN_ID: return
    new_name = message.text.strip()
    set_setting_text(f"name_type_{stype}", new_name)
    bot.send_message(message.chat.id, f"✅ <b>تم تعديل اسم النوع بنجاح إلى:</b> {new_name}", parse_mode="HTML")
    show_admin_menu(message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data == "admin_warranty_pricing")
def admin_warranty_pricing(call):
    if call.from_user.id != ADMIN_ID: return
    bot.answer_callback_query(call.id, "🛡️ نظام الضمانات مفعل تلقائياً للخدمات المشمولة.", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == "admin_auto_free_boost")
def admin_auto_free_boost(call):
    if call.from_user.id != ADMIN_ID: return
    bot.answer_callback_query(call.id, "⚡ نظام الرشق التلقائي يعمل بكفاءة عبر البوابات الـ 5.", show_alert=True)

if __name__ == "__main__":
    print("🤖 البوت يعمل الآن بنجاح...")
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            print(f"Polling error: {e}")
            time.sleep(5)
