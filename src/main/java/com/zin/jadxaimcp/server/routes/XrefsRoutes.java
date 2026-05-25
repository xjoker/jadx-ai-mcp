package com.zin.jadxaimcp.server.routes;

import io.javalin.http.Context;

import jadx.api.ICodeInfo;
import jadx.api.JavaClass;
import jadx.api.JavaField;
import jadx.api.JavaMethod;
import jadx.api.JavaNode;
import jadx.api.utils.CodeUtils;
import jadx.gui.JadxWrapper;
import jadx.gui.ui.MainWindow;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Map;
import java.util.HashMap;
import java.util.List;
import java.util.ArrayList;
import java.util.Set;
import java.util.Collections;
import java.util.HashSet;
import java.util.LinkedHashMap;

import com.zin.jadxaimcp.utils.PaginationUtils;
import com.zin.jadxaimcp.utils.PaginationUtils.PaginationException;
import com.zin.jadxaimcp.utils.JadxAIMCPPluginError;
import com.zin.jadxaimcp.utils.ClassCacheManager;
import com.zin.jadxaimcp.utils.JadxApiAdapter;
import com.zin.jadxaimcp.utils.JadxSearchLock;

public class XrefsRoutes {
    private static final Logger logger = LoggerFactory.getLogger(XrefsRoutes.class);
    private final MainWindow mainWindow;
    private final PaginationUtils paginationUtils;

    public XrefsRoutes(MainWindow mainWindow) {
        this.mainWindow = mainWindow;
        this.paginationUtils = new PaginationUtils();
    }

    /**
     * @return void
     * @param Context
     * 
     * This routing method handles the /xrefs-to-class MCP tool call.
     * 1. It validates and retrieves the required 'class' parameter from the request
     * 2. It finds the target class by name using the JADX wrapper
     * 3. It collects all cross-references to the class from:
     *      - Classes that reference the target class
     *      - Methods that reference the target class
     *      - Constructor calls to the target class
     * 4. It builds a map of class names to their referencing methods
     * 5. It aggregates class references and ensures no duplicates are added
     * 6. For each reference, it determines if it's a:
     *      - Method-level reference (includes method details)
     *      - Class-level reference (only class name)
     * 7. It applies pagination to the collected references and returns the result
     * 
     * Note: Constructor references are handled separately to ensure all instantiation points are
     * captured in the cross-reference analysis.
     */
    public void handleXrefsToClass(Context ctx) {
        String className = validateRequiredParam(ctx, "class_name");
        if (className == null) return;

        boolean includeSnippet = "true".equalsIgnoreCase(ctx.queryParam("include_snippet"));
        int contextLines = parseIntParam(ctx.queryParam("context_lines"), 3);

        if (!tryAcquireDecompileLock(ctx)) {
            return;
        }
        try {
            JavaClass targetJavaClass = findClassByName(ctx, className);
            if (targetJavaClass == null) return;

            List<JavaClass> classReferences = new ArrayList<>(extractClasses(targetJavaClass.getUseIn()));
            List<JavaMethod> methodReferences = new ArrayList<>(JadxApiAdapter.getClassUseInMethods(targetJavaClass));

            // Include constructor references
            for (JavaMethod javaMethod : targetJavaClass.getMethods()) {
                if (javaMethod.isConstructor()) {
                    methodReferences.addAll(extractMethods(javaMethod.getUseIn()));
                }
            }

            // Add classes that call constructors
            Set<String> existingClassNames = new HashSet<>();
            for (JavaClass cls : classReferences) {
                existingClassNames.add(cls.getFullName());
            }
            for (JavaMethod mth : methodReferences) {
                JavaClass parentClass = mth.getDeclaringClass();
                if (parentClass != null && !existingClassNames.contains(parentClass.getFullName())) {
                    classReferences.add(parentClass);
                    existingClassNames.add(parentClass.getFullName());
                }
            }

            List<Map<String, Object>> referenceList =
                collectPreciseReferences(targetJavaClass, classReferences, methodReferences);

            if (includeSnippet) {
                attachSnippets(referenceList, contextLines);
            }

            sendXrefsResponse(ctx, referenceList);
        } catch (PaginationException e) {
            JadxAIMCPPluginError.handleError(ctx, 400, "Pagination error occurred while trying to handleXrefsToClass(): " + e.getMessage(), logger);
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Internal error occurred while trying to find class references: " + e.getMessage(), e, logger);
        } finally {
            JadxSearchLock.release();
        }
    }

