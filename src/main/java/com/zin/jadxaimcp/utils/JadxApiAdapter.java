package com.zin.jadxaimcp.utils;

import jadx.api.JavaClass;
import jadx.api.JavaField;
import jadx.api.JavaMethod;
import jadx.core.dex.info.AccessInfo;
import jadx.core.dex.instructions.args.ArgType;
import jadx.core.dex.nodes.ClassNode;
import jadx.core.dex.nodes.FieldNode;
import jadx.core.dex.nodes.MethodNode;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * Centralizes all access to JADX internal node APIs.
 *
 * <p>Upstream marks JavaClass#getClassNode(), JavaMethod#getMethodNode() and
 * JavaField#getFieldNode() as internal and not stable. Keep all such calls isolated here and
 * prefer the public JavaClass/JavaMethod/JavaField APIs everywhere else.</p>
 */
public final class JadxApiAdapter {
    private JadxApiAdapter() {
    }

    public static AccessInfo getAccessFlags(JavaClass cls) {
        ClassNode classNode = getInternalClassNode(cls);
        return classNode != null ? classNode.getAccessFlags() : null;
    }

    public static MethodInfoSnapshot getMethodInfo(JavaMethod method) {
        return buildMethodInfo(getInternalMethodNode(method));
    }

    public static String getFieldType(JavaField field) {
        FieldNode fieldNode = getInternalFieldNode(field);
        return fieldNode != null && fieldNode.getType() != null ? fieldNode.getType().toString() : null;
    }

    public static String getSuperClass(JavaClass cls) {
        ClassNode classNode = getInternalClassNode(cls);
        return classNode != null && classNode.getSuperClass() != null
            ? classNode.getSuperClass().toString()
            : null;
    }

    public static List<String> getInterfaces(JavaClass cls) {
        ClassNode classNode = getInternalClassNode(cls);
        if (classNode == null || classNode.getInterfaces() == null || classNode.getInterfaces().isEmpty()) {
            return Collections.emptyList();
        }

        List<String> interfaces = new ArrayList<>(classNode.getInterfaces().size());
        for (ArgType iface : classNode.getInterfaces()) {
            interfaces.add(iface.toString());
        }
        return interfaces;
    }

    public static boolean isProcessComplete(JavaClass cls) {
        ClassNode classNode = getInternalClassNode(cls);
        return classNode != null && classNode.getState().isProcessComplete();
    }

    public static List<MethodInfoSnapshot> getDeclaredMethodInfos(JavaClass cls) {
        ClassNode classNode = getInternalClassNode(cls);
        if (classNode == null || classNode.getMethods() == null || classNode.getMethods().isEmpty()) {
            return Collections.emptyList();
        }

        List<MethodInfoSnapshot> methods = new ArrayList<>(classNode.getMethods().size());
        for (MethodNode methodNode : classNode.getMethods()) {
            methods.add(buildMethodInfo(methodNode));
        }
        return methods;
    }

    public static List<FieldInfoSnapshot> getDeclaredFieldInfos(JavaClass cls) {
        ClassNode classNode = getInternalClassNode(cls);
        if (classNode == null || classNode.getFields() == null || classNode.getFields().isEmpty()) {
            return Collections.emptyList();
        }

        List<FieldInfoSnapshot> fields = new ArrayList<>(classNode.getFields().size());
        for (FieldNode fieldNode : classNode.getFields()) {
            fields.add(buildFieldInfo(fieldNode));
        }
        return fields;
    }

    public static List<JavaMethod> getClassUseInMethods(JavaClass cls) {
        ClassNode classNode = getInternalClassNode(cls);
        if (classNode == null || classNode.getUseInMth() == null || classNode.getUseInMth().isEmpty()) {
            return Collections.emptyList();
        }

        List<JavaMethod> methods = new ArrayList<>(classNode.getUseInMth().size());
        for (MethodNode methodNode : classNode.getUseInMth()) {
            JavaMethod javaMethod = methodNode.getJavaNode();
            if (javaMethod != null) {
                methods.add(javaMethod);
            }
        }
        return methods;
    }

    public static MethodInfoSnapshot getMethodInfo(MethodNode methodNode) {
        return buildMethodInfo(methodNode);
    }

