#!/bin/bash
# jadx-gui wrapper script
# Auto-loads /apks/target.apk if exists, otherwise starts empty

TARGET_APK="/apks/target.apk"

if [ -f "$TARGET_APK" ]; then
    echo "Auto-loading APK: $TARGET_APK"
    exec /opt/jadx/bin/jadx-gui "$TARGET_APK"
else
    echo "No target.apk found, starting jadx-gui without file"
    exec /opt/jadx/bin/jadx-gui
fi