    /**
     * @return void
     * @param Context
     * 
     * This routing method handles the /xrefs-to-method MCP tool call.
     * 1. It validates and retrieves required 'class' and 'method' parameters from the request
     * 2. It finds the containing class by name.
     * 3. It locates all methods matching the given method name within the class
     * 4. It collects related methods including:
     *      - The matched methods
     *      - All overridden versions of the method (inheritance hierarchy)
     * 5. It aggregates all method references (call sites) from each related method
     * 6. It extracts reference information for each calling method including:
     *      - Calling class name
     *      - Calling method name
     * 7. It applies pagination to the collected references and returns the result
     * 
     * Note: This method handles method overrides to provide complete corss-reference analysis
     * across the inheritance hierarchy.
     */
    public void handleXrefsToMethod(Context ctx) {
        String className = validateRequiredParam(ctx, "class_name");
        String methodName = validateRequiredParam(ctx, "method_name");
        if (className == null || methodName == null) return;

        boolean includeSnippet = "true".equalsIgnoreCase(ctx.queryParam("include_snippet"));
        int contextLines = parseIntParam(ctx.queryParam("context_lines"), 3);

        if (!tryAcquireDecompileLock(ctx)) {
            return;
        }
        try {
            JavaClass containingClass = findClassByName(ctx, className);
            if (containingClass == null) return;

            List<JavaMethod> matchedMethods = findMethodsByName(ctx, containingClass, methodName);
            if (matchedMethods == null) return;

            List<JavaMethod> relatedMethods = new ArrayList<>();
            for (JavaMethod baseMethod : matchedMethods) {
                for (JavaMethod m : getMethodWithOverrides(baseMethod)) {
                    if (!relatedMethods.contains(m)) {
                        relatedMethods.add(m);
                    }
                }
            }

            List<Map<String, Object>> referenceList = new ArrayList<>();
            Set<String> seenReferences = new HashSet<>();
            for (JavaMethod relatedMethod : relatedMethods) {
                mergeReferences(
                    referenceList,
                    seenReferences,
                    collectMethodReferences(relatedMethod, extractMethods(relatedMethod.getUseIn()))
                );
            }

            if (includeSnippet) {
                attachSnippets(referenceList, contextLines);
            }

            sendXrefsResponse(ctx, referenceList);
        } catch (PaginationException e) {
            JadxAIMCPPluginError.handleError(ctx, 400, "Pagination error occurred while trying to handleXrefsToMethod(): " + e.getMessage(), logger);
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Internal error occurred while trying to find method references: " + e.getMessage(), e, logger);
        } finally {
            JadxSearchLock.release();
        }
    }

    /**
     * @return void
     * @param Context
     * 
     * This routing method handles the /xrefs-to-field MCP tool call.
     * 1. It validates and retrieves required 'class_name' and 'field_name' parameters from the request
     * 2. It finds the containing class by name
     * 3. it locates the target field within the class by field name
     * 4. it retrieves all method references where the field is used (read/write operations)
     * 5. It collects reference information for each method that accesses the field
     * 6. It applies pagination to the collected field references and returns the result
     * 
     * Note: Field references include all usage locations (both reads and writes) across the entire codebase.
     */
    public void handleXrefsToField(Context ctx) {
        String className = validateRequiredParam(ctx, "class_name");
        String fieldName = validateRequiredParam(ctx, "field_name");
        if (className == null || fieldName == null) return;

        if (!tryAcquireDecompileLock(ctx)) {
            return;
        }
        try {
            JavaClass containingClass = findClassByName(ctx, className);
            if (containingClass == null) return;

            JavaField targetField = findFieldByName(ctx, containingClass, fieldName);
            if (targetField == null) return;

            List<JavaMethod> fieldReferences = extractMethods(targetField.getUseIn());
            List<Map<String, Object>> referenceList = collectMethodReferences(targetField, fieldReferences);
            sendXrefsResponse(ctx, referenceList);
        } catch (PaginationException e) {
            JadxAIMCPPluginError.handleError(ctx, 400, "Pagination error occurred while trying to handleXrefsToField(): " + e.getMessage(), logger);
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Internal error occurred while trying to find field references: " + e.getMessage(), e, logger);
        } finally {
            JadxSearchLock.release();
        }
    }
    // Helper methods
    
