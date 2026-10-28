import os
import sys
import json
import time
import io
import html
import threading
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

from image_renderer import render_dashboard_image

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "data.json")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
INDEX_FILE = os.path.join(BASE_DIR, "index.html")
KIOSK_FILE = os.path.join(BASE_DIR, "kiosk.html")

# Percorso predefinito del progetto principale (kindle-fridge-dashboard) per sincronizzazione diretta
PARENT_FRIDGE_DATA = os.path.abspath(os.path.join(BASE_DIR, "..", "kindle-fridge-dashboard", "data.json"))
PARENT_FRIDGE_CONFIG = os.path.abspath(os.path.join(BASE_DIR, "..", "kindle-fridge-dashboard", "config.json"))

data_lock = threading.Lock()

def get_rome_now():
    """Fuso orario Roma (CET/CEST)."""
    try:
        import zoneinfo
        return datetime.now(zoneinfo.ZoneInfo("Europe/Rome"))
    except Exception:
        pass
    now_utc = datetime.now(timezone.utc)
    year = now_utc.year
    march_last = datetime(year, 3, 31, 1, 0, tzinfo=timezone.utc)
    dst_start = march_last - timedelta(days=(march_last.weekday() + 1) % 7)
    oct_last = datetime(year, 10, 31, 1, 0, tzinfo=timezone.utc)
    dst_end = oct_last - timedelta(days=(oct_last.weekday() + 1) % 7)
    tz = timezone(timedelta(hours=2)) if dst_start <= now_utc < dst_end else timezone(timedelta(hours=1))
    return now_utc.astimezone(tz)

