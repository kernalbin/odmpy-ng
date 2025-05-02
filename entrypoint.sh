#!/bin/bash -x
set -e

# Set defaults if not provided
: "${HOST_UID:=1000}"
: "${HOST_GID:=1000}"

# Find existing group with the desired GID
existing_group=$(getent group "$HOST_GID" | cut -d: -f1 || true)

if [ -z "$existing_group" ]; then
    groupadd -g "$HOST_GID" hostgroup
    groupname=hostgroup
else
    groupname="$existing_group"
fi

existing_user=$(getent passwd "$HOST_UID" | cut -d: -f1 || true)
if [ -z "$existing_user" ]; then
    useradd -m -u "$HOST_UID" -g "$groupname" hostuser
    username=hostuser
else
    username="$existing_user"
fi

# Fix permissions (optional, e.g., for /downloads)
mkdir -p /downloads
chown $HOST_UID:$HOST_GID /downloads
chown -R $HOST_UID:$HOST_GID /app

# Drop privileges
exec gosu "$username" python3 interactive.py /config/config.json

