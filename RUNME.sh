#!/bin/sh
# RUNME.sh - Gestore avvio/arresto Kindle Simple Dashboard tramite comandi da barra di ricerca (;log runme)

PID=$(pgrep -f "kindle_loop.sh")

if [ -n "$PID" ]; then
    eips 1 25 "Fermando Kindle Dashboard..."
    killall -9 kindle_loop.sh 2>/dev/null
    kill -9 $PID 2>/dev/null
    if [ -f /usr/bin/lipc-set-prop ]; then
        lipc-set-prop -i com.lab126.powerd preventScreenSaver 0 2>/dev/null
    fi
    sleep 1
    eips -c
    eips 1 25 "Dashboard fermata. Buona lettura!"
else
    eips 1 25 "Avvio Kindle Dashboard..."
    if [ -f /usr/bin/lipc-set-prop ]; then
        lipc-set-prop -i com.lab126.powerd preventScreenSaver 1 2>/dev/null
    fi
    nohup /bin/sh /mnt/us/kindle_loop.sh "https://kindlecontrolcenter.onrender.com/screen.png" 600 >/tmp/dashboard.log 2>&1 &
    sleep 2
fi
