#!/bin/bash

# botfights.sh -- wrapper for botfights.io <=> monkeystud

DIR=botfights_monkeystud_`date +%Y-%m-%d-%H-%M-%S`
virtualenv $DIR
source $DIR/bin/activate
pip install -e .
monkeystud --catch-exceptions=TRUE --log-level=DEBUG tournament --num-games 10000 $@
