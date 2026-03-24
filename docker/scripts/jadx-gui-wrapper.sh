#!/bin/bash
# jadx-gui wrapper script
# Auto-loads target file from /apks/ if exists, otherwise starts empty
# Supports: JAR, APK, AAR, DEX (priority: JAR > APK > AAR > DEX)
# NOTE: --rename-flags none disables auto-renaming for accurate Hook development
#
# OOM recovery: -XX:+ExitOnOutOfMemoryError causes exit(3) on OOM.
# This wrapper detects previous OOM crashes and skips auto-loading
# to prevent an infinite OOM→restart→OOM loop.
#
# Signal handling: JADX runs as a background child so the wrapper can
# forward SIGTERM/SIGINT (from docker stop / supervisord) and still
# capture the exit code for OOM flag logic.

export JAVA_OPTS="${JAVA_OPTS} -XX:+ExitOnOutOfMemoryError"

OOM_FLAG="/tmp/.jadx-oom-crash"
JADX_PID=""

# Forward SIGTERM/SIGINT to child JVM for graceful shutdown
_term() {
    if [ -n "$JADX_PID" ]; then
        kill -TERM "$JADX_PID" 2>/dev/null
    fi
}
trap _term TERM INT

# Start JADX as background child, then wait for it
start_jadx() {
    "$@" &
    JADX_PID=$!
    wait "$JADX_PID"
    EXIT_CODE=$?
    JADX_PID=""
    return $EXIT_CODE
}

# If previous run OOM-crashed, start empty to break the loop
if [ -f "$OOM_FLAG" ]; then
    echo "================================================"
    echo "  WARNING: Previous JADX run crashed with OutOfMemoryError"
    echo "  Starting WITHOUT auto-loading to prevent OOM loop."
    echo ""
    echo "  To recover:"
    echo "    1. Increase container memory or JAVA_OPTS -Xmx"
    echo "    2. Remove $OOM_FLAG (or restart container)"
    echo "    3. Load file manually via noVNC GUI"
    echo "================================================"
    rm -f "$OOM_FLAG"
    start_jadx /opt/jadx/bin/jadx-gui --rename-flags none
else
    TARGET_JAR="/apks/target.jar"
    TARGET_APK="/apks/target.apk"
    TARGET_AAR="/apks/target.aar"
    TARGET_DEX="/apks/target.dex"

    # Determine target file (priority: JAR > APK > AAR > DEX)
    TARGET=""
    if [ -f "$TARGET_JAR" ]; then
        TARGET="$TARGET_JAR"
    elif [ -f "$TARGET_APK" ]; then
        TARGET="$TARGET_APK"
    elif [ -f "$TARGET_AAR" ]; then
        TARGET="$TARGET_AAR"
    elif [ -f "$TARGET_DEX" ]; then
        TARGET="$TARGET_DEX"
    fi

    if [ -n "$TARGET" ]; then
        echo "Auto-loading: $TARGET"
        start_jadx /opt/jadx/bin/jadx-gui --rename-flags none "$TARGET"
    else
        echo "No target file found (JAR/APK/AAR/DEX), starting jadx-gui without file"
        start_jadx /opt/jadx/bin/jadx-gui --rename-flags none
    fi
fi

EXIT_CODE=$?

# exit(3) = -XX:+ExitOnOutOfMemoryError triggered
if [ "$EXIT_CODE" -eq 3 ]; then
    echo "JADX exited with code 3 (OutOfMemoryError). Setting OOM flag."
    date -u +"%Y-%m-%dT%H:%M:%SZ" > "$OOM_FLAG"
fi

exit $EXIT_CODE
