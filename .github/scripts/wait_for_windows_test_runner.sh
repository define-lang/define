#!/bin/bash
# Prints the Tailscale IP address of the tailnet machine named $1 once it
# joins. The Windows test runner takes its name only once it serves, so this
# waits for each change to the tailnet instead of probing the runner.
set -euo pipefail

hostname=$1
while read -r _; do
	address=$(sudo -n tailscale status --json | jq -r --arg hostname "$hostname" \
		'first(.Peer[]? | select(.HostName == $hostname) | .TailscaleIPs[0]) // empty')
	if [[ -n $address ]]; then
		echo "$address"
		exit 0
	fi
done < <(sudo -n tailscale debug watch-ipn --initial | jq --unbuffered -c 'null')
echo "The Tailscale event stream ended before $hostname joined." >&2
exit 1
