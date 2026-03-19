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

if date +%s%N &>/dev/null; then
  DATE_CMD=date
else
  DATE_CMD=gdate
fi

function _date() {
    $DATE_CMD +%s%N
}

t1=$(_date)
t2=$(_date)
t3=$(_date)
t4=$(_date)
t5=$(_date)
t6=$(_date)
t7=$(_date)
t8=$(_date)
t9=$(_date)
t10=$(_date)
t11=$(_date)
t12=$(_date)

echo "Time elapsed between two date calls: $((t2-t1)) ns"
echo "Time elapsed between two date calls: $((t3-t2)) ns"
echo "Time elapsed between two date calls: $((t4-t3)) ns"
echo "Time elapsed between two date calls: $((t5-t4)) ns"
echo "Time elapsed between two date calls: $((t6-t5)) ns"
echo "Time elapsed between two date calls: $((t7-t6)) ns"
echo "Time elapsed between two date calls: $((t8-t7)) ns"
echo "Time elapsed between two date calls: $((t9-t8)) ns"
echo "Time elapsed between two date calls: $((t10-t9)) ns"
echo "Time elapsed between two date calls: $((t11-t10)) ns"
echo "Time elapsed between two date calls: $((t12-t11)) ns"

(
t1=$(_date)
for i in $(seq 2000); do
  if exec 3<>/dev/tcp/"$HOST"/"$PORT"; then
    printf "GET %s HTTP/1.0\r\nHost: %s\r\nConnection: close\r\n\r\n" "$URL_PATH" "$HOST" >&3
    read -r _ status_code _ <&3
    exec 3>&-
    if [[ "$status_code" == "200" ]]; then
      echo "ERROR: Should not reach here"
      break
    fi
  fi
  # Spin here and do nothing rather waiting some arbitrary unlucky timing
done
t2=$(_date)
echo "Average time per failed request: $(( (t2-t1) / 2000 )) ns"
) 2>/dev/null

(
t1=$(_date)
for i in $(seq 2000); do
  curl -s -o /dev/null -w ''%{http_code}'' $TARGET_URL > /dev/null
done
t2=$(_date)
echo "Average time per failed curl request: $(( (t2-t1) / 2000 )) ns"
) 2>/dev/null

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

(
t1=$(_date)
for i in $(seq 1000); do
  if exec 3<>/dev/tcp/"$HOST"/"$PORT"; then
    printf "GET %s HTTP/1.0\r\nHost: %s\r\nConnection: close\r\n\r\n" "$URL_PATH" "$HOST" >&3
    read -r _ status_code _ <&3
    exec 3>&-
    if [[ "$status_code" != "200" ]]; then
      echo "ERROR: Should not reach here"
      break
    fi
  fi
  # Spin here and do nothing rather waiting some arbitrary unlucky timing
done
t2=$(_date)
echo "Average time per successfull request: $(( (t2-t1) / 1000 )) ns"
) 2>/dev/null

(
t1=$(_date)
for i in $(seq 1000); do
  curl -s -o /dev/null -w ''%{http_code}'' $TARGET_URL > /dev/null
done
t2=$(_date)
echo "Average time per successfull curl request: $(( (t2-t1) / 1000 )) ns"
) 2>/dev/null

# Ensure cleanup on exit (e.g. on timeout)
trap "kill -15 $APP_PID $CURL_PID 2>/dev/null; wait $APP_PID 2>/dev/null; rm -f $END_TS_FILE" EXIT

# Wait for the client loop to get a successful response
wait $CURL_PID 2>/dev/null

TTFR=$((($(cat "$END_TS_FILE") - ts)/1000000))
echo "${TTFR}"
