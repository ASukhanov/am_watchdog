#!/bin/bash
ii=0
until python am_watchdog.py; do
    echo "Server 'am_watchdog' exit with code $?.  Respawning.." >&2
    sleep 1
done
