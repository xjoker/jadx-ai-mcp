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
import java.util.WeakHashMap;

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

    // Per-ClassNode snapshot caches. WeakHashMap keys are JavaClass instances; when a class is
    // garbage-collected the corresponding entry is automatically evicted, so we don't pin memory.
    // Both maps are guarded by their own monitors (synchronised on the map itself) so concurrent
    // reads from different threads don't corrupt state.
    private static final WeakHashMap<JavaClass, List<MethodInfoSnapshot>> methodSnapshotCache =
            new WeakHashMap<>();
    private static final WeakHashMap<JavaClass, List<FieldInfoSnapshot>> fieldSnapshotCache =
            new WeakHashMap<>();

    /**
     * Invalidates the snapshot cache entries for {@code cls} (both method and field lists).
     * Call this whenever the class is renamed so subsequent callers get fresh data.
     */
    public static void invalidateSnapshots(JavaClass cls) {
        if (cls == null) {
            return;
        }
        synchronized (methodSnapshotCache) {
            methodSnapshotCache.remove(cls);
        }
        synchronized (fieldSnapshotCache) {
            fieldSnapshotCache.remove(cls);
        }
    }

    /** Clears all snapshot cache entries (e.g. on full project reload). */
    public static void clearAllSnapshotCaches() {
        synchronized (methodSnapshotCache) {
            methodSnapshotCache.clear();
        }
        synchronized (fieldSnapshotCache) {
            fieldSnapshotCache.clear();
        }
    }

    public static String getClassAliasName(JavaClass cls) {
        return cls != null ? cls.getFullName() : null;
    }

    public static String getClassRawName(JavaClass cls) {
        return cls != null ? cls.getRawName() : null;
    }

    public static String getClassAliasSimpleName(JavaClass cls) {
        return cls != null ? cls.getName() : null;
    }

    public static String getClassRawSimpleName(JavaClass cls) {
        ClassNode classNode = getInternalClassNode(cls);
        return classNode != null && classNode.getClassInfo() != null
            ? classNode.getClassInfo().getShortName()
            : null;
    }

    public static boolean matchesClassName(JavaClass cls, String requestedName) {
        return matchesValue(requestedName, getClassAliasName(cls), false)
            || matchesValue(requestedName, getClassRawName(cls), false);
    }

    public static AccessInfo getAccessFlags(JavaClass cls) {
        ClassNode classNode = getInternalClassNode(cls);
        return classNode != null ? classNode.getAccessFlags() : null;
    }

    public static MethodInfoSnapshot getMethodInfo(JavaMethod method) {
        return buildMethodInfo(getInternalMethodNode(method));
    }

    public static String getMethodAliasName(JavaMethod method) {
        return method != null ? method.getName() : null;
    }

    public static String getMethodRawName(JavaMethod method) {
        MethodNode methodNode = getInternalMethodNode(method);
        return methodNode != null && methodNode.getMethodInfo() != null
            ? methodNode.getMethodInfo().getName()
            : null;
    }

    public static String getMethodFullId(JavaMethod method) {
        MethodNode methodNode = getInternalMethodNode(method);
        return methodNode != null && methodNode.getMethodInfo() != null
            ? methodNode.getMethodInfo().getFullId()
            : null;
    }

    public static String getMethodRawFullId(JavaMethod method) {
        MethodNode methodNode = getInternalMethodNode(method);
        return methodNode != null && methodNode.getMethodInfo() != null
            ? methodNode.getMethodInfo().getRawFullId()
            : null;
    }

    public static boolean matchesMethodName(JavaMethod method, String requestedName) {
        return matchesValue(requestedName, getMethodAliasName(method), true)
            || matchesValue(requestedName, getMethodRawName(method), true)
            || matchesValue(requestedName, getMethodFullId(method), true)
            || matchesValue(requestedName, getMethodRawFullId(method), true);
    }

    /**
     * Returns true when {@code method}'s JVM short descriptor (e.g. {@code "foo(I)V"}) matches
     * {@code descriptor} using case-sensitive exact comparison.
     *
     * <p>The short descriptor is available via {@link jadx.core.dex.info.MethodInfo#getShortId()}
     * and has the form {@code name(arg-types)return-type}, e.g. {@code "process(Ljava/lang/String;I)Z"}.
     * Pass {@code null} to skip descriptor filtering (match-all).</p>
     */
    public static boolean matchesMethodDescriptor(JavaMethod method, String descriptor) {
        if (descriptor == null || descriptor.isEmpty()) {
            return true; // no filter — match everything
        }
        MethodNode methodNode = getInternalMethodNode(method);
        if (methodNode == null || methodNode.getMethodInfo() == null) {
            return false;
        }
        String shortId = methodNode.getMethodInfo().getShortId();
        return descriptor.equals(shortId);
    }

    /**
     * Same as {@link #matchesMethodDescriptor(JavaMethod, String)} but operates on a
     * {@link MethodInfoSnapshot} so callers that only have snapshot data can filter without
     * needing to acquire the full {@link JavaMethod}.
     */
    public static boolean matchesMethodDescriptor(MethodInfoSnapshot snapshot, String descriptor) {
        if (descriptor == null || descriptor.isEmpty()) {
            return true;
        }
        return descriptor.equals(snapshot.getShortId());
    }

    public static String getFieldType(JavaField field) {
        FieldNode fieldNode = getInternalFieldNode(field);
        return fieldNode != null && fieldNode.getType() != null ? fieldNode.getType().toString() : null;
    }

    public static String getFieldAliasName(JavaField field) {
        return field != null ? field.getName() : null;
    }

    public static String getFieldRawName(JavaField field) {
        return field != null ? field.getRawName() : null;
    }

    public static String getFieldRawFullId(JavaField field) {
        FieldNode fieldNode = getInternalFieldNode(field);
        return fieldNode != null && fieldNode.getFieldInfo() != null
            ? fieldNode.getFieldInfo().getRawFullId()
            : null;
    }

    public static boolean matchesFieldName(JavaField field, String requestedName) {
        return matchesValue(requestedName, getFieldAliasName(field), false)
            || matchesValue(requestedName, getFieldRawName(field), false)
            || matchesValue(requestedName, getFieldRawFullId(field), false);
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
        if (cls == null) {
            return Collections.emptyList();
        }
        synchronized (methodSnapshotCache) {
            List<MethodInfoSnapshot> cached = methodSnapshotCache.get(cls);
            if (cached != null) {
                return cached;
            }
        }

        ClassNode classNode = getInternalClassNode(cls);
        if (classNode == null || classNode.getMethods() == null || classNode.getMethods().isEmpty()) {
            return Collections.emptyList();
        }

        List<MethodInfoSnapshot> methods = new ArrayList<>(classNode.getMethods().size());
        for (MethodNode methodNode : classNode.getMethods()) {
            methods.add(buildMethodInfo(methodNode));
        }
        List<MethodInfoSnapshot> immutable = Collections.unmodifiableList(methods);
        synchronized (methodSnapshotCache) {
            methodSnapshotCache.put(cls, immutable);
        }
        return immutable;
    }

    public static List<FieldInfoSnapshot> getDeclaredFieldInfos(JavaClass cls) {
        if (cls == null) {
            return Collections.emptyList();
        }
        synchronized (fieldSnapshotCache) {
            List<FieldInfoSnapshot> cached = fieldSnapshotCache.get(cls);
            if (cached != null) {
                return cached;
            }
        }

        ClassNode classNode = getInternalClassNode(cls);
        if (classNode == null || classNode.getFields() == null || classNode.getFields().isEmpty()) {
            return Collections.emptyList();
        }

        List<FieldInfoSnapshot> fields = new ArrayList<>(classNode.getFields().size());
        for (FieldNode fieldNode : classNode.getFields()) {
            fields.add(buildFieldInfo(fieldNode));
        }
        List<FieldInfoSnapshot> immutable = Collections.unmodifiableList(fields);
        synchronized (fieldSnapshotCache) {
            fieldSnapshotCache.put(cls, immutable);
        }
        return immutable;
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
            methodNode.getMethodInfo().getName(),
            methodNode.getAlias(),
            methodNode.getMethodInfo().getDeclClass().getFullName(),
            methodNode.getMethodInfo().getFullName(),
            methodNode.getMethodInfo().getAliasFullName(),
            methodNode.getMethodInfo().getFullId(),
            methodNode.getMethodInfo().getRawFullId(),
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
            fieldNode.getFieldInfo().getName(),
            fieldNode.getAlias(),
            fieldNode.getFieldInfo().getRawFullId(),
            fieldNode.getType() != null ? fieldNode.getType().toString() : null,
            fieldNode.getAccessFlags()
        );
    }

    public static final class MethodInfoSnapshot {
        private final String name;
        private final String aliasName;
        private final String declaringClassName;
        private final String fullName;
        private final String aliasFullName;
        private final String fullId;
        private final String rawFullId;
        private final String shortId;
        private final ArgType returnType;
        private final List<ArgType> argumentTypes;
        private final AccessInfo accessFlags;
        private final boolean constructor;
        private final boolean classInit;
        private final Integer basicBlockCount;

        private MethodInfoSnapshot(
            String name,
            String aliasName,
            String declaringClassName,
            String fullName,
            String aliasFullName,
            String fullId,
            String rawFullId,
            String shortId,
            ArgType returnType,
            List<ArgType> argumentTypes,
            AccessInfo accessFlags,
            boolean constructor,
            boolean classInit,
            Integer basicBlockCount
        ) {
            this.name = name;
            this.aliasName = aliasName;
            this.declaringClassName = declaringClassName;
            this.fullName = fullName;
            this.aliasFullName = aliasFullName;
            this.fullId = fullId;
            this.rawFullId = rawFullId;
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

        public String getRawName() {
            return name;
        }

        public String getAliasName() {
            return aliasName;
        }

        public String getFullName() {
            return fullName;
        }

        public String getAliasFullName() {
            return aliasFullName;
        }

        public String getDeclaringClassName() {
            return declaringClassName;
        }

        public String getFullId() {
            return fullId;
        }

        public String getRawFullId() {
            return rawFullId;
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
        private final String aliasName;
        private final String rawFullId;
        private final String type;
        private final AccessInfo accessFlags;

        private FieldInfoSnapshot(String name, String aliasName, String rawFullId, String type, AccessInfo accessFlags) {
            this.name = name;
            this.aliasName = aliasName;
            this.rawFullId = rawFullId;
            this.type = type;
            this.accessFlags = accessFlags;
        }

        public String getName() {
            return name;
        }

        public String getRawName() {
            return name;
        }

        public String getAliasName() {
            return aliasName;
        }

        public String getRawFullId() {
            return rawFullId;
        }

        public String getType() {
            return type;
        }

        public AccessInfo getAccessFlags() {
            return accessFlags;
        }
    }

    private static boolean matchesValue(String requestedValue, String candidateValue, boolean ignoreCase) {
        if (requestedValue == null || requestedValue.isEmpty() || candidateValue == null || candidateValue.isEmpty()) {
            return false;
        }
        return ignoreCase ? candidateValue.equalsIgnoreCase(requestedValue) : candidateValue.equals(requestedValue);
    }
}
