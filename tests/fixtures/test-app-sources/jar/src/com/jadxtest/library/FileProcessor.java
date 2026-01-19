package com.jadxtest.library;

import java.io.*;
import java.util.ArrayList;
import java.util.List;

/**
 * File processor for testing import detection and code search.
 * Tests: get_class_source, get_imports, search_by_code
 */
public class FileProcessor {
    
    private final String basePath;
    private List<String> processedFiles = new ArrayList<>();
    
    public FileProcessor(String basePath) {
        this.basePath = basePath;
    }
    
    /**
     * Read file content
     */
    public String readFile(String filename) throws IOException {
        File file = new File(basePath, filename);
        StringBuilder content = new StringBuilder();
        
        try (BufferedReader reader = new BufferedReader(new FileReader(file))) {
            String line;
            while ((line = reader.readLine()) != null) {
                content.append(line).append("\n");
            }
        }
        
        processedFiles.add(filename);
        return content.toString();
    }
    
    /**
     * Write content to file
     */
    public void writeFile(String filename, String content) throws IOException {
        File file = new File(basePath, filename);
        
        try (BufferedWriter writer = new BufferedWriter(new FileWriter(file))) {
            writer.write(content);
        }
        
        processedFiles.add(filename);
    }
    
    /**
     * Copy file
     */
    public void copyFile(String source, String dest) throws IOException {
        String content = readFile(source);
        writeFile(dest, content);
    }
    
    /**
     * Get list of processed files
     */
    public List<String> getProcessedFiles() {
        return new ArrayList<>(processedFiles);
    }
}
