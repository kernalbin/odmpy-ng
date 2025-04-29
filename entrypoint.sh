#!/bin/bash
set -e

# Run app
python3 interactive.py /config/config.json

# Set ownership of downloaded files
chown -R ubuntu /downloads