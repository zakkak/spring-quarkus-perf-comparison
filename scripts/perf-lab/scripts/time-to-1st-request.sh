#!/usr/bin/env bash

RUN_CMD="$1"
TARGET_URL="$2"
LOG_FILE="$3"

END_TS_FILE=$(mktemp)

function _date() {
    current=$(date +%s%N)
    if [ $? -ne 0 ]; then
      current=$(gdate +%s%N)
    fi
    echo "$current"
}

# Start the client loop before the application so it's already polling
(
  while [[ $(curl -s -o /dev/null -w ''%{http_code}'' ${TARGET_URL}) != 200 ]]; do
    # Spin here and do nothing rather waiting some arbitrary unlucky timing
    :
  done
  _date > "$END_TS_FILE"
) &
CURL_PID=$!

# Record start time and launch the application.
# Redirect and exec inside the subshell so the application process
# directly replaces the subshell, making $APP_PID its actual PID.
ts=$(_date)
( exec $RUN_CMD &>"$LOG_FILE" ) &
APP_PID=$!

# Ensure cleanup on exit (e.g. on timeout)
trap "kill -15 $APP_PID $CURL_PID 2>/dev/null; rm -f $END_TS_FILE" EXIT

# Wait for the client loop to get a successful response
wait $CURL_PID 2>/dev/null

TTFR=$((($(cat "$END_TS_FILE") - ts)/1000000))
echo "${TTFR}"
