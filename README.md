# 📟 Kindle Simple Dashboard (Meteo, Note & Spesa)

Progetto parallelo e leggero pensato appositamente per **Amazon Kindle (E-Ink)**, focalizzato esclusivamente su:
1. **🌤️ Meteo in tempo reale** (Salemi TP con temperatura, condizione, min/max, probabilità pioggia e prossime ore).
2. **📌 Note in Bacheca** (sincronizzate in tempo reale con i messaggi Telegram).
3. **🛒 Lista della Spesa** (gestibile via Telegram o con checkbox touch).

> **Nessun orario scolastico, nessun orologio ingombrante**: interfaccia pulita, minimale, ad alto contrasto monocromatico (1-bit / 8-bit grayscale), studiata per azzerare ghosting e distrazioni sullo schermo E-Ink del frigo.

---

## ⚡ Come funziona in parallelo con Kindle Fridge

Mentre il tablet da 10 pollici esegue il progetto principale (`kindle-fridge-dashboard` su porta **8000** con orario lezioni e Axios), questo progetto:
* Ascolta sulla porta **8080**.
* **Condivide automaticamente i dati** di [`../kindle-fridge-dashboard/data.json`](../kindle-fridge-dashboard/data.json): ogni volta che tu o la tua famiglia aggiungete una nota o un articolo per la spesa su Telegram, appare **immediatamente** sia sul tablet che sul Kindle!
* Non genera conflitti con le API di Telegram perché legge lo stesso store condiviso.

---

## 🚀 Avvio rapido

```bash
# Entra nella cartella
cd C:\Users\Irvine\.gemini\antigravity\scratch\kindle-simple-dashboard

# Installa la dipendenza (solo Pillow)
pip install -r requirements.txt

# Avvia il server (porta predefinita 8080)
python server.py 8080
```

---

## 📱 Visualizzazione sul Kindle

Hai due modalità di utilizzo a seconda di come è configurato il tuo Kindle:

### Modalità 1: Come Singola Immagine (Script Loop con `eips -g`)
Per Kindle jailbroken o con script wget/curl:
* L'endpoint `http://<IP_COMPUTER>:8080/screen.png` restituisce un'immagine PNG monocromatica ad altissimo contrasto generata al volo.
* Puoi copiare lo script incluso [`kindle_loop.sh`](kindle_loop.sh) sul Kindle ed eseguirlo:
  ```bash
  chmod +x kindle_loop.sh
  ./kindle_loop.sh http://192.168.1.XXX:8080/screen.png
  ```
  Lo script scarica e aggiorna lo schermo con `eips -g` ogni 10 secondi esatti.

### Modalità 2: Tramite Browser Web Sperimentale del Kindle
* Apri il browser del Kindle all'indirizzo `http://<IP_COMPUTER>:8080`.
* La pagina si aggiorna automaticamente **ogni 10 secondi** via JavaScript e ha il tag di fallback `<noscript><meta http-equiv="refresh" content="10"></noscript>`.

---

## ⚙️ Parametri Risoluzione Immagine

La risoluzione fissa predefinita in `config.json` è impostata su **Kindle 11ª Generazione** (Basic touch 2022, 300 ppi: **1072x1448**).
Se richiami l'endpoint `http://localhost:8080/screen.png` senza parametri, otterrai direttamente l'immagine nativa per Kindle 11.

Puoi comunque cambiare al volo o forzare altri orientamenti e modelli via parametri URL:
* **Kindle 11ª Gen (1072x1448 portrait - predefinito):** `http://localhost:8080/screen.png`
* **Kindle 11ª Gen (1448x1072 landscape):** `http://localhost:8080/screen.png?w=1448&h=1072`
* **Kindle Legacy (600x800 portrait):** `http://localhost:8080/screen.png?w=600&h=800`
* **Kindle Legacy (800x600 landscape):** `http://localhost:8080/screen.png?w=800&h=600`
* **Kindle Paperwhite (758x1024):** `http://localhost:8080/screen.png?w=758&h=1024`
