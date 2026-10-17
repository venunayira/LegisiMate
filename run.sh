#!/bin/sh
# Only source this project's operator-controlled local config; never shell-trace secrets.
set -eu
cd -- "$(dirname -- "$0")"
if [ -f .env ]; then
    set -a
    . ./.env
    set +a
fi
exec .venv/bin/python -m legisimate.server "$@"
