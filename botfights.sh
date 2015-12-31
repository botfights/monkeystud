#!/bin/bash

# botfights.sh -- wrapper for botfights.io <=> monkeystud

python monkeystud.py tournament --catch-exceptions=on --log-level=10 $@
