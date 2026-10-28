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

  # Scarica immagine dal server con timeout di 5 secondi
  if wget -q -O "$TMP_IMG" --timeout=5 "$SERVER_URL"; then
    # Disegna immagine a schermo con eips
    eips -g "$TMP_IMG"
  else
    echo "[Errore] Impossibile contattare il server: $SERVER_URL"
  fi
  sleep 10
done
