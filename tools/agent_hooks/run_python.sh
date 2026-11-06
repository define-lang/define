#!/bin/bash
# Runs Python in isolated mode with these arguments, using the first of python3,
# python and py that works. On Windows, python3 and python are often Microsoft
# Store stubs that only print an error, and py is the launcher that the
# python.org installer provides.
for python in python3 python py; do
	if command -v "$python" >/dev/null && "$python" -c '' 2>/dev/null; then
		exec "$python" -I "$@"
	fi
done
echo 'The agent hooks need Python 3 on PATH as python3, python or py.' >&2
exit 1
