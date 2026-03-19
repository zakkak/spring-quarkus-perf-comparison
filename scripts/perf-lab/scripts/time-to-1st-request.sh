#!/usr/bin/env bash

RUN_CMD="$1"
TARGET_URL="$2"
LOG_FILE="$3"

END_TS_FILE=$(mktemp)

# Parse host and port from TARGET_URL (e.g. http://localhost:8080/fruits)
URL_NO_SCHEME="${TARGET_URL#http://}"
HOST_PORT="${URL_NO_SCHEME%%/*}"
HOST="${HOST_PORT%%:*}"
PORT="${HOST_PORT##*:}"
: "${PORT:=80}"
if [[ "$URL_NO_SCHEME" == */* ]]; then
  URL_PATH="/${URL_NO_SCHEME#*/}"
else
  URL_PATH="/"
fi

function _date() {
    current=$(date +%s%N)
    if [ $? -ne 0 ]; then
      current=$(gdate +%s%N)
    fi
    echo "$current"
}

# Start the client loop before the application so it's already polling
(
  while true; do
    if exec 3<>/dev/tcp/"$HOST"/"$PORT"; then
      printf "GET %s HTTP/1.0\r\nHost: %s\r\nConnection: close\r\n\r\n" "$URL_PATH" "$HOST" >&3
      read -r _ status_code _ <&3
      exec 3>&-
      if [[ "$status_code" == "200" ]]; then
        break
      fi
    fi
    # Spin here and do nothing rather waiting some arbitrary unlucky timing
  done
  _date > "$END_TS_FILE"
) 2>/dev/null &
CURL_PID=$!

# Record start time and launch the application.
# Redirect and exec inside the subshell so the application process
# directly replaces the subshell, making $APP_PID its actual PID.
ts=$(_date)
( exec $RUN_CMD &>"$LOG_FILE" ) &
APP_PID=$!

# Ensure cleanup on exit (e.g. on timeout)
trap "kill -15 $APP_PID $CURL_PID 2>/dev/null; wait $APP_PID 2>/dev/null; rm -f $END_TS_FILE" EXIT

# Wait for the client loop to get a successful response
wait $CURL_PID 2>/dev/null

TTFR=$((($(cat "$END_TS_FILE") - ts)/1000000))
echo "${TTFR}"
