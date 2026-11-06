#!/bin/bash
# Prints the Tailscale IP address of the tailnet machine named $1 once it
# joins. The Windows test runner takes its name only once it serves, and takes
# the name $1-failed if it fails first, so this waits for each change to the
# tailnet instead of probing the runner.
set -euo pipefail

hostname=$1
while read -r _; do
	peers=$(sudo -n tailscale status --json)
	if jq -e --arg hostname "$hostname-failed" 'any(.Peer[]?; .HostName == $hostname)' \
		<<<"$peers" >/dev/null; then
		echo "The Windows test runner failed before it served." >&2
		exit 1
	fi
	address=$(jq -r --arg hostname "$hostname" \
		'first(.Peer[]? | select(.HostName == $hostname) | .TailscaleIPs[0]) // empty' <<<"$peers")
	if [[ -n $address ]]; then
		echo "$address"
		exit 0
	fi
done < <(sudo -n tailscale debug watch-ipn --initial | jq --unbuffered -c 'null')
echo "The Tailscale event stream ended before $hostname joined." >&2
exit 1
