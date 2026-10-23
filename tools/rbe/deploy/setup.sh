#!/usr/bin/env bash
# Sets up the rbe service on this machine, or removes it with --uninstall. Run it
# with sudo as the developer who will use and deploy the service; see
# ../README.md. Running it again updates the setup.
set -euo pipefail

readonly STATE=/var/lib/rbe
readonly IMAGE=$STATE/store.img
readonly STORE=$STATE/store
readonly LIBEXEC=/usr/local/libexec/rbe
readonly UNITS=/etc/systemd/system
readonly SUDOERS=/etc/sudoers.d/rbe
# These are the options the store was benchmarked with: more allocation groups
# and a bigger log for many parallel metadata changes, and no parent pointers or
# reverse mapping, which only slow down creating and deleting the many files of
# action directories. rbe-store.service attaches the image with 4096-byte
# sectors, which direct I/O needs, so XFS must use them too.
readonly MKFS_OPTIONS=(-s size=4096 -d agcount=32 -n parent=0 -m rmapbt=0 -l size=512m)

usage() {
	echo "usage: sudo $0 [--size SIZE] | --uninstall" >&2
	echo "SIZE is the store's size, such as 300G (the default)." >&2
	exit 2
}

require_commands() {
	local missing=()
	local command
	for command in "$@"; do
		command -v "$command" >/dev/null || missing+=("$command")
	done
	if ((${#missing[@]})); then
		echo "Missing commands: ${missing[*]}" >&2
		exit 1
	fi
}

setup() {
	local size=$1
	local owner=$SUDO_USER
	local owner_group
	owner_group=$(id -gn "$owner")
	local size_bytes
	size_bytes=$(numfmt --from=iec "$size")

	if ! id rbe >/dev/null 2>&1; then
		useradd --system --user-group --home-dir "$STATE" --no-create-home \
			--shell /usr/sbin/nologin rbe
	fi
	install -d -m 0755 "$STATE" "$STORE"

	local grow=false
	if [[ ! -e $IMAGE ]]; then
		touch "$IMAGE"
		chmod 0600 "$IMAGE"
		# Copy-on-write would make btrfs rewrite and compress the image's blocks
		# under XFS. It can only be turned off while the file is empty.
		if [[ $(stat -f -c %T "$STATE") == btrfs ]]; then
			chattr +C "$IMAGE"
		fi
		truncate -s "$size_bytes" "$IMAGE"
		mkfs.xfs -q "${MKFS_OPTIONS[@]}" "$IMAGE"
	else
		local current_bytes
		current_bytes=$(stat -c %s "$IMAGE")
		if ((size_bytes < current_bytes)); then
			echo "The store is already $(numfmt --to=iec "$current_bytes"), and XFS cannot shrink." >&2
			echo "Run with --uninstall first to start over with a smaller store." >&2
			exit 1
		fi
		if ((size_bytes > current_bytes)); then
			truncate -s "$size_bytes" "$IMAGE"
			grow=true
		fi
	fi

	local script_dir
	script_dir=$(dirname "$(realpath "$0")")
	install -m 0644 "$script_dir/rbe.socket" "$script_dir/rbe.service" \
		"$script_dir/rbe-store.service" "$UNITS"
	systemctl daemon-reload
	systemctl start rbe-store.service
	if [[ $grow == true ]]; then
		# The loop device keeps the image's old size until told to recheck it.
		losetup --set-capacity "$(findmnt -n -o SOURCE "$STORE")"
		xfs_growfs "$STORE" >/dev/null
	fi
	chown rbe:rbe "$STORE"
	chmod 0750 "$STORE"

	# The developer installs new binaries without root, so the binary can do
	# nothing the developer couldn't already do.
	install -d -o "$owner" -m 0755 "$LIBEXEC"

	install -d -m 0755 "$UNITS/rbe.socket.d" "$UNITS/rbe.service.d"
	printf '[Socket]\nSocketGroup=%s\n' "$owner_group" >"$UNITS/rbe.socket.d/group.conf"
	# Keep a tenth of the filesystem for action directories and XFS metadata.
	local filesystem_bytes
	filesystem_bytes=$(df -B1 --output=size "$STORE" | tail -n 1)
	printf '[Service]\nEnvironment=MAX_CAS_BYTES=%d\n' $((filesystem_bytes * 9 / 10)) \
		>"$UNITS/rbe.service.d/store.conf"

	local sudoers_entry
	sudoers_entry=$(mktemp)
	echo "$owner ALL=(root) NOPASSWD: $(command -v systemctl) restart rbe.service" >"$sudoers_entry"
	visudo -cqf "$sudoers_entry"
	install -m 0440 "$sudoers_entry" "$SUDOERS"
	rm "$sudoers_entry"

	systemctl daemon-reload
	# A changed socket unit takes effect only when the socket is recreated, and
	# systemd won't recreate it while the service is using it.
	systemctl stop rbe.service
	systemctl enable rbe.socket
	systemctl restart rbe.socket
	if [[ -x $LIBEXEC/rbe ]]; then
		systemctl start rbe.service
	fi
	echo "The rbe service is set up for $owner. Deploy it with: bazelisk run //tools/rbe/deploy"
}

uninstall() {
	systemctl disable --now rbe.socket rbe.service rbe-store.service 2>/dev/null || true
	if mountpoint -q "$STORE"; then
		echo "$STORE is still mounted; unmount it and run this again." >&2
		exit 1
	fi
	rm -rf "$STATE" "$LIBEXEC" "$SUDOERS" "$UNITS/rbe.socket" "$UNITS/rbe.service" \
		"$UNITS/rbe-store.service" "$UNITS/rbe.socket.d" "$UNITS/rbe.service.d"
	systemctl daemon-reload
	if id rbe >/dev/null 2>&1; then
		userdel rbe
	fi
	echo "Removed the rbe service."
}

main() {
	local size=300G
	local remove=false
	while (($#)); do
		case $1 in
		--size)
			(($# >= 2)) || usage
			size=$2
			shift 2
			;;
		--uninstall)
			remove=true
			shift
			;;
		*) usage ;;
		esac
	done
	if ((EUID != 0)) || [[ -z ${SUDO_USER:-} || $SUDO_USER == root ]]; then
		echo "Run this with sudo from your own account." >&2
		exit 1
	fi
	if [[ $remove == true ]]; then
		require_commands systemctl mountpoint userdel
		uninstall
	else
		require_commands systemctl useradd mkfs.xfs xfs_growfs losetup findmnt visudo numfmt chattr
		setup "$size"
	fi
}

main "$@"