def load_config():
    cfg = {
        "port": 8080,
        "shared_data_path": PARENT_FRIDGE_DATA if os.path.exists(PARENT_FRIDGE_DATA) else "",
        "city_name": "Salemi (TP)",
        "weather_lat": 37.818,
        "weather_lon": 12.801,
        "bot_token": "",
        "shared_data_url": "",
        "default_width": 1072,
        "default_height": 1448
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                user_cfg = json.load(f)
                cfg.update(user_cfg)
        except Exception as e:
            print("[Config] Errore lettura config.json:", e)

    # Variabili d'ambiente
    if os.environ.get("PORT"):
        cfg["port"] = int(os.environ.get("PORT"))
    if os.environ.get("SHARED_DATA_PATH"):
        cfg["shared_data_path"] = os.environ.get("SHARED_DATA_PATH")
    if os.environ.get("SHARED_DATA_URL"):
        cfg["shared_data_url"] = os.environ.get("SHARED_DATA_URL")
    if os.environ.get("BOT_TOKEN"):
        cfg["bot_token"] = os.environ.get("BOT_TOKEN")

    return cfg

def get_target_data_file():
    cfg = load_config()
    shared = cfg.get("shared_data_path", "").strip()
    if shared and os.path.exists(shared):
        return shared
    return DATA_FILE

def load_data():
    cfg = load_config()
    shared_url = cfg.get("shared_data_url", "").strip()
    if shared_url:
        try:
            req = urllib.request.Request(shared_url, headers={"User-Agent": "KindleSimpleDashboard/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                rem = json.loads(resp.read().decode("utf-8"))
                return {
                    "notes": rem.get("notes", []),
                    "groceries": rem.get("groceries", [])
                }
        except Exception as e:
            print(f"[Sync URL] Errore fetch da {shared_url}: {e}")

    target_file = get_target_data_file()
    with data_lock:
        if os.path.exists(target_file):
            try:
                with open(target_file, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    d.setdefault("notes", [])
                    d.setdefault("groceries", [])
                    return d
            except Exception as e:
                print(f"[Data] Errore lettura {target_file}:", e)

        # Fallback locale
        return {
            "notes": [
                {"id": 1, "author": "MAMMA", "text": "Promemoria bacheca Kindle sincronizzata!", "time": "10:00"}
            ],
            "groceries": [
                {"id": 1, "text": "Latte fresco", "author": "MAMMA", "done": False},
                {"id": 2, "text": "Caffè macinato", "author": "PAPÀ", "done": False}
            ]
        }

def save_data(data):
    target_file = get_target_data_file()
    with data_lock:
        try:
            # Se stiamo usando il file condiviso di kindle-fridge-dashboard, preserviamo i campi esistenti (tasks, backpack, etc.)
            full_data = {}
            if os.path.exists(target_file):
                try:
                    with open(target_file, "r", encoding="utf-8") as f:
                        full_data = json.load(f)
                except Exception:
                    pass
            full_data.update(data)
            tmp_file = target_file + ".tmp"
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(full_data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_file, target_file)
        except Exception as e:
            print(f"[Data] Errore salvataggio {target_file}:", e)

# --- METEO OPEN-METEO (CACHE 20 MINUTI) ---
WMO_CODES = {
    0: 'SERENO', 1: 'QUASI SERENO', 2: 'POCO NUVOLOSO', 3: 'COPERTO',
    45: 'NEBBIA', 48: 'NEBBIA',
    51: 'PIOVIGGINE', 53: 'PIOVIGGINE', 55: 'PIOVIGGINE',
    61: 'PIOGGIA DEBOLE', 63: 'PIOGGIA', 65: 'FORTE PIOGGIA',
    71: 'NEVE', 73: 'NEVE', 75: 'FORTE NEVE',
    80: 'ROVESCI', 81: 'ROVESCI', 82: 'FORTI ROVESCI',
    95: 'TEMPORALE', 96: 'TEMPORALE', 99: 'TEMPORALE'
}

cached_weather = None
last_weather_time = 0

def get_weather():
    global cached_weather, last_weather_time
    now_ts = time.time()
    if cached_weather and (now_ts - last_weather_time < 1200):
        return cached_weather

    cfg = load_config()
    lat = cfg.get("weather_lat", 37.818)
    lon = cfg.get("weather_lon", 12.801)
    city = cfg.get("city_name", "Salemi (TP)")

    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            "&current=temperature_2m,weather_code&hourly=temperature_2m,weather_code"
            "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max&timezone=Europe%2FRome"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "KindleSimpleDashboard/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            res = json.loads(resp.read().decode("utf-8"))

        curr = res.get("current", {})
        daily = res.get("daily", {})
        hourly = res.get("hourly", {})

        curr_temp = round(curr.get("temperature_2m", 0))
        curr_code = curr.get("weather_code", 0)
        curr_desc = WMO_CODES.get(curr_code, "VARIABILE")
        min_temp = round(daily.get("temperature_2m_min", [0])[0])
        max_temp = round(daily.get("temperature_2m_max", [0])[0])
        rain_prob = daily.get("precipitation_probability_max", [0])[0]

        curr_iso_prefix = curr.get("time", "")[:13]
        h_times = hourly.get("time", [])
        curr_idx = 0
        for idx, ht in enumerate(h_times):
            if ht.startswith(curr_iso_prefix):
                curr_idx = idx
                break

        forecast_slots = []
        for step in [6, 12]:
            target_idx = curr_idx + step
            if target_idx < len(h_times):
                t_str = h_times[target_idx].split("T")[1]
                temp_val = round(hourly["temperature_2m"][target_idx])
                c_val = hourly["weather_code"][target_idx]
                desc_val = WMO_CODES.get(c_val, "Variabile").capitalize()
                forecast_slots.append({"time": t_str, "temp": f"{temp_val}°", "desc": desc_val})

        cached_weather = {
            "city": city,
            "temp": f"{curr_temp}°C",
            "condition": curr_desc,
            "min_max": f"MIN {min_temp}° • MAX {max_temp}°",
            "rain": f"PIOGGIA {rain_prob}%",
            "forecast": forecast_slots
        }
        last_weather_time = now_ts
        return cached_weather
    except Exception as e:
        print("[Meteo] Errore Open-Meteo:", e)
        if cached_weather:
            return cached_weather
        return {
            "city": city,
            "temp": "18°C",
            "condition": "POCO NUVOLOSO",
            "min_max": "MIN 12° • MAX 21°",
            "rain": "PIOGGIA 0%",
            "forecast": [
                {"time": "15:00", "temp": "20°", "desc": "Sereno"},
                {"time": "21:00", "temp": "16°", "desc": "Sereno"}
            ]
        }

# --- STANDALONE TELEGRAM BOT (OPZIONALE) ---
def send_telegram_message(token, chat_id, text):
    if not token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "HTML"}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10):
            pass
    except Exception as e:
        print(f"[Telegram] Errore invio: {e}")

def handle_telegram_message(token, msg):
    chat_id = msg.get("chat", {}).get("id")
    from_user = msg.get("from", {})
    author = from_user.get("first_name", "FAMIGLIA").upper()
    text = (msg.get("text") or "").strip()

    if not text or not chat_id:
        return

    text_lower = text.lower()
    now_time = get_rome_now().strftime("%H:%M")
    data = load_data()

    # Comandi Spesa
    if text_lower.startswith("spesa ") or text_lower.startswith("comprare "):
        items_raw = text[6:] if text_lower.startswith("spesa ") else text[9:]
        clean_items = [i.strip() for i in items_raw.replace(" e ", ",").replace("\n", ",").split(",") if i.strip()]
        if clean_items:
            next_id = max([g.get("id", 0) for g in data.get("groceries", [])] + [0]) + 1
            added = []
            for item in clean_items:
                data.setdefault("groceries", []).insert(0, {
                    "id": next_id,
                    "text": item.capitalize(),
                    "author": author,
                    "done": False
                })
                added.append(item.capitalize())
                next_id += 1
            save_data(data)
            send_telegram_message(token, chat_id, f"🛒 <b>Aggiunto alla spesa:</b>\n• " + "\n• ".join([html.escape(x) for x in added]))
        return

    if text_lower in ["/spesa", "spesa", "cosa manca"]:
        pending = [g["text"] for g in data.get("groceries", []) if not g.get("done")]
        if not pending:
            send_telegram_message(token, chat_id, "🛒 <b>Lista della spesa vuota!</b>")
        else:
            send_telegram_message(token, chat_id, "🛒 <b>Da comprare:</b>\n• " + "\n• ".join([html.escape(x) for x in pending]))
        return

    if text_lower.startswith("/fatto ") or text_lower.startswith("preso "):
        query = text.split(" ", 1)[1].strip().lower()
        matched = None
        for g in data.get("groceries", []):
            if query in g["text"].lower() and not g.get("done"):
                g["done"] = True
                matched = g["text"]
                break
        if matched:
            save_data(data)
            send_telegram_message(token, chat_id, f"✅ Segnato come preso: <b>{html.escape(matched)}</b>")
        else:
            send_telegram_message(token, chat_id, f"❓ Articolo \"{html.escape(query)}\" non trovato.")
        return

    # Comandi Note
    if text_lower in ["/cancellanote", "/svuotanote"]:
        data["notes"] = []
        save_data(data)
        send_telegram_message(token, chat_id, "🗑️ <b>Tutte le note in bacheca sono state cancellate.</b>")
        return

    note_content = text
    if text_lower.startswith("nota ") or text_lower.startswith("promemoria "):
        note_content = text.split(" ", 1)[1].strip()

    next_id = max([n.get("id", 0) for n in data.get("notes", [])] + [0]) + 1
    new_note = {
        "id": next_id,
        "author": author,
        "text": note_content,
        "time": now_time
    }
    data.setdefault("notes", []).insert(0, new_note)
    data["notes"] = data["notes"][:6]
    save_data(data)
    send_telegram_message(token, chat_id, f"📌 <b>Nota appuntata sul Kindle ({html.escape(author)}):</b>\n\"{html.escape(note_content)}\"")

def telegram_poller_thread():
    last_offset = 0
    while True:
        cfg = load_config()
        token = cfg.get("bot_token", "").strip()
        # Se non c'è un bot token dedicato per questa istanza, non fa polling (lascia gestire a kindle-fridge-dashboard)
        if not token:
            time.sleep(5)
            continue

        url = f"https://api.telegram.org/bot{token}/getUpdates?offset={last_offset}&timeout=20"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "KindleSimpleBot/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                if res.get("ok"):
                    for update in res.get("result", []):
                        last_offset = update["update_id"] + 1
                        msg = update.get("message")
                        if msg:
                            handle_telegram_message(token, msg)
        except Exception:
            time.sleep(5)

# --- HTTP REQUEST HANDLER ---
class KindleSimpleHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qparams = urllib.parse.parse_qs(parsed.query)

        # 1. API DATI JSON
        if parsed.path == "/api/data":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            data = load_data()
            weather = get_weather()
            resp = {
                "notes": data.get("notes", []),
                "groceries": data.get("groceries", []),
                "weather": weather,
                "sync_time": datetime.now().strftime("%H:%M:%S"),
                "is_shared": bool(get_target_data_file() == PARENT_FRIDGE_DATA)
            }
            self.wfile.write(json.dumps(resp, ensure_ascii=False).encode("utf-8"))
            return

        # 2. ENDPOINT IMMAGINE DINAMICA PER KINDLE (/screen.png o /screen.bmp)
        if parsed.path in ["/screen.png", "/image.png", "/screen.bmp"]:
            cfg = load_config()
            default_w = cfg.get("default_width", 1072)
            default_h = cfg.get("default_height", 1448)

            width = int(qparams.get("w", [default_w])[0])
            height = int(qparams.get("h", [default_h])[0])

            data = load_data()
            weather = get_weather()

            # Genera immagine in memoria
            img = render_dashboard_image(data, weather, width=width, height=height)
            buf = io.BytesIO()
            is_bmp = parsed.path.endswith(".bmp")
            fmt = "BMP" if is_bmp else "PNG"
            mime = "image/bmp" if is_bmp else "image/png"
            img.save(buf, format=fmt)
            img_bytes = buf.getvalue()

            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(img_bytes)))
            self.end_headers()
            self.wfile.write(img_bytes)
            return

        # 3. INTERFACCIA WEB HTML
        if parsed.path in ["/kiosk", "/kiosk.html"]:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            with open(KIOSK_FILE, "rb") as f:
                self.wfile.write(f.read())
            return

        if parsed.path in ["/", "/index.html"]:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            with open(INDEX_FILE, "rb") as f:
                self.wfile.write(f.read())
            return

        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b"{}"
        try:
            req_data = json.loads(body.decode("utf-8"))
        except Exception:
            req_data = {}

        # Proxy automatico se configurato SHARED_DATA_URL (es. verso Kindlefridge su Render)
        cfg = load_config()
        shared_url = cfg.get("shared_data_url", "").strip()
        if shared_url and parsed.path.startswith("/api/"):
            base_remote = shared_url.split("/api/")[0]
            try:
                fwd_req = urllib.request.Request(
                    f"{base_remote}{parsed.path}",
                    data=body,
                    headers={"Content-Type": "application/json", "User-Agent": "KindleSimpleDashboard/1.0"}
                )
                with urllib.request.urlopen(fwd_req, timeout=5) as fwd_resp:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(fwd_resp.read())
                    return
            except Exception as e:
                print(f"[Sync URL] Errore proxy POST a {base_remote}: {e}")

        data = load_data()

        # Toggle Spesa
        if parsed.path == "/api/toggle-grocery":
            gid = req_data.get("id")
            for item in data.get("groceries", []):
                if item.get("id") == gid:
                    item["done"] = not item.get("done", False)
                    break
            save_data(data)
            self._send_json({"ok": True, "groceries": data.get("groceries", [])})
            return

        # Pulisci Spesa Comprata
        if parsed.path == "/api/clear-groceries":
            data["groceries"] = [g for g in data.get("groceries", []) if not g.get("done")]
            save_data(data)
            self._send_json({"ok": True, "groceries": data.get("groceries", [])})
            return

        # Elimina Nota
        if parsed.path == "/api/delete-note":
            nid = req_data.get("id")
            data["notes"] = [n for n in data.get("notes", []) if n.get("id") != nid]
            save_data(data)
            self._send_json({"ok": True, "notes": data.get("notes", [])})
            return

        self.send_response(404)
        self.end_headers()

    def _send_json(self, obj):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(obj, ensure_ascii=False).encode("utf-8"))

