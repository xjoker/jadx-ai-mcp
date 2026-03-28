package com.zin.jadxaimcp.utils;

import jadx.api.JadxArgs;
import jadx.api.ResourceFile;
import jadx.gui.JadxWrapper;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/**
 * Utility class for detecting file types loaded in JADX.
 * 
 * Supports APK, JAR, DEX, AAR, and class files.
 * Provides information about Android-specific features and Smali availability.
 * 
 * @author JADX AI MCP Team
 */
public class FileTypeDetector {
    private static final Logger logger = LoggerFactory.getLogger(FileTypeDetector.class);
    private static final ManifestInfoService manifestInfoService = ManifestInfoService.getInstance();

    /**
     * File types supported by JADX
     */
    public enum FileType {
        APK("apk", true, true),
        AAR("aar", true, true),
        DEX("dex", false, true),
        JAR("jar", false, false),
        CLASS("class", false, false),
        UNKNOWN("unknown", false, false);

        private final String name;
        private final boolean androidFeatures;
        private final boolean smaliAvailable;

        FileType(String name, boolean androidFeatures, boolean smaliAvailable) {
            this.name = name;
            this.androidFeatures = androidFeatures;
            this.smaliAvailable = smaliAvailable;
        }

        public String getName() { return name; }
        public boolean hasAndroidFeatures() { return androidFeatures; }
        public boolean isSmaliAvailable() { return smaliAvailable; }
    }

    /**
     * Result of file type detection
     */
    public static class DetectionResult {
        private final List<FileType> fileTypes;
        private final List<String> filePaths;
        private final boolean androidFeatures;
        private final boolean smaliAvailable;

        public DetectionResult(List<FileType> fileTypes, List<String> filePaths) {
            this.fileTypes = fileTypes;
            this.filePaths = filePaths;
            
            // Android features available if ANY file supports them
            this.androidFeatures = fileTypes.stream().anyMatch(FileType::hasAndroidFeatures);
            // Smali available if ANY file supports it
            this.smaliAvailable = fileTypes.stream().anyMatch(FileType::isSmaliAvailable);
        }

        public List<FileType> getFileTypes() { return fileTypes; }
        public List<String> getFilePaths() { return filePaths; }
        public boolean hasAndroidFeatures() { return androidFeatures; }
        public boolean isSmaliAvailable() { return smaliAvailable; }

        /**
         * Returns primary file type (first detected)
         */
        public FileType getPrimaryType() {
            return fileTypes.isEmpty() ? FileType.UNKNOWN : fileTypes.get(0);
        }

        /**
         * Converts result to Map for JSON serialization
         */
        public Map<String, Object> toMap() {
            Map<String, Object> map = new HashMap<>();
            
            if (fileTypes.size() == 1) {
                map.put("file_type", fileTypes.get(0).getName());
            } else {
                List<String> typeNames = new ArrayList<>();
                for (FileType ft : fileTypes) {
                    typeNames.add(ft.getName());
                }
                map.put("file_types", typeNames);
                map.put("file_type", getPrimaryType().getName());
            }
            
            map.put("android_features", androidFeatures);
            map.put("smali_available", smaliAvailable);
            
            return map;
        }

        /**
         * Returns list of unavailable tools for AI guidance
         */
        public List<String> getUnavailableTools() {
            List<String> tools = new ArrayList<>();
            
            if (!androidFeatures) {
                tools.add("get_android_manifest");
                tools.add("get_main_activity_class");
                tools.add("get_strings");
            }
            
            if (!smaliAvailable) {
                tools.add("get_smali_of_class");
            }
            
            return tools;
        }
    }

    /**
     * Detects file type from JADX wrapper
     */
    public static DetectionResult detect(JadxWrapper wrapper) {
        List<FileType> types = new ArrayList<>();
        List<String> paths = new ArrayList<>();

        try {
            if (wrapper == null || wrapper.getDecompiler() == null) {
                return new DetectionResult(types, paths);
            }

            JadxArgs args = wrapper.getDecompiler().getArgs();
            if (args == null) {
                return new DetectionResult(types, paths);
            }

            List<File> inputFiles = args.getInputFiles();
            if (inputFiles == null || inputFiles.isEmpty()) {
                // Fallback: check if resources exist (indicates APK/AAR)
                List<ResourceFile> resources = wrapper.getResources();
                if (resources != null && !resources.isEmpty()) {
                    ResourceFile manifest = manifestInfoService.getManifestFile(wrapper);
                    if (manifest != null) {
                        types.add(FileType.APK);
                        paths.add("(detected from manifest)");
                    }
                }
                return new DetectionResult(types, paths);
            }

            for (File file : inputFiles) {
                paths.add(file.getAbsolutePath());

                // Use magic number detection for accurate file type identification
                FileType detectedType = detectFileType(file);
                types.add(detectedType);
            }

        } catch (Exception e) {
            logger.warn("Failed to detect file type: {}", e.getMessage());
        }

        return new DetectionResult(types, paths);
    }