    /**
     * 
     * @param Context, String
     * @return String
     * 
     * This helper method validates the essential parameters required in HTTP request. It gets the
     * param using queryParam() method of Context class. if the values is null then handleError() else
     * return the value.
     */
    private String validateRequiredParam(Context ctx, String paramName) {
        String value = ctx.queryParam(paramName);
        if (value == null || value.isEmpty()) {
            JadxAIMCPPluginError.handleError(ctx, 400, "Missing required parameter '" + paramName + "'", logger);
            return null;
        }
        return value;
    }

    /**
     * 
     * @param Context, String
     * @return JavaClass
     * 
     * This helper method find the requests class using name. It uses the JadxWrapper to 
     * get the list of all classes. Then for each class, checks it one by one if it is the 
     * requested class or not, if yes then return it else no match found then handlError() and
     * return null.
     */
    private JavaClass findClassByName(Context ctx, String className) {
        try {
            JadxWrapper wrapper = mainWindow.getWrapper();
            
            // Initialize cache if not already done
            if (ClassCacheManager.getStatus() == ClassCacheManager.CacheStatus.NOT_INITIALIZED) {
                ClassCacheManager.initCache(wrapper);
            }
            
            // Get from cache
            Map<String, JavaClass> classMap = ClassCacheManager.getCache();
            JavaClass cls = ClassCacheManager.findClass(classMap, className);
            if (cls != null) {
                return cls;
            }
        } catch (Exception e) {
            logger.warn("Failed to use class cache: " + e.getMessage());
        }
        
        JadxAIMCPPluginError.handleError(ctx, 404, "Class " + className + " not found.", logger);
        return null;
    }

    /**
     * 
     * @param Context, JavaClass, String
     * @return List<JavaMethod>
     * 
     * This helper method find list of methods by name. For each method in given class, if it 
     * matches then add it to list, else continue, if no match found the handleError() else return
     * the list.
     */
    private List<JavaMethod> findMethodsByName(Context ctx, JavaClass javaClass, String methodName) {
        List<JavaMethod> matchedMethods = new ArrayList<>();
        String simpleClassName = javaClass.getName();
        String rawSimpleClassName = JadxApiAdapter.getClassRawSimpleName(javaClass);
        for (JavaMethod method : javaClass.getMethods()) {
            if (!method.isConstructor() && JadxApiAdapter.matchesMethodName(method, methodName)) {
                matchedMethods.add(method);
            } else if (method.isConstructor()
                    && (methodName.equals(simpleClassName)
                    || (rawSimpleClassName != null && methodName.equals(rawSimpleClassName)))) {
                matchedMethods.add(method);
            }
        }
        if (matchedMethods.isEmpty()) {
            JadxAIMCPPluginError.handleError(ctx, 404, "Method " + methodName + " not found in class " + javaClass.getFullName(), logger);
            return null;
        }
        return matchedMethods;
    }

    /**
     * @return JavaField
     * @param Context, JavaClass, String
     * 
     * This helper method find the field(attribute) of class by name. 
     * For each field(attribute) of given class, if it mathces the requested field, then return it,
     * else continue, if no match found then handleError() else return the list. 
     * 
     */
    private JavaField findFieldByName(Context ctx, JavaClass javaClass, String fieldName) {
        for (JavaField field : javaClass.getFields()) {
            if (JadxApiAdapter.matchesFieldName(field, fieldName)) return field;
        }
        JadxAIMCPPluginError.handleError(ctx, 404, "Field " + fieldName + " not found in class " + javaClass.getFullName(), logger);
        return null;
    }

    private List<JavaMethod> extractMethods(List<JavaNode> nodes) {
        List<JavaMethod> methods = new ArrayList<>();
        if (nodes == null || nodes.isEmpty()) {
            return methods;
        }

        for (JavaNode node : nodes) {
            if (node instanceof JavaMethod) {
                methods.add((JavaMethod) node);
            }
        }
        return methods;
    }

    private List<JavaClass> extractClasses(List<JavaNode> nodes) {
        List<JavaClass> classes = new ArrayList<>();
        if (nodes == null || nodes.isEmpty()) {
            return classes;
        }

        for (JavaNode node : nodes) {
            if (node instanceof JavaClass) {
                classes.add((JavaClass) node);
            }
        }
        return classes;
    }

