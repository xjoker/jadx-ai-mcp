package com.zin.jadxaimcp.utils;

import jadx.core.dex.instructions.args.ArgType;
import jadx.core.dex.instructions.args.PrimitiveType;

import java.util.List;
import java.util.stream.Collectors;

/**
 * Utility class for converting JADX ArgType to Frida-compatible type strings.
 * 
 * Frida uses JVM internal format for array types:
 * - int[] -> "[I"
 * - String[] -> "[Ljava.lang.String;"
 * - int[][] -> "[[I"
 * 
 * For primitive types, Frida uses the Java type name:
 * - int -> "int"
 * - boolean -> "boolean"
 * 
 * For object types, Frida uses fully qualified class names:
 * - String -> "java.lang.String"
 */
public class FridaTypeConverter {

    /**
     * Converts a JADX ArgType to a Frida-compatible type string.
     * 
     * @param type The JADX ArgType to convert
     * @return Frida-compatible type string for use in .overload()
     */
    public static String toFridaType(ArgType type) {
        if (type == null) {
            return "void";
        }
        
        // Handle array types - convert to JVM format
        if (type.isArray()) {
            int dimension = type.getArrayDimension();
            ArgType rootElement = type.getArrayRootElement();
            String prefix = "[".repeat(dimension);
            
            if (rootElement.isPrimitive()) {
                // Primitive arrays: [I, [Z, [[B, etc.
                return prefix + getPrimitiveShortName(rootElement.getPrimitiveType());
            } else if (rootElement.isObject()) {
                // Object arrays: [Ljava.lang.String;
                return prefix + "L" + rootElement.getObject() + ";";
            } else {
                // Unknown array element type
                return prefix + "Ljava.lang.Object;";
            }
        }
        
        // Handle primitive types - use Java type names
        if (type.isPrimitive()) {
            return type.getPrimitiveType().toString().toLowerCase();
        }
        
        // Handle object types - use fully qualified names
        if (type.isObject()) {
            return type.getObject();
        }
        
        // Fallback for unknown types
        return type.toString();
    }

    /**
     * Converts a list of ArgTypes to a Frida overload string.
     * 
     * @param types List of argument types
     * @return Formatted string for Frida .overload(), e.g., "'java.lang.String', 'int'"
     */
    public static String toFridaOverloadString(List<ArgType> types) {
        if (types == null || types.isEmpty()) {
            return "";
        }
        
        return types.stream()
            .map(FridaTypeConverter::toFridaType)
            .map(t -> "'" + t + "'")
            .collect(Collectors.joining(", "));
    }

    /**
     * Generates a Frida hook template for a method.
     * 
     * @param className Fully qualified class name
     * @param methodName Method name
     * @param argTypes List of argument types
     * @param isConstructor Whether this is a constructor
     * @return Frida hook code template
     */
    public static String generateHookTemplate(String className, String methodName, 
                                               List<ArgType> argTypes, boolean isConstructor) {
        String overloadStr = toFridaOverloadString(argTypes);
        String targetMethod = isConstructor ? "$init" : methodName;
        
        // Generate parameter names
        StringBuilder paramNames = new StringBuilder();
        for (int i = 0; i < argTypes.size(); i++) {
            if (i > 0) paramNames.append(", ");
            paramNames.append("arg").append(i);
        }
        
        StringBuilder template = new StringBuilder();
        template.append("var clazz = Java.use('").append(className).append("');\n");
        template.append("clazz.").append(targetMethod);
        
        if (!overloadStr.isEmpty()) {
            template.append(".overload(").append(overloadStr).append(")");
        }
        
        template.append(".implementation = function(").append(paramNames).append(") {\n");
        template.append("    console.log('").append(methodName).append(" called');\n");
        template.append("    // TODO: Add your hook logic here\n");
        template.append("    return this.").append(targetMethod).append("(").append(paramNames).append(");\n");
        template.append("};");
        
        return template.toString();
    }

    /**
     * Gets the JVM short name for a primitive type.
     * 
     * @param type The primitive type
     * @return Single character JVM type descriptor
     */
    private static String getPrimitiveShortName(PrimitiveType type) {
        switch (type) {
            case INT:
                return "I";
            case BOOLEAN:
                return "Z";
            case BYTE:
                return "B";
            case SHORT:
                return "S";
            case CHAR:
                return "C";
            case LONG:
                return "J";
            case FLOAT:
                return "F";
            case DOUBLE:
                return "D";
            case VOID:
                return "V";
            default:
                return "L";
        }
    }
}