    /**
     * Detects file type by extension
     */
    private static FileType detectByExtension(String fileName) {
        if (fileName.endsWith(".apk")) {
            return FileType.APK;
        } else if (fileName.endsWith(".aar")) {
            return FileType.AAR;
        } else if (fileName.endsWith(".dex")) {
            return FileType.DEX;
        } else if (fileName.endsWith(".jar")) {
            return FileType.JAR;
        } else if (fileName.endsWith(".class")) {
            return FileType.CLASS;
        }
        return FileType.UNKNOWN;
    }

    /**
     * Checks if a ZIP/JAR file contains DEX files (making it effectively an APK)
     */
    private static boolean containsDex(File file) {
        if (!file.exists() || !file.canRead()) {
            return false;
        }

        try (ZipInputStream zis = new ZipInputStream(new FileInputStream(file))) {
            ZipEntry entry;
            while ((entry = zis.getNextEntry()) != null) {
                String name = entry.getName().toLowerCase();
                if (name.equals("classes.dex") || name.startsWith("classes") && name.endsWith(".dex")) {
                    return true;
                }
                if (name.equals("androidmanifest.xml")) {
                    return true;
                }
            }
        } catch (IOException e) {
            logger.debug("Failed to check ZIP contents for {}: {}", file.getName(), e.getMessage());
        }
        
        return false;
    }

    // Magic number constants
    private static final byte[] MAGIC_DEX = {0x64, 0x65, 0x78, 0x0A};  // "dex\n"
    private static final byte[] MAGIC_ZIP = {0x50, 0x4B, 0x03, 0x04};  // "PK\x03\x04"
    private static final byte[] MAGIC_CLASS = {(byte) 0xCA, (byte) 0xFE, (byte) 0xBA, (byte) 0xBE};

    /**
     * Detects file type by magic number (file header bytes).
     * 
     * This is more reliable than extension-based detection as it
     * prevents extension spoofing (e.g., APK renamed to .jar).
     * 
     * @param file File to detect
     * @return Detected file type, or null if magic number doesn't match known types
     */
    private static FileType detectByMagic(File file) {
        if (!file.exists() || !file.canRead() || file.length() < 4) {
            return null;
        }

        byte[] header = new byte[4];
        try (FileInputStream fis = new FileInputStream(file)) {
            if (fis.read(header) != 4) {
                return null;
            }
        } catch (IOException e) {
            logger.debug("Failed to read file header for {}: {}", file.getName(), e.getMessage());
            return null;
        }

        // Check DEX magic
        if (matchesMagic(header, MAGIC_DEX)) {
            return FileType.DEX;
        }

        // Check ZIP magic (APK, AAR, JAR are all ZIP files)
        if (matchesMagic(header, MAGIC_ZIP)) {
            // Need to check contents to distinguish APK/AAR from JAR
            if (containsDex(file)) {
                // Has DEX or AndroidManifest, likely APK
                String fileName = file.getName().toLowerCase();
                if (fileName.endsWith(".aar")) {
                    return FileType.AAR;
                }
                return FileType.APK;
            }
            return FileType.JAR;
        }

        // Check CLASS file magic
        if (matchesMagic(header, MAGIC_CLASS)) {
            return FileType.CLASS;
        }

        return null;
    }

    /**
     * Checks if header bytes match the given magic number
     */
    private static boolean matchesMagic(byte[] header, byte[] magic) {
        if (header.length < magic.length) {
            return false;
        }
        for (int i = 0; i < magic.length; i++) {
            if (header[i] != magic[i]) {
                return false;
            }
        }
        return true;
    }

    /**
     * Detects file type using both magic number and extension.
     * Magic number takes precedence for security.
     * 
     * @param file File to detect
     * @return Detected file type
     */
    public static FileType detectFileType(File file) {
        // Try magic number first (more secure)
        FileType magicType = detectByMagic(file);
        if (magicType != null) {
            // Warn if extension doesn't match magic
            String fileName = file.getName().toLowerCase();
            FileType extType = detectByExtension(fileName);
            if (extType != FileType.UNKNOWN && extType != magicType) {
                logger.warn("File {} has extension for {} but magic indicates {}",
                    file.getName(), extType.getName(), magicType.getName());
            }
            return magicType;
        }

        // Fallback to extension
        return detectByExtension(file.getName().toLowerCase());
    }
}
