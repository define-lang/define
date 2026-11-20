#!/bin/sh
# Stands in for bazelisk in worker_test.py. The directory that holds this
# script also holds its state. Each `test` command runs the next of the
# numbered behaviors in the `tests` directory: "fail" exits as a crashed server
# does, "hang" waits until it is killed, "killed" fails its last target's test,
# and any other passes.
fake=$(dirname "$0")
events=
for argument; do
	case $argument in
	--build_event_json_file=*)
		events=${argument#*=}
		: >"$events"
		;;
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
targets=
target=
patterns=no
for argument; do
	if [ $patterns = yes ]; then
		targets="$targets $argument"
		target=$argument
	elif [ "$argument" = -- ]; then
		patterns=yes
	fi
done
case $command in
test) echo "test$targets" >>"$fake/commands" ;;
*) echo "$command" >>"$fake/commands" ;;
esac
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
	killed)
		printf '{"id":{"testResult":{"label":"%s","run":1,"shard":1,"attempt":1}},"testResult":{"status":"FAILED"}}\n' "$target" >"$events"
		exit 3
		;;
	esac
	;;
esac