    /**
     * Collect references for method-level use sites represented as public JavaMethod objects.
     */
    private List<Map<String, Object>> collectMethodReferences(JavaNode targetNode, List<JavaMethod> methodNodes) {
        return collectPreciseReferences(targetNode, Collections.emptyList(), methodNodes);
    }

    /**
     * @return void
     * @param List<Map<String, String>>, Set<String>, Map<String, String>
     * 
     * This helper checks if list does not contains any duplicate item. 
     * First it checks if item is not null, Then it extracts the key from item which is the name
     * of the method. if seen(known list of methods) does not contain it then adds this to it else
     * skips it.
     */
    private void addIfUnique(List<Map<String, Object>> list, Set<String> seen, Map<String, Object> item) {
        if (item != null) {
            String key = item.get("class") + "#" + item.get("method") + "#"
                + String.valueOf(item.getOrDefault("source_line", "")) + "#"
                + String.valueOf(item.getOrDefault("code_snippet", ""));
            if (!seen.contains(key)) {
                seen.add(key);
                list.add(item);
            }
        }
    }

    private void mergeReferences(
            List<Map<String, Object>> target,
            Set<String> seen,
            List<Map<String, Object>> additions) {
        for (Map<String, Object> addition : additions) {
            addIfUnique(target, seen, addition);
        }
    }

    /**
     * Extract a stable reference payload from a public JavaMethod use site.
     */
    private Map<String, Object> extractMethodReferenceInfo(JavaMethod method) {
        if (method == null) return null;
        try {
            Map<String, Object> refInfo = new HashMap<>();
            JavaClass parent = method.getDeclaringClass();
            JavaClass parentJavaClass = null;
            if (parent != null) {
                refInfo.put("class", parent.getFullName());
                refInfo.put("raw_class", JadxApiAdapter.getClassRawName(parent));
                parentJavaClass = ensureClassDecompiled(parent);
            }
            String name = method.isClassInit() ? "" : method.getName();
            if ("<clinit>".equals(name)) name = "";
            refInfo.put("method", name);
            refInfo.put("raw_method", JadxApiAdapter.getMethodRawName(method));
            JadxApiAdapter.MethodInfoSnapshot methodInfo = JadxApiAdapter.getMethodInfo(method);
            refInfo.put("from_method", methodInfo != null ? methodInfo.getFullId() : method.getFullName());
            refInfo.put("raw_from_method", JadxApiAdapter.getMethodRawFullId(method));
            refInfo.put("source_line", resolveDefinitionSourceLine(parentJavaClass, method.getDefPos()));
            return refInfo;
        } catch (Exception e) {
            logger.warn("Failed to extract reference info: " + e.getMessage());
            return null;
        }
    }

    /**
     * Ensure code metadata is ready before resolving precise source positions.
     */
    private JavaClass ensureClassDecompiled(JavaClass javaClass) {
        if (javaClass == null) {
            return null;
        }
        if (!JadxApiAdapter.isProcessComplete(javaClass)) {
            try {
                javaClass.decompile();
            } catch (Exception e) {
                logger.warn("Failed to decompile class {}: {}", javaClass.getFullName(), e.getMessage());
            }
        }
        return javaClass;
    }

