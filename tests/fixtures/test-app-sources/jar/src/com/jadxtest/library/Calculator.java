package com.jadxtest.library;

/**
 * Simple calculator for testing JADX MCP tools.
 * Tests: get_class_source, get_methods, get_fields
 */
public class Calculator {
    
    // Test field detection
    private int lastResult = 0;
    public static final String VERSION = "1.0.0";
    
    /**
     * Add two numbers
     */
    public int add(int a, int b) {
        lastResult = a + b;
        return lastResult;
    }
    
    /**
     * Subtract two numbers
     */
    public int subtract(int a, int b) {
        lastResult = a - b;
        return lastResult;
    }
    
    /**
     * Multiply two numbers
     */
    public int multiply(int a, int b) {
        lastResult = a * b;
        return lastResult;
    }
    
    /**
     * Divide two numbers
     * @throws ArithmeticException if divisor is zero
     */
    public int divide(int a, int b) {
        if (b == 0) {
            throw new ArithmeticException("Division by zero");
        }
        lastResult = a / b;
        return lastResult;
    }
    
    /**
     * Get the last calculation result
     */
    public int getLastResult() {
        return lastResult;
    }
}
