package com.zin.jadxaimcp.server.routes;

import io.javalin.http.Context;

import jadx.api.JavaClass;
import jadx.api.JavaField;
import jadx.api.JavaMethod;
import jadx.core.dex.nodes.ClassNode;
import jadx.core.dex.nodes.FieldNode;
import jadx.core.dex.nodes.MethodNode;
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

import com.zin.jadxaimcp.utils.PaginationUtils;
import com.zin.jadxaimcp.utils.PaginationUtils.PaginationException;
import com.zin.jadxaimcp.utils.JadxAIMCPPluginError;
import com.zin.jadxaimcp.utils.ClassCacheManager;
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

        if (!tryAcquireDecompileLock(ctx)) {
            return;
        }
        try {
            JavaClass targetJavaClass = findClassByName(ctx, className);
            if (targetJavaClass == null) return;

            ClassNode targetClassNode = targetJavaClass.getClassNode();
            List<ClassNode> classReferences = targetClassNode.getUseIn();
            List<MethodNode> methodReferences = new ArrayList<>(targetClassNode.getUseInMth());

            // Include constructor references
            for (JavaMethod javaMethod : targetJavaClass.getMethods()) {
                if (javaMethod.isConstructor()) {
                    methodReferences.addAll(javaMethod.getMethodNode().getUseIn());
                }
            }

            // Build className -> method names map
            Map<String, Set<String>> classToMethodsMap = new HashMap<>();
            for (MethodNode mth : methodReferences) {
                ClassNode parentClass = mth.getParentClass();
                if (parentClass != null) {
                    classToMethodsMap.computeIfAbsent(parentClass.getFullName(), k -> new HashSet<>()).add(mth.getName());
                }
            }

            // Add classes that call constructors
            Set<String> existingClassNames = new HashSet<>();
            for (ClassNode cls : classReferences) {
                existingClassNames.add(cls.getFullName());
            }
            for (MethodNode mth : methodReferences) {
                ClassNode parentClass = mth.getParentClass();
                if (parentClass != null && !existingClassNames.contains(parentClass.getFullName())) {
                    classReferences.add(parentClass);
                    existingClassNames.add(parentClass.getFullName());
                }
            }

            // Build final list
            List<Map<String, String>> referenceList = new ArrayList<>();
            Set<String> seenReferences = new HashSet<>();

            // Process Class References
            for (ClassNode refClassNode : classReferences) {
                String refClassName = refClassNode.getFullName();

                // Method-level references
                if (classToMethodsMap.containsKey(refClassName)) {
                    for (MethodNode mth : methodReferences) {
                        if (mth.getParentClass() != null && mth.getParentClass().getFullName().equals(refClassName)) {
                            Map<String, String> refInfo = extractMethodNodeReferenceInfo(mth);
                            addIfUnique(referenceList, seenReferences, refInfo);
                        }
                    }
                } else {
                    // Class-level reference
                    Map<String, String> refInfo = new HashMap<>();
                    refInfo.put("class", refClassName);
                    refInfo.put("method", "");
                    addIfUnique(referenceList, seenReferences, refInfo);
                }
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

            List<MethodNode> allMethodReferences = new ArrayList<>();
            for (JavaMethod relatedMethod : relatedMethods) {
                allMethodReferences.addAll(relatedMethod.getMethodNode().getUseIn());
            }

            List<Map<String, String>> referenceList = collectMethodNodeReferences(allMethodReferences);
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

            FieldNode fieldNode = targetField.getFieldNode();
            List<MethodNode> fieldReferences = fieldNode.getUseIn();
            List<Map<String, String>> referenceList = collectMethodNodeReferences(fieldReferences);
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
            JavaClass cls = classMap.get(className);
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
        for (JavaMethod method : javaClass.getMethods()) {
            if (!method.isConstructor() && method.getName().equals(methodName)) {
                matchedMethods.add(method);
            } else if (method.isConstructor() && methodName.equals(simpleClassName)) {
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
            if (field.getName().equals(fieldName)) return field;
        }
        JadxAIMCPPluginError.handleError(ctx, 404, "Field " + fieldName + " not found in class " + javaClass.getFullName(), logger);
        return null;
    }

    /**
     * @return List<Map<String, String>> 
     * @param List<MethodNode>
     * 
     * This helper method returns list of referenced to metod node. For each method node in given 
     * MethodNodes, get its reference info to Map<String, String>, verify if it is unique using addIfUnique() method.
     * if it is unique then add it to list else skip.
     * Return the collected list.
     */
    private List<Map<String, String>> collectMethodNodeReferences(List<MethodNode> methodNodes) {
        Set<String> seenReferences = new HashSet<>();
        List<Map<String, String>> referenceList = new ArrayList<>();
        for (MethodNode refMethodNode : methodNodes) {
            Map<String, String> refInfo = extractMethodNodeReferenceInfo(refMethodNode);
            addIfUnique(referenceList, seenReferences, refInfo);
        }
        return referenceList;
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
    private void addIfUnique(List<Map<String, String>> list, Set<String> seen, Map<String, String> item) {
        if (item != null) {
            String key = item.get("class") + "#" + item.get("method");
            if (!seen.contains(key)) {
                seen.add(key);
                list.add(item);
            }
        }
    }

    /**
     * @return Map<String, String> 
     * @param MethodNode
     * 
     * This helper method extracts method node reference info from MethodNode. 
     * First it get's the parent class of method node using getParanetClass() method MethodNode and
     * stores it in ClassNode's object named 'parent'. if parent is not null then put it in reference list.
     * Then it gets the JavaMethod of method node using getJavaNode(). if it is not null then get that
     * method name else get the method node name. 
     * 
     * If this 'name' equals '<clinit>' then empty it. Put the 'name' if reference info list. 
     * Return info list.
     */
    private Map<String, String> extractMethodNodeReferenceInfo(MethodNode methodNode) {
        if (methodNode == null) return null;
        try {
            Map<String, String> refInfo = new HashMap<>();
            ClassNode parent = methodNode.getParentClass();
            if (parent != null) {
                refInfo.put("class", parent.getFullName());
                ensureClassDecompiled(parent);
            }
            JavaMethod javaMethod = methodNode.getJavaNode();
            String name = (javaMethod != null) ? javaMethod.getName() : methodNode.getName();
            if ("<clinit>".equals(name)) name = "";
            refInfo.put("method", name);
            return refInfo;
        } catch (Exception e) {
            logger.warn("Failed to extract reference info: " + e.getMessage());
            return null;
        }
    }

    /**
     * @return void
     * @param ClassNode
     * 
     * This helper method checks if the class is decomplied or not. 
     * if classNode is not null and classNode's processing state is not complete then
     *  - try to check classNode's JavaNode is not null 
     *     - if it not null then decompile it. 
     *  - If any exception then handle it.
     */
    private void ensureClassDecompiled(ClassNode classNode) {
        if (classNode != null && !classNode.getState().isProcessComplete()) {
            try {
                if (classNode.getJavaNode() != null) classNode.getJavaNode().decompile();
            } catch (Exception e) {
                logger.warn("Failed to decompile class {}: {}", classNode.getFullName(), e.getMessage());
            }
        }
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
    private void sendXrefsResponse(Context ctx, List<Map<String, String>> referenceList) throws PaginationException {
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
                
                JavaClass targetClass = classMap.get(className);
                
                if (targetClass == null) {
                    result.put("found", false);
                    result.put("error", "Class not found");
                    results.add(result);
                    continue;
                }

                List<Map<String, String>> xrefs = new ArrayList<>();
                Set<String> seen = new HashSet<>();
                boolean matched = false;

                try {
                    switch (type) {
                        case "class":
                            matched = true;
                            ClassNode classNode = targetClass.getClassNode();
                            for (MethodNode mth : classNode.getUseInMth()) {
                                Map<String, String> ref = extractMethodNodeReferenceInfo(mth);
                                addIfUnique(xrefs, seen, ref);
                            }
                            break;
                            
                        case "method":
                            if (parts.length < 3) {
                                result.put("found", false);
                                result.put("error", "Method name required");
                                results.add(result);
                                continue;
                            }
                            String methodName = parts[2];
                            for (JavaMethod method : targetClass.getMethods()) {
                                if (method.getName().equals(methodName)) {
                                    matched = true;
                                    for (MethodNode mth : method.getMethodNode().getUseIn()) {
                                        Map<String, String> ref = extractMethodNodeReferenceInfo(mth);
                                        addIfUnique(xrefs, seen, ref);
                                    }
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
                            for (JavaField field : targetClass.getFields()) {
                                if (field.getName().equals(fieldName)) {
                                    matched = true;
                                    for (MethodNode mth : field.getFieldNode().getUseIn()) {
                                        Map<String, String> ref = extractMethodNodeReferenceInfo(mth);
                                        addIfUnique(xrefs, seen, ref);
                                    }
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
