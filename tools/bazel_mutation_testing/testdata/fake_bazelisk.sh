#!/bin/sh
# Stands in for bazelisk in worker_test.py. The directory that holds this
# script also holds its state. Each `test` command runs the next of the
# numbered behaviors in the `tests` directory: "fail" exits as a crashed server
# does, "hang" waits until it is killed, and any other passes.
fake=$(dirname "$0")
for argument; do
	case $argument in
	--build_event_json_file=*) : >"${argument#*=}" ;;
	esac
done
for argument; do
	case $argument in
	-*) ;;
	*)
		command=$argument
		break
		;;
	esac
done
case $command in
info) echo "$fake/output_base" ;;
build)
	mkdir -p bazel-bin/tools/format/format_
	printf '#!/bin/sh\n' >bazel-bin/tools/format/format_/format
	chmod +x bazel-bin/tools/format/format_/format
	;;
test)
	count=$(($(cat "$fake/count" 2>/dev/null || echo 0) + 1))
	echo "$count" >"$fake/count"
	behavior=$(cat "$fake/tests/$count" 2>/dev/null)
	case $behavior in
	fail)
		echo "bazel crashed" >&2
		exit 37
		;;
	hang)
		mkdir -p "$fake/output_base/server"
		echo $$ >"$fake/output_base/server/server.pid.txt"
		mkfifo "$fake/never_written"
		exec cat "$fake/never_written"
		;;
	esac
	;;
esac
