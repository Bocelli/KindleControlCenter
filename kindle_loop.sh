#!/bin/sh
# ==============================================================================
# Kindle Simple Dashboard - Script di refresh continuo (ogni 10 secondi)
# Da copiare ed eseguire su Amazon Kindle jailbroken con 'eips' abilitato.
#
# Utilizzo:
#   chmod +x kindle_loop.sh
#   ./kindle_loop.sh http://192.168.1.XXX:8080/screen.png
# ==============================================================================

# Inserisci qui l'IP del computer o server su cui gira server.py
SERVER_URL="${1:-https://kindlecontrolcenter.onrender.com/screen.png}"
INTERVAL="${2:-600}" # Default: 10 minuti (600 secondi)
TMP_IMG="/tmp/kindle_screen.png"

echo "Avvio Kindle Dashboard Loop verso: $SERVER_URL"
echo "Aggiornamento ogni $INTERVAL secondi (~$((INTERVAL / 60)) min). Premi Ctrl+C per fermare."

# Disabilita screensaver nativo se presente
if [ -f /usr/bin/lipc-set-prop ]; then
  lipc-set-prop -i com.lab126.powerd preventScreenSaver 1
fi

# Pulizia iniziale dello schermo per azzerare tastiera e ghosting
eips -c 2>/dev/null

CYCLES=0
while true; do
  CYCLES=$((CYCLES + 1))
  # Pulizia completa dello schermo ogni 6 cicli (~1 ora) per azzerare il ghosting E-Ink
  if [ "$CYCLES" -ge 6 ]; then
    eips -c 2>/dev/null
    CYCLES=0
  fi

  # Rileva livello batteria del Kindle (0-100)
  BAT=""
  if command -v lipc-get-prop >/dev/null 2>&1; then
    BAT=$(lipc-get-prop com.lab126.powerd battLevel 2>/dev/null)
  fi
  if [ -z "$BAT" ] && [ -f /sys/class/power_supply/battery/capacity ]; then
    BAT=$(cat /sys/class/power_supply/battery/capacity 2>/dev/null)
  fi

  REQ_URL="$SERVER_URL"
  if [ -n "$BAT" ]; then
    case "$REQ_URL" in
      *\?*) REQ_URL="${REQ_URL}&bat=${BAT}" ;;
      *)    REQ_URL="${REQ_URL}?bat=${BAT}" ;;
    esac
  fi

  # Scarica immagine dal server (prova curl, wget o fallback binario)
  SUCCESS=1
  if [ -x /mnt/us/bin/curl ]; then
    /mnt/us/bin/curl -k -s -m 8 -o "$TMP_IMG" "$REQ_URL" && SUCCESS=0
  elif command -v curl >/dev/null 2>&1; then
    curl -k -s -m 8 -o "$TMP_IMG" "$REQ_URL" && SUCCESS=0
  elif command -v wget >/dev/null 2>&1; then
    wget -q --no-check-certificate -O "$TMP_IMG" --timeout=8 "$REQ_URL" 2>/dev/null && SUCCESS=0
  fi

  if [ "$SUCCESS" -eq 0 ] && [ -s "$TMP_IMG" ]; then
    # Disegna immagine a schermo con eips
    eips -g "$TMP_IMG"
  else
    echo "[Errore] Impossibile scaricare immagine da: $SERVER_URL"
  fi
  sleep "$INTERVAL"
done
