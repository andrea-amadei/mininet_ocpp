#!/bin/sh

sudo "$(dirname "$0")/venv/bin/python" "$(dirname "$0")/ocpp/client.py" "$@"
