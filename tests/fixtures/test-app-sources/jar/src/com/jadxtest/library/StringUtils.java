package com.jadxtest.library;

/**
 * String utilities for testing search functionality.
 * Tests: get_strings, search_by_code
 */
public class StringUtils {
    
    // Test string detection
    public static final String APP_NAME = "JADX Test Library";
    public static final String ERROR_EMPTY = "Input cannot be empty";
    public static final String ERROR_NULL = "Input cannot be null";
    private static final String SECRET_KEY = "sk_test_12345678";
    
    /**
     * Check if string is empty or null
     */
    public static boolean isEmpty(String str) {
        return str == null || str.trim().isEmpty();
    }
    
    /**
     * Reverse a string
     */
    public static String reverse(String str) {
        if (str == null) {
            throw new IllegalArgumentException(ERROR_NULL);
        }
        return new StringBuilder(str).reverse().toString();
    }
    
    /**
     * Count occurrences of a character
     */
    public static int countChar(String str, char c) {
        if (isEmpty(str)) {
            return 0;
        }
        int count = 0;
        for (char ch : str.toCharArray()) {
            if (ch == c) {
                count++;
            }
        }
        return count;
    }
    
    /**
     * Encrypt using simple XOR (for testing purposes)
     */
    public static String encrypt(String data) {
        if (data == null) return null;
        StringBuilder result = new StringBuilder();
        for (int i = 0; i < data.length(); i++) {
            result.append((char) (data.charAt(i) ^ SECRET_KEY.charAt(i % SECRET_KEY.length())));
        }
        return result.toString();
    }
}
