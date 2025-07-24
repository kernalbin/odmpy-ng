#!/bin/bash
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

echo "Run commands as in-container user $username (UID: $HOST_UID, GID: $HOST_GID)"

# Fix permissions
mkdir -p /downloads
mkdir -p /tmp-downloads
chown $HOST_UID:$HOST_GID /downloads /tmp-downloads

echo "Process arguments for $0 $@"
if [[ $1 == "--idle" ]]; then
    while true; do
        sleep 60
        printf "."
    done
else
    # Drop privileges (-u to unbuffer, line by line is better for us)
    exec gosu "$username" python3 -u interactive.py /config/config.json "$@"
fi

