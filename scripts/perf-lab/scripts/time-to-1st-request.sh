#!/usr/bin/env bash

RUN_CMD="$1"
TARGET_URL="$2"
LOG_FILE="$3"

function _date() {
    current=$(date +%s%N)
    if [ $? -ne 0 ]; then
      current=$(gdate +%s%N)
    fi
    echo "$current"
}

# Start the application
eval "$RUN_CMD" &>"$LOG_FILE" &
APP_PID=$!

# Ensure the application is killed when the script exits (e.g. on timeout)
trap "kill -15 $APP_PID 2>/dev/null" EXIT

ts=$(_date)

while [[ $(curl -s -o /dev/null -w ''%{http_code}'' ${TARGET_URL}) != 200 ]]
do
  # Spin here and do nothing rather waiting some arbitrary unlucky timing
  :
done

TTFR=$((($(_date) - ts)/1000000))
echo "${TTFR}"
