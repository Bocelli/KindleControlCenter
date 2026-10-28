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
SERVER_URL="${1:-http://192.168.1.100:8080/screen.png}"
TMP_IMG="/tmp/kindle_screen.png"

echo "Avvio Kindle Dashboard Loop verso: $SERVER_URL"
echo "Aggiornamento ogni 10 secondi. Premi Ctrl+C per fermare."

# Disabilita screensaver nativo se presente
if [ -f /usr/bin/lipc-set-prop ]; then
  lipc-set-prop -i com.lab126.powerd preventScreenSaver 1
fi

CYCLES=0
while true; do
  CYCLES=$((CYCLES + 1))
  # Pulizia completa dello schermo ogni 30 cicli (~5 minuti) per azzerare il ghosting E-Ink
  if [ "$CYCLES" -ge 30 ]; then
    eips -c 2>/dev/null
    CYCLES=0
  fi

  # Scarica immagine dal server (prova curl, wget o fallback binario)
  SUCCESS=1
  if [ -x /mnt/us/bin/curl ]; then
    /mnt/us/bin/curl -k -s -m 8 -o "$TMP_IMG" "$SERVER_URL" && SUCCESS=0
  elif command -v curl >/dev/null 2>&1; then
    curl -k -s -m 8 -o "$TMP_IMG" "$SERVER_URL" && SUCCESS=0
  elif command -v wget >/dev/null 2>&1; then
    wget -q --no-check-certificate -O "$TMP_IMG" --timeout=8 "$SERVER_URL" 2>/dev/null && SUCCESS=0
  fi

  if [ "$SUCCESS" -eq 0 ] && [ -s "$TMP_IMG" ]; then
    # Disegna immagine a schermo con eips
    eips -g "$TMP_IMG"
  else
    echo "[Errore] Impossibile scaricare immagine da: $SERVER_URL"
  fi
  sleep 10
done
