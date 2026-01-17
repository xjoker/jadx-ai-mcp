#!/bin/bash
# jadx-gui wrapper script
# Auto-loads target file from /apks/ if exists, otherwise starts empty
# Supports: JAR, APK, AAR, DEX (priority: JAR > APK > AAR > DEX)
# NOTE: --rename-flags none disables auto-renaming for accurate Hook development

TARGET_JAR="/apks/target.jar"
TARGET_APK="/apks/target.apk"
TARGET_AAR="/apks/target.aar"
TARGET_DEX="/apks/target.dex"

# Priority: JAR > APK > AAR > DEX
if [ -f "$TARGET_JAR" ]; then
    echo "Auto-loading JAR: $TARGET_JAR"
    exec /opt/jadx/bin/jadx-gui --rename-flags none "$TARGET_JAR"
elif [ -f "$TARGET_APK" ]; then
    echo "Auto-loading APK: $TARGET_APK"
    exec /opt/jadx/bin/jadx-gui --rename-flags none "$TARGET_APK"
elif [ -f "$TARGET_AAR" ]; then
    echo "Auto-loading AAR: $TARGET_AAR"
    exec /opt/jadx/bin/jadx-gui --rename-flags none "$TARGET_AAR"
elif [ -f "$TARGET_DEX" ]; then
    echo "Auto-loading DEX: $TARGET_DEX"
    exec /opt/jadx/bin/jadx-gui --rename-flags none "$TARGET_DEX"
else
    echo "No target file found (JAR/APK/AAR/DEX), starting jadx-gui without file"
    exec /opt/jadx/bin/jadx-gui --rename-flags none
fi
