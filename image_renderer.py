import os
import textwrap
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

def get_font(name_or_style, size):
    """Carica un font TrueType con fallback multipli (Windows / Linux / default)."""
    candidates = []
    if name_or_style == "bold":
        candidates = ["segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf", "segoeui.ttf", "arial.ttf"]
    else:
        candidates = ["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"]

    for c in candidates:
        try:
            return ImageFont.truetype(c, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()

def render_dashboard_image(data, weather, width=1072, height=1448):
    """
    Genera un'immagine PNG monocromatica ad alto contrasto (scala di grigi 8-bit)
    perfetta per schermi E-Ink Amazon Kindle (Kindle 11a gen 1072x1448 portrait / 1448x1072 landscape,
    Paperwhite 758x1024, Kindle base 600x800).
    """
    # Modalità 'L' (grayscale a 8-bit) per antialiasing nitido su e-ink
    img = Image.new("L", (width, height), 255)
    draw = ImageDraw.Draw(img)

    BLACK = 0
    WHITE = 255

    is_portrait = height >= width
    # Scala proporzionale in base alla risoluzione di riferimento (600x800 portrait, 800x600 landscape)
    scale = (width / 600.0) if is_portrait else (width / 800.0)

    f_title = get_font("bold", max(18, int(22 * scale)))
    f_header = get_font("bold", max(14, int(16 * scale)))
    f_body = get_font("regular", max(12, int(14 * scale)))
    f_small = get_font("regular", max(10, int(12 * scale)))
    f_temp = get_font("bold", max(28, int(38 * scale)))

    # Bordo esterno
    draw.rectangle([0, 0, width - 1, height - 1], outline=BLACK, width=2)
    sync_time = datetime.now().strftime("%H:%M:%S")

    city = weather.get("city", "Salemi (TP)").upper()
    cond = weather.get("condition", "SERENO").upper()
    temp = weather.get("temp", "--°C")
    min_max = weather.get("min_max", "")
    rain = weather.get("rain", "")
    forecast_slots = weather.get("forecast", [])

    if is_portrait:
        # ==========================================
        # LAYOUT PORTRAIT (es. Kindle 11: 1072x1448)
        # ==========================================
        
        # 1. METEO BANNER (Top)
        meteo_h = int(125 * (height / 800.0))
        draw.rectangle([0, 0, width, meteo_h], fill=WHITE, outline=BLACK, width=2)

        # Badge città a larghezza dinamica
        city_badge = f" {city} "
        c_bbox = draw.textbbox((16, int(10 * scale)), city_badge, font=f_small)
        draw.rectangle([10, int(8 * scale), c_bbox[2] + int(4 * scale), c_bbox[3] + int(4 * scale)], fill=BLACK)
        draw.text((16, int(10 * scale)), city_badge, font=f_small, fill=WHITE)

        # Temperatura grande
        draw.text((15, int(38 * scale)), temp, font=f_temp, fill=BLACK)
        temp_bbox = draw.textbbox((15, int(38 * scale)), temp, font=f_temp)

        # Condizione meteo e min/max
        cond_x = max(int(130 * scale), temp_bbox[2] + int(12 * scale))
        draw.text((cond_x, int(42 * scale)), cond, font=f_header, fill=BLACK)
        draw.text((cond_x, int(64 * scale)), f"{min_max}  •  {rain}", font=f_small, fill=BLACK)

        # Previsioni prossime ore
        if forecast_slots:
            fc_text = "  |  ".join([f"{s.get('time', '')}: {s.get('temp', '')} ({s.get('desc', '')})" for s in forecast_slots[:2]])
            draw.text((15, int(96 * scale)), f"Prossime ore: {fc_text}", font=f_small, fill=BLACK)

        # 2. NOTE SULLA BACHECA (Metà superiore)
        notes_top = meteo_h
        notes_h = int((height - meteo_h - 35) * 0.48)
        notes_bottom = notes_top + notes_h

        # Header Note (barra nera)
        draw.rectangle([0, notes_top, width, notes_top + int(32 * scale)], fill=BLACK)
        draw.text((15, notes_top + int(6 * scale)), "NOTE IN BACHECA (SYNC TELEGRAM)", font=f_header, fill=WHITE)

        notes = data.get("notes", [])
        curr_y = notes_top + int(40 * scale)

        if not notes:
            draw.text((20, curr_y + 10), "Nessuna nota presente sulla bacheca.", font=f_body, fill=BLACK)
            draw.text((20, curr_y + int(30 * scale)), "Invia un messaggio al bot Telegram per appuntarlo qui.", font=f_small, fill=BLACK)
        else:
            char_w = draw.textlength("n", font=f_body)
            wrap_w = max(30, int((width - 40) / (char_w * 1.05)))
            for n in notes:
                author = (n.get("author") or "FAMIGLIA").upper()
                time_str = n.get("time") or ""
                text = n.get("text") or ""

                # Badge Autore con misura dinamica esatta
                abbox = draw.textbbox((20, curr_y + int(2 * scale)), author, font=f_small)
                badge_right = abbox[2] + int(6 * scale)
                draw.rectangle([15, curr_y, badge_right, curr_y + int(18 * scale)], fill=BLACK)
                draw.text((20, curr_y + int(2 * scale)), author, font=f_small, fill=WHITE)

                if time_str:
                    draw.text((badge_right + int(8 * scale), curr_y + int(2 * scale)), time_str, font=f_small, fill=BLACK)

                # Testo della nota (a capo automatico)
                curr_y += int(22 * scale)
                wrapped_lines = textwrap.wrap(text, width=wrap_w)
                for line in wrapped_lines[:2]:
                    draw.text((20, curr_y), line, font=f_body, fill=BLACK)
                    curr_y += int(18 * scale)

                curr_y += int(6 * scale)
                draw.line([15, curr_y, width - 15, curr_y], fill=BLACK, width=1)
                curr_y += int(6 * scale)

                if curr_y > notes_bottom - int(30 * scale):
                    break

        # 3. LISTA DELLA SPESA (Metà inferiore)
        spesa_top = notes_bottom
        spesa_bottom = height - int(32 * scale)

        groceries = data.get("groceries", [])
        pending_count = len([g for g in groceries if not g.get("done")])
        header_spesa = f"LISTA DELLA SPESA ({pending_count} DA COMPRARE)" if pending_count else "LISTA DELLA SPESA (TUTTO COMPRATO)"

        draw.rectangle([0, spesa_top, width, spesa_top + int(32 * scale)], fill=BLACK)
        draw.text((15, spesa_top + int(6 * scale)), header_spesa, font=f_header, fill=WHITE)

        curr_y = spesa_top + int(42 * scale)
        if not groceries:
            draw.text((20, curr_y + 10), "Nessun articolo nella spesa.", font=f_body, fill=BLACK)
            draw.text((20, curr_y + int(30 * scale)), "Scrivi 'spesa latte, pasta' su Telegram per aggiungerli.", font=f_small, fill=BLACK)
        else:
            sorted_groceries = sorted(groceries, key=lambda x: x.get("done", False))
            for g in sorted_groceries:
                is_done = g.get("done", False)
                text = g.get("text", "")
                author = g.get("author", "")

                # Casella Checkbox
                cb_size = int(16 * scale)
                cb_x = 20
                cb_y = curr_y + 1
                draw.rectangle([cb_x, cb_y, cb_x + cb_size, cb_y + cb_size], outline=BLACK, width=2)
                if is_done:
                    draw.line([cb_x, cb_y, cb_x + cb_size, cb_y + cb_size], fill=BLACK, width=2)
                    draw.line([cb_x, cb_y + cb_size, cb_x + cb_size, cb_y], fill=BLACK, width=2)

                item_x = cb_x + cb_size + int(12 * scale)
                item_font = f_body if not is_done else f_small
                draw.text((item_x, curr_y), text, font=item_font, fill=BLACK)

                if author:
                    draw.text((width - int(120 * scale), curr_y), f"({author})", font=f_small, fill=BLACK)

                if is_done:
                    bbox = draw.textbbox((item_x, curr_y), text, font=item_font)
                    draw.line([item_x, curr_y + int(9 * scale), bbox[2], curr_y + int(9 * scale)], fill=BLACK, width=1)

                curr_y += int(26 * scale)
                if curr_y > spesa_bottom - int(24 * scale):
                    break

        # 4. FOOTER DI STATO
        draw.rectangle([0, height - int(30 * scale), width, height], fill=BLACK)
        draw.text((15, height - int(22 * scale)), f"KINDLE SIMPLE DASHBOARD  •  REFRESH 10s  •  ORE {sync_time}", font=f_small, fill=WHITE)

    else:
        # ==========================================
        # LAYOUT LANDSCAPE (es. Kindle 11: 1448x1072)
        # ==========================================
        meteo_h = int(95 * (height / 600.0))
        draw.rectangle([0, 0, width, meteo_h], fill=WHITE, outline=BLACK, width=2)

        city_badge = f" {city} "
        c_bbox = draw.textbbox((int(18 * scale), int(12 * scale)), city_badge, font=f_small)
        draw.rectangle([int(12 * scale), int(10 * scale), c_bbox[2] + int(4 * scale), c_bbox[3] + int(4 * scale)], fill=BLACK)
        draw.text((int(18 * scale), int(12 * scale)), city_badge, font=f_small, fill=WHITE)

        draw.text((int(15 * scale), int(34 * scale)), temp, font=f_temp, fill=BLACK)
        temp_bbox = draw.textbbox((int(15 * scale), int(34 * scale)), temp, font=f_temp)

        cond_x = max(int(140 * scale), temp_bbox[2] + int(14 * scale))
        draw.text((cond_x, int(36 * scale)), cond, font=f_header, fill=BLACK)
        draw.text((cond_x, int(58 * scale)), f"{min_max}   |   {rain}", font=f_small, fill=BLACK)

        if forecast_slots:
            fc_text = "   •   ".join([f"ore {s.get('time', '')}: {s.get('temp', '')} ({s.get('desc', '')})" for s in forecast_slots[:2]])
            draw.text((width - int(380 * scale), int(38 * scale)), f"Previsioni prossime ore:\n{fc_text}", font=f_small, fill=BLACK)

        # 2. COLONNE SPLIT (Sinistra Note, Destra Spesa)
        split_x = width // 2
        header_h = int(30 * scale)
        footer_h = int(28 * scale)
        content_top = meteo_h
        content_bottom = height - footer_h

        draw.line([split_x, content_top, split_x, content_bottom], fill=BLACK, width=2)

        # Header Sinistra (NOTE)
        draw.rectangle([0, content_top, split_x, content_top + header_h], fill=BLACK)
        draw.text((int(15 * scale), content_top + int(6 * scale)), "NOTE IN BACHECA (TELEGRAM)", font=f_header, fill=WHITE)

        notes = data.get("notes", [])
        curr_y = content_top + header_h + int(10 * scale)
        if not notes:
            draw.text((int(20 * scale), curr_y + 10), "Nessuna nota presente sulla bacheca.", font=f_body, fill=BLACK)
        else:
            char_w = draw.textlength("n", font=f_body)
            wrap_w = max(20, int((split_x - int(40 * scale)) / (char_w * 1.05)))
            for n in notes:
                author = (n.get("author") or "FAMIGLIA").upper()
                time_str = n.get("time") or ""
                text = n.get("text") or ""

                abbox = draw.textbbox((int(19 * scale), curr_y + int(1 * scale)), author, font=f_small)
                badge_right = abbox[2] + int(4 * scale)
                draw.rectangle([int(15 * scale), curr_y, badge_right, curr_y + int(16 * scale)], fill=BLACK)
                draw.text((int(19 * scale), curr_y + int(1 * scale)), author, font=f_small, fill=WHITE)

                if time_str:
                    draw.text((badge_right + int(8 * scale), curr_y + int(1 * scale)), time_str, font=f_small, fill=BLACK)

                curr_y += int(20 * scale)
                for line in textwrap.wrap(text, width=wrap_w)[:2]:
                    draw.text((int(20 * scale), curr_y), line, font=f_body, fill=BLACK)
                    curr_y += int(18 * scale)

                curr_y += int(6 * scale)
                draw.line([int(15 * scale), curr_y, split_x - int(15 * scale), curr_y], fill=BLACK, width=1)
                curr_y += int(6 * scale)

                if curr_y > content_bottom - int(24 * scale):
                    break

        # Header Destra (SPESA)
        groceries = data.get("groceries", [])
        pending_count = len([g for g in groceries if not g.get("done")])
        h_spesa = f"LISTA SPESA ({pending_count} DA COMPRARE)" if pending_count else "LISTA SPESA (TUTTO COMPRATO)"
        draw.rectangle([split_x, content_top, width, content_top + header_h], fill=BLACK)
        draw.text((split_x + int(15 * scale), content_top + int(6 * scale)), h_spesa, font=f_header, fill=WHITE)

        curr_y = content_top + header_h + int(10 * scale)
        if not groceries:
            draw.text((split_x + int(20 * scale), curr_y + 10), "Nessun articolo da comprare.", font=f_body, fill=BLACK)
        else:
            sorted_groceries = sorted(groceries, key=lambda x: x.get("done", False))
            for g in sorted_groceries:
                is_done = g.get("done", False)
                text = g.get("text", "")
                author = g.get("author", "")

                cb_size = int(15 * scale)
                cb_x = split_x + int(20 * scale)
                cb_y = curr_y + 1
                draw.rectangle([cb_x, cb_y, cb_x + cb_size, cb_y + cb_size], outline=BLACK, width=2)
                if is_done:
                    draw.line([cb_x, cb_y, cb_x + cb_size, cb_y + cb_size], fill=BLACK, width=2)
                    draw.line([cb_x, cb_y + cb_size, cb_x + cb_size, cb_y], fill=BLACK, width=2)

                item_x = cb_x + cb_size + int(10 * scale)
                item_font = f_body if not is_done else f_small
                draw.text((item_x, curr_y), text, font=item_font, fill=BLACK)

                if author:
                    draw.text((width - int(100 * scale), curr_y), f"({author})", font=f_small, fill=BLACK)

                if is_done:
                    bbox = draw.textbbox((item_x, curr_y), text, font=item_font)
                    draw.line([item_x, curr_y + int(9 * scale), bbox[2], curr_y + int(9 * scale)], fill=BLACK, width=1)

                curr_y += int(24 * scale)
                if curr_y > content_bottom - int(20 * scale):
                    break

        # 3. FOOTER
        draw.rectangle([0, height - footer_h, width, height], fill=BLACK)
        draw.text((int(15 * scale), height - int(20 * scale)), f"KINDLE SIMPLE DASHBOARD  •  REFRESH 10s  •  ORE {sync_time}", font=f_small, fill=WHITE)

    return img