    /**
     * Escape hatch for logic that still needs MethodNode-only capabilities such as instruction
     * walking or reflection over internal semantic usage APIs.
     */
    @SuppressWarnings("JadxInternalApiUsage")
    public static MethodNode getInternalMethodNode(JavaMethod method) {
        return method != null ? method.getMethodNode() : null;
    }

    @SuppressWarnings("JadxInternalApiUsage")
    private static ClassNode getInternalClassNode(JavaClass cls) {
        return cls != null ? cls.getClassNode() : null;
    }

    @SuppressWarnings("JadxInternalApiUsage")
    private static FieldNode getInternalFieldNode(JavaField field) {
        return field != null ? field.getFieldNode() : null;
    }

    @SuppressWarnings("JadxInternalApiUsage")
    private static MethodInfoSnapshot buildMethodInfo(MethodNode methodNode) {
        if (methodNode == null) {
            return null;
        }

        List<ArgType> argumentTypes = methodNode.getMethodInfo().getArgumentsTypes();
        List<ArgType> safeArgumentTypes = argumentTypes == null
            ? Collections.emptyList()
            : new ArrayList<>(argumentTypes);
        Integer basicBlockCount = methodNode.getBasicBlocks() != null
            ? methodNode.getBasicBlocks().size()
            : null;

        return new MethodInfoSnapshot(
            methodNode.getName(),
            methodNode.getMethodInfo().getDeclClass().getFullName(),
            methodNode.getMethodInfo().getFullName(),
            methodNode.getMethodInfo().getFullId(),
            methodNode.getMethodInfo().getShortId(),
            methodNode.getMethodInfo().getReturnType(),
            safeArgumentTypes,
            methodNode.getAccessFlags(),
            methodNode.getMethodInfo().isConstructor(),
            methodNode.getMethodInfo().isClassInit(),
            basicBlockCount
        );
    }

    @SuppressWarnings("JadxInternalApiUsage")
    private static FieldInfoSnapshot buildFieldInfo(FieldNode fieldNode) {
        if (fieldNode == null) {
            return null;
        }

        return new FieldInfoSnapshot(
            fieldNode.getName(),
            fieldNode.getType() != null ? fieldNode.getType().toString() : null,
            fieldNode.getAccessFlags()
        );
    }

    public static final class MethodInfoSnapshot {
        private final String name;
        private final String declaringClassName;
        private final String fullName;
        private final String fullId;
        private final String shortId;
        private final ArgType returnType;
        private final List<ArgType> argumentTypes;
        private final AccessInfo accessFlags;
        private final boolean constructor;
        private final boolean classInit;
        private final Integer basicBlockCount;

        private MethodInfoSnapshot(
            String name,
            String declaringClassName,
            String fullName,
            String fullId,
            String shortId,
            ArgType returnType,
            List<ArgType> argumentTypes,
            AccessInfo accessFlags,
            boolean constructor,
            boolean classInit,
            Integer basicBlockCount
        ) {
            this.name = name;
            this.declaringClassName = declaringClassName;
            this.fullName = fullName;
            this.fullId = fullId;
            this.shortId = shortId;
            this.returnType = returnType;
            this.argumentTypes = Collections.unmodifiableList(argumentTypes);
            this.accessFlags = accessFlags;
            this.constructor = constructor;
            this.classInit = classInit;
            this.basicBlockCount = basicBlockCount;
        }

        public String getName() {
            return name;
        }

        public String getFullName() {
            return fullName;
        }

        public String getDeclaringClassName() {
            return declaringClassName;
        }

        public String getFullId() {
            return fullId;
        }

        public String getShortId() {
            return shortId;
        }

        public ArgType getReturnType() {
            return returnType;
        }

        public List<ArgType> getArgumentTypes() {
            return argumentTypes;
        }

        public AccessInfo getAccessFlags() {
            return accessFlags;
        }

        public boolean isConstructor() {
            return constructor;
        }

        public boolean isClassInit() {
            return classInit;
        }

        public Integer getBasicBlockCount() {
            return basicBlockCount;
        }
    }

    public static final class FieldInfoSnapshot {
        private final String name;
        private final String type;
        private final AccessInfo accessFlags;

        private FieldInfoSnapshot(String name, String type, AccessInfo accessFlags) {
            this.name = name;
            this.type = type;
            this.accessFlags = accessFlags;
        }

        public String getName() {
            return name;
        }

        public String getType() {
            return type;
        }

        public AccessInfo getAccessFlags() {
            return accessFlags;
        }
    }
}