    private List<Map<String, Object>> collectPreciseReferences(
            JavaNode targetNode,
            List<JavaClass> classNodes,
            List<JavaMethod> methodNodes) {
        LinkedHashMap<String, JavaClass> topUseClasses = new LinkedHashMap<>();
        for (JavaClass classNode : classNodes) {
            JavaClass javaClass = ensureClassDecompiled(classNode);
            if (javaClass != null) {
                topUseClasses.put(javaClass.getFullName(), javaClass);
            }
        }
        for (JavaMethod methodNode : methodNodes) {
            JavaClass parentClass = methodNode.getDeclaringClass();
            if (parentClass == null) {
                continue;
            }
            JavaClass javaClass = ensureClassDecompiled(parentClass);
            if (javaClass != null) {
                topUseClasses.put(javaClass.getFullName(), javaClass);
            }
        }

        List<Map<String, Object>> referenceList = new ArrayList<>();
        Set<String> seenReferences = new HashSet<>();

        for (JavaClass topUseClass : topUseClasses.values()) {
            boolean preciseAdded = collectUsePlacesForClass(targetNode, topUseClass, referenceList, seenReferences);
            if (preciseAdded) {
                continue;
            }

            boolean hasMethodReferenceInClass = false;
            for (JavaMethod methodNode : methodNodes) {
                if (methodNode.getDeclaringClass() != null
                        && topUseClass.getFullName().equals(methodNode.getDeclaringClass().getFullName())) {
                    hasMethodReferenceInClass = true;
                    addIfUnique(referenceList, seenReferences, extractMethodReferenceInfo(methodNode));
                }
            }

            if (!hasMethodReferenceInClass) {
                Map<String, Object> classRefInfo = new HashMap<>();
                classRefInfo.put("class", topUseClass.getFullName());
                classRefInfo.put("raw_class", JadxApiAdapter.getClassRawName(topUseClass));
                classRefInfo.put("method", "");
                classRefInfo.put("raw_method", "");
                classRefInfo.put("from_method", "");
                classRefInfo.put("raw_from_method", "");
                classRefInfo.put("source_line", resolveDefinitionSourceLine(topUseClass, topUseClass.getDefPos()));
                addIfUnique(referenceList, seenReferences, classRefInfo);
            }
        }
        return referenceList;
    }
    
    /**
     * @return List<JavaMethod>
     * @param JavaMethod
     * 
     * This helper method gets list of methods which are overridden.  
     * First it gets the list of related methods using getOverrideRelatedMethods() method of
     * JavaMethod. If this list is not null and this list if not empty then return the list otherwise 
     * return the javaMethod it self. 
     */
    private List<JavaMethod> getMethodWithOverrides(JavaMethod javaMethod) {
        List<JavaMethod> related = javaMethod.getOverrideRelatedMethods();
        return (related != null && !related.isEmpty()) ? related : Collections.singletonList(javaMethod);
    }

    /**
     * @return void
     * @param Context, List<Map<String, String>>
     * @throws PaginationException
     * 
     * This helper method sends the response to MCP tool calls for this category. 
     * First it creates a map of result with pagination and returns it as a json response.
     */
    private boolean collectUsePlacesForClass(
            JavaNode targetNode,
            JavaClass topUseClass,
            List<Map<String, Object>> referenceList,
            Set<String> seenReferences) {
        try {
            ICodeInfo codeInfo = topUseClass.getCodeInfo();
            if (codeInfo == null || !codeInfo.hasMetadata()) {
                return false;
            }

            List<Integer> usePositions = topUseClass.getUsePlacesFor(codeInfo, targetNode);
            if (usePositions.isEmpty()) {
                return false;
            }

            String code = codeInfo.getCodeStr();
            JadxWrapper wrapper = mainWindow.getWrapper();
            boolean added = false;

            for (int pos : usePositions) {
                String line = CodeUtils.getLineForPos(code, pos).trim();
                if (line.startsWith("import ")) {
                    continue;
                }
                JavaNode enclosingNode = wrapper.getEnclosingNode(codeInfo, pos);
                Map<String, Object> refInfo = buildPreciseReferenceInfo(topUseClass, enclosingNode, line, code, pos);
                addIfUnique(referenceList, seenReferences, refInfo);
                added = true;
            }
            return added;
        } catch (Exception e) {
            logger.debug("Precise xref collection failed for {} in {}: {}",
                targetNode.getFullName(), topUseClass.getFullName(), e.getMessage());
            return false;
        }
    }

