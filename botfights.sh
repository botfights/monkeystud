#!/bin/bash

# botfights.sh -- wrapper for botfights.io <=> monkeystud

command=$1
shift

if [ $command == "tournament" ]; then
  bots="$@"
  python monkeystud.py tournament --catch-exceptions=on --log-level=10 $bots
fi

if [ $command == "verify" ]; then
  bot="$1"
  python monkeystud.py verify --catch-exceptions=on --log-level=10 $bot
fi