def run_server(port=8080):
    os.chdir(BASE_DIR)
    cfg = load_config()

    # Avvia thread bot telegram solo se configurato un token standalone
    if cfg.get("bot_token", "").strip():
        t = threading.Thread(target=telegram_poller_thread, daemon=True)
        t.start()
        print("[Telegram] Bot poller avviato in modalità standalone.")
    else:
        target_file = get_target_data_file()
        if os.path.exists(target_file):
            print(f"[Sync] Collegato al file dati condiviso: {target_file}")
            print("[Sync] Note e spesa si aggiornano in tempo reale tramite il bot principale.")
        else:
            print("[Sync] Modalità locale: in attesa di dati.")

    server_address = ("", port)
    httpd = ThreadingHTTPServer(server_address, KindleSimpleHandler)
    print("=" * 60)
    print(f"[Kindle Simple Dashboard] Server attivo!")
    print(f"   * Dashboard Web (10s auto-refresh): http://localhost:{port}")
    print(f"   * Endpoint Immagine PNG:           http://localhost:{port}/screen.png")
    print(f"   * Risoluzione predefinita:         {cfg.get('default_width', 1072)}x{cfg.get('default_height', 1448)} (Kindle 11a gen)")
    print("=" * 60)
    httpd.serve_forever()

if __name__ == "__main__":
    cfg = load_config()
    default_port = cfg.get("port", 8080)
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            port = default_port
    else:
        port = default_port
    run_server(port)