    private Map<String, Object> buildPreciseReferenceInfo(
            JavaClass topUseClass,
            JavaNode enclosingNode,
            String line,
            String code,
            int position) {
        Map<String, Object> refInfo = new HashMap<>();
        refInfo.put("class", topUseClass.getFullName());
        refInfo.put("raw_class", JadxApiAdapter.getClassRawName(topUseClass));
        refInfo.put("code_snippet", line);

        int decompiledLine = CodeUtils.getLineNumForPos(
            code,
            position,
            mainWindow.getWrapper().getArgs().getCodeNewLineStr()
        );
        refInfo.put("decompiled_line", decompiledLine);
        refInfo.put("source_line", topUseClass.getSourceLine(decompiledLine));

        if (enclosingNode instanceof JavaMethod) {
            JavaMethod fromMethod = (JavaMethod) enclosingNode;
            String legacyMethodName = fromMethod.isClassInit() ? "" : fromMethod.getName();
            refInfo.put("method", legacyMethodName);
            refInfo.put("raw_method", JadxApiAdapter.getMethodRawName(fromMethod));
            JadxApiAdapter.MethodInfoSnapshot methodInfo = JadxApiAdapter.getMethodInfo(fromMethod);
            refInfo.put("from_method", methodInfo != null ? methodInfo.getFullId() : fromMethod.getFullName());
            refInfo.put("raw_from_method", JadxApiAdapter.getMethodRawFullId(fromMethod));
        } else {
            refInfo.put("method", "");
            refInfo.put("raw_method", "");
            refInfo.put("from_method", "");
            refInfo.put("raw_from_method", "");
        }
        return refInfo;
    }

    private Integer resolveDefinitionSourceLine(JavaClass javaClass, int definitionPosition) {
        if (javaClass == null || definitionPosition <= 0) {
            return null;
        }
        try {
            ICodeInfo codeInfo = javaClass.getCodeInfo();
            if (codeInfo == null) {
                return null;
            }
            int decompiledLine = CodeUtils.getLineNumForPos(
                codeInfo.getCodeStr(),
                definitionPosition,
                mainWindow.getWrapper().getArgs().getCodeNewLineStr()
            );
            return javaClass.getSourceLine(decompiledLine);
        } catch (Exception e) {
            logger.debug("Failed to resolve definition source line for {}: {}", javaClass.getFullName(), e.getMessage());
            return null;
        }
    }

    private void sendXrefsResponse(Context ctx, List<Map<String, Object>> referenceList) throws PaginationException {
        Map<String, Object> result = paginationUtils.handlePagination(ctx, referenceList, "xrefs", "references", ref -> ref);
        ctx.json(result);
    }

    /**
     * @return void
     * @param Context
     * 
     * This routing method handles the /batch-xrefs MCP tool call.
     * Allows fetching xrefs for multiple targets in a single request.
     * 
     * Request parameters:
     * - targets (required): Comma-separated list of "type:class_name[:method_or_field]" 
     *   Examples: 
     *   - "class:com.example.MyClass"
     *   - "method:com.example.MyClass:myMethod"
     *   - "field:com.example.MyClass:myField"
     * 
     * Returns JSON with results for each target.
     * Max limit: 10 targets per request.
     */
    public void handleBatchXrefs(Context ctx) {
        String targetsParam = ctx.queryParam("targets");
        if (targetsParam == null || targetsParam.isEmpty()) {
            JadxAIMCPPluginError.handleError(ctx, 400, 
                "Missing 'targets' parameter. Format: type:class[:member]", logger);
            return;
        }

        String[] targets = targetsParam.split(",");
        final int MAX_BATCH_SIZE = 10;
        if (targets.length > MAX_BATCH_SIZE) {
            JadxAIMCPPluginError.handleError(ctx, 400, 
                "Too many targets. Maximum " + MAX_BATCH_SIZE + " per request.", logger);
            return;
        }

        if (!tryAcquireDecompileLock(ctx)) {
            return;
        }
        try {
            JadxWrapper wrapper = mainWindow.getWrapper();
            
            // Initialize cache if not already done
            if (ClassCacheManager.getStatus() == ClassCacheManager.CacheStatus.NOT_INITIALIZED) {
                ClassCacheManager.initCache(wrapper);
            }
            
            // Check cache status
            ClassCacheManager.CacheStatus status = ClassCacheManager.getStatus();
            if (status == ClassCacheManager.CacheStatus.LOADING) {
                Map<String, Object> health = ClassCacheManager.getHealthInfo();
                Map<String, Object> response = new HashMap<>();
                response.put("status", "loading");
                response.put("type", "batch-xrefs");
                response.put("message", "Class cache is being loaded in background. First load takes ~30-60 seconds for large APKs.");
                response.put("retry_after", 10);
                response.put("health", health);

                long elapsed = health.containsKey("elapsed_seconds") ? ((Number) health.get("elapsed_seconds")).longValue() : 0;
                if (elapsed > 0) {
                    response.put("estimated_remaining", "~" + Math.max(0, 40 - elapsed) + " seconds");
                }

                ctx.status(503).json(response);
                return;
            }
            
            // Get cached class map
            Map<String, JavaClass> classMap = ClassCacheManager.getCache();
            List<Map<String, Object>> results = new ArrayList<>();

            for (String target : targets) {
                String trimmed = target.trim();
                String[] parts = trimmed.split(":", 3);
                
                Map<String, Object> result = new HashMap<>();
                result.put("target", trimmed);
                
                if (parts.length < 2) {
                    result.put("found", false);
                    result.put("error", "Invalid format. Use type:class[:member]");
                    results.add(result);
                    continue;
                }

                String type = parts[0].toLowerCase();
                String className = parts[1];
                
                JavaClass targetClass = ClassCacheManager.findClass(classMap, className);
                
                if (targetClass == null) {
                    result.put("found", false);
                    result.put("error", "Class not found");
                    results.add(result);
                    continue;
                }

                List<Map<String, Object>> xrefs = new ArrayList<>();
                boolean matched = false;

                try {
                    switch (type) {
                        case "class":
                            matched = true;
                            List<JavaMethod> methodRefs = new ArrayList<>(JadxApiAdapter.getClassUseInMethods(targetClass));
                            for (JavaMethod javaMethod : targetClass.getMethods()) {
                                if (javaMethod.isConstructor()) {
                                    methodRefs.addAll(extractMethods(javaMethod.getUseIn()));
                                }
                            }
                            xrefs = collectPreciseReferences(
                                targetClass,
                                new ArrayList<>(extractClasses(targetClass.getUseIn())),
                                methodRefs
                            );
                            break;
                            
                        case "method":
                            if (parts.length < 3) {
                                result.put("found", false);
                                result.put("error", "Method name required");
                                results.add(result);
                                continue;
                            }
                            String methodName = parts[2];
                            Set<String> seenMethodRefs = new HashSet<>();
                            for (JavaMethod method : targetClass.getMethods()) {
                                if (JadxApiAdapter.matchesMethodName(method, methodName)) {
                                    matched = true;
                                    mergeReferences(
                                        xrefs,
                                        seenMethodRefs,
                                        collectMethodReferences(method, extractMethods(method.getUseIn()))
                                    );
                                }
                            }
                            if (!matched) {
                                result.put("found", false);
                                result.put("error", "Method '" + methodName + "' not found in class " + className);
                                results.add(result);
                                continue;
                            }
                            break;
                            
                        case "field":
                            if (parts.length < 3) {
                                result.put("found", false);
                                result.put("error", "Field name required");
                                results.add(result);
                                continue;
                            }
                            String fieldName = parts[2];
                            Set<String> seenFieldRefs = new HashSet<>();
                            for (JavaField field : targetClass.getFields()) {
                                if (JadxApiAdapter.matchesFieldName(field, fieldName)) {
                                    matched = true;
                                    mergeReferences(
                                        xrefs,
                                        seenFieldRefs,
                                        collectMethodReferences(field, extractMethods(field.getUseIn()))
                                    );
                                }
                            }
                            if (!matched) {
                                result.put("found", false);
                                result.put("error", "Field '" + fieldName + "' not found in class " + className);
                                results.add(result);
                                continue;
                            }
                            break;
                            
                        default:
                            result.put("found", false);
                            result.put("error", "Invalid type. Use class/method/field");
                            results.add(result);
                            continue;
                    }
                    
                    result.put("found", true);
                    result.put("xrefs_count", xrefs.size());
                    result.put("xrefs", xrefs);
                } catch (Exception e) {
                    result.put("found", false);
                    result.put("error", "Failed: " + e.getMessage());
                }
                
                results.add(result);
            }

            Map<String, Object> response = new HashMap<>();
            response.put("results", results);
            response.put("total", targets.length);
            ctx.json(response);

        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Internal error in batch xrefs: " + e.getMessage(), e, logger);
        } finally {
            JadxSearchLock.release();
        }
    }

    /**
     * Parses an integer query parameter, returning {@code defaultValue} if the
     * parameter is null, blank, or non-numeric.
     */
    private int parseIntParam(String raw, int defaultValue) {
        if (raw == null || raw.isBlank()) {
            return defaultValue;
        }
        try {
            return Integer.parseInt(raw.trim());
        } catch (NumberFormatException e) {
            return defaultValue;
        }
    }

    /**
     * For each entry in {@code referenceList}, looks up the source code of the
     * referencing class and attaches a {@code snippet} sub-object containing
     * the lines around {@code source_line} (or {@code decompiled_line} as fallback).
     *
     * <p>If source code is unavailable or an error occurs for a specific entry,
     * that entry's {@code snippet} is set to {@code null} — the call never fails
     * the entire xref response.</p>
     *
     * @param referenceList mutable list of xref maps (modified in place)
     * @param contextLines  number of lines before and after the reference line to include
     */
    private void attachSnippets(List<Map<String, Object>> referenceList, int contextLines) {
        // Cache source code per class name to avoid repeated decompilation
        Map<String, String[]> sourceLineCache = new HashMap<>();

        for (Map<String, Object> ref : referenceList) {
            try {
                String fromClassName = (String) ref.get("class");
                if (fromClassName == null || fromClassName.isEmpty()) {
                    ref.put("snippet", null);
                    continue;
                }

                // Resolve the target line — prefer source_line (maps to original .java/.kt),
                // fall back to decompiled_line.
                Integer targetLine = null;
                Object sourceLine = ref.get("source_line");
                if (sourceLine instanceof Number) {
                    targetLine = ((Number) sourceLine).intValue();
                }
                if (targetLine == null || targetLine <= 0) {
                    Object decompiledLine = ref.get("decompiled_line");
                    if (decompiledLine instanceof Number) {
                        targetLine = ((Number) decompiledLine).intValue();
                    }
                }
                if (targetLine == null || targetLine <= 0) {
                    ref.put("snippet", null);
                    continue;
                }

                // Fetch and cache decompiled source lines for this class.
                String[] lines = sourceLineCache.get(fromClassName);
                if (lines == null) {
                    lines = fetchSourceLines(fromClassName);
                    sourceLineCache.put(fromClassName, lines != null ? lines : new String[0]);
                }
                if (lines == null || lines.length == 0) {
                    ref.put("snippet", null);
                    continue;
                }

                // lines array is 0-based; targetLine is 1-based.
                int zeroLine = targetLine - 1;
                int startLine = Math.max(0, zeroLine - contextLines);
                int endLine = Math.min(lines.length - 1, zeroLine + contextLines);

                StringBuilder sb = new StringBuilder();
                for (int i = startLine; i <= endLine; i++) {
                    sb.append(lines[i]);
                    if (i < endLine) {
                        sb.append('\n');
                    }
                }

                Map<String, Object> snippet = new HashMap<>();
                snippet.put("code", sb.toString());
                snippet.put("start_line", startLine + 1); // convert back to 1-based
                snippet.put("end_line", endLine + 1);
                ref.put("snippet", snippet);

            } catch (Exception e) {
                logger.debug("[JAI] Failed to attach snippet for xref entry: {}", e.getMessage());
                ref.put("snippet", null);
            }
        }
    }

    /**
     * Returns the decompiled source of {@code className} split into lines, or
     * {@code null} if the class cannot be found or decompiled.
     */
    private String[] fetchSourceLines(String className) {
        try {
            JadxWrapper wrapper = mainWindow.getWrapper();
            Map<String, jadx.api.JavaClass> classMap = ClassCacheManager.getCache();
            jadx.api.JavaClass cls = ClassCacheManager.findClass(classMap, className);
            if (cls == null) {
                return null;
            }
            jadx.api.ICodeInfo codeInfo = cls.getCodeInfo();
            if (codeInfo == null) {
                return null;
            }
            String code = codeInfo.getCodeStr();
            if (code == null) {
                return null;
            }
            String newLine = wrapper.getArgs().getCodeNewLineStr();
            return code.split(java.util.regex.Pattern.quote(newLine), -1);
        } catch (Exception e) {
            logger.debug("[JAI] fetchSourceLines failed for {}: {}", className, e.getMessage());
            return null;
        }
    }

    private boolean tryAcquireDecompileLock(Context ctx) {
        if (JadxSearchLock.tryAcquire()) {
            return true;
        }

        Map<String, Object> busyResponse = new HashMap<>();
        busyResponse.put("error", "Decompilation operation in progress");
        busyResponse.put("retry_after", JadxSearchLock.RETRY_AFTER_SECONDS);
        busyResponse.put("busy", true);
        ctx.status(503).json(busyResponse);
        return false;
    }
}
