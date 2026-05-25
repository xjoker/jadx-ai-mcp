package com.zin.jadxaimcp.server.routes;

import io.javalin.http.Context;

import jadx.api.JavaClass;
import jadx.api.JavaMethod;
import jadx.core.dex.instructions.BaseInvokeNode;
import jadx.core.dex.instructions.args.InsnArg;
import jadx.core.dex.instructions.args.InsnWrapArg;
import jadx.core.dex.nodes.InsnNode;
import jadx.core.dex.nodes.MethodNode;
import jadx.gui.JadxWrapper;
import jadx.gui.ui.MainWindow;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;
import org.xml.sax.InputSource;

import javax.xml.XMLConstants;
import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import java.io.StringReader;
import java.util.*;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import com.zin.jadxaimcp.utils.ClassCacheManager;
import com.zin.jadxaimcp.utils.JadxAIMCPPluginError;
import com.zin.jadxaimcp.utils.JadxApiAdapter;
import com.zin.jadxaimcp.utils.JadxSearchLock;
import com.zin.jadxaimcp.utils.ManifestInfoService;

/**
 * Analysis Routes: attack surface, string literal search, call graph export.
 */
public class AnalysisRoutes {
    private static final Logger logger = LoggerFactory.getLogger(AnalysisRoutes.class);
    private static final String ANDROID_NS = "http://schemas.android.com/apk/res/android";

    /** Known DANGEROUS-level Android permissions. */
    private static final Set<String> DANGEROUS_PERMISSIONS = new HashSet<>(Arrays.asList(
        "android.permission.READ_CONTACTS",
        "android.permission.WRITE_CONTACTS",
        "android.permission.GET_ACCOUNTS",
        "android.permission.READ_CALL_LOG",
        "android.permission.WRITE_CALL_LOG",
        "android.permission.PROCESS_OUTGOING_CALLS",
        "android.permission.CAMERA",
        "android.permission.RECORD_AUDIO",
        "android.permission.READ_PHONE_STATE",
        "android.permission.READ_PHONE_NUMBERS",
        "android.permission.CALL_PHONE",
        "android.permission.ANSWER_PHONE_CALLS",
        "android.permission.ADD_VOICEMAIL",
        "android.permission.USE_SIP",
        "android.permission.BODY_SENSORS",
        "android.permission.BODY_SENSORS_BACKGROUND",
        "android.permission.SEND_SMS",
        "android.permission.RECEIVE_SMS",
        "android.permission.READ_SMS",
        "android.permission.RECEIVE_WAP_PUSH",
        "android.permission.RECEIVE_MMS",
        "android.permission.READ_EXTERNAL_STORAGE",
        "android.permission.READ_MEDIA_IMAGES",
        "android.permission.READ_MEDIA_VIDEO",
        "android.permission.READ_MEDIA_AUDIO",
        "android.permission.READ_MEDIA_VISUAL_USER_SELECTED",
        "android.permission.WRITE_EXTERNAL_STORAGE",
        "android.permission.ACCESS_FINE_LOCATION",
        "android.permission.ACCESS_COARSE_LOCATION",
        "android.permission.ACCESS_BACKGROUND_LOCATION",
        "android.permission.ACTIVITY_RECOGNITION",
        "android.permission.BLUETOOTH_SCAN",
        "android.permission.BLUETOOTH_CONNECT",
        "android.permission.BLUETOOTH_ADVERTISE",
        "android.permission.UWB_RANGING",
        "android.permission.POST_NOTIFICATIONS",
        "android.permission.NEARBY_WIFI_DEVICES",
        "android.permission.USE_EXACT_ALARM",
        "com.android.voicemail.permission.ADD_VOICEMAIL"
    ));

    private final MainWindow mainWindow;
    private final ManifestInfoService manifestInfoService = ManifestInfoService.getInstance();

    public AnalysisRoutes(MainWindow mainWindow) {
        this.mainWindow = mainWindow;
    }

    // -------------------------------------------------------------------------
    // GET /attack-surface
    // -------------------------------------------------------------------------

    /**
     * GET /attack-surface
     *
     * Parses AndroidManifest.xml and returns a structured view of the APK's
     * exported components, intent filters, permissions, and deep-links.
     */
    public void handleAttackSurface(Context ctx) {
        try {
            JadxWrapper wrapper = mainWindow.getWrapper();
            if (wrapper == null) {
                ctx.status(503).json(Map.of("error", "JADX wrapper not initialized", "total_exported", 0));
                return;
            }

            String manifestContent = manifestInfoService.getManifestContent(wrapper);
            if (manifestContent == null || manifestContent.isBlank()) {
                ctx.json(Map.of(
                    "error", "manifest not available",
                    "total_exported", 0
                ));
                return;
            }

            Document doc = parseXml(manifestContent);
            if (doc == null) {
                ctx.json(Map.of("error", "failed to parse manifest", "total_exported", 0));
                return;
            }

            Element manifestEl = getFirstElement(doc, "manifest");
            String pkgName = manifestEl != null ? emptyToNull(manifestEl.getAttribute("package")) : null;
            Element appEl = getFirstElement(doc, "application");

            List<Map<String, Object>> activities = new ArrayList<>();
            List<Map<String, Object>> services = new ArrayList<>();
            List<Map<String, Object>> receivers = new ArrayList<>();
            List<Map<String, Object>> providers = new ArrayList<>();
            List<Map<String, Object>> customPermissions = new ArrayList<>();
            List<String> dangerousPermissionsUsed = new ArrayList<>();
            Set<String> deeplinkSummary = new LinkedHashSet<>();

            // Parse <uses-permission> for dangerous ones
            NodeList usesPermNodes = doc.getElementsByTagName("uses-permission");
            for (int i = 0; i < usesPermNodes.getLength(); i++) {
                Node n = usesPermNodes.item(i);
                if (!(n instanceof Element)) continue;
                String permName = getAndroidAttr((Element) n, "name");
                if (permName != null && DANGEROUS_PERMISSIONS.contains(permName)) {
                    dangerousPermissionsUsed.add(permName);
                }
            }

            // Parse <permission> for custom permissions
            NodeList permNodes = doc.getElementsByTagName("permission");
            for (int i = 0; i < permNodes.getLength(); i++) {
                Node n = permNodes.item(i);
                if (!(n instanceof Element)) continue;
                Element el = (Element) n;
                String permName = getAndroidAttr(el, "name");
                String protectionLevel = getAndroidAttr(el, "protectionLevel");
                if (permName != null) {
                    Map<String, Object> entry = new LinkedHashMap<>();
                    entry.put("name", permName);
                    entry.put("protection_level", resolveProtectionLevel(protectionLevel));
                    customPermissions.add(entry);
                }
            }

            // Parse application components
            if (appEl != null) {
                NodeList children = appEl.getChildNodes();
                for (int i = 0; i < children.getLength(); i++) {
                    Node node = children.item(i);
                    if (!(node instanceof Element)) continue;
                    Element el = (Element) node;
                    String tag = el.getTagName();
                    String exportedAttr = getAndroidAttr(el, "exported");
                    boolean explicitlyExported = "true".equalsIgnoreCase(exportedAttr);
                    if (!explicitlyExported) continue;

                    String compName = normalizeComponentName(pkgName, getAndroidAttr(el, "name"));

                    switch (tag) {
                        case "activity":
                        case "activity-alias": {
                            Map<String, Object> entry = new LinkedHashMap<>();
                            entry.put("name", compName);
                            entry.put("exported", true);
                            List<Map<String, Object>> filters = parseIntentFilters(el, deeplinkSummary);
                            entry.put("intent_filters", filters);
                            activities.add(entry);
                            break;
                        }
                        case "service": {
                            Map<String, Object> entry = new LinkedHashMap<>();
                            entry.put("name", compName);
                            entry.put("exported", true);
                            List<Map<String, Object>> filters = parseIntentFilters(el, null);
                            entry.put("intent_filters", filters);
                            services.add(entry);
                            break;
                        }
                        case "receiver": {
                            Map<String, Object> entry = new LinkedHashMap<>();
                            entry.put("name", compName);
                            entry.put("exported", true);
                            List<String> actions = parseReceiverActions(el);
                            entry.put("actions", actions);
                            receivers.add(entry);
                            break;
                        }
                        case "provider": {
                            Map<String, Object> entry = new LinkedHashMap<>();
                            entry.put("name", compName);
                            entry.put("exported", true);
                            entry.put("authority", emptyToNull(getAndroidAttr(el, "authorities")));
                            String grantUri = getAndroidAttr(el, "grantUriPermissions");
                            entry.put("grant_uri_permissions", "true".equalsIgnoreCase(grantUri));
                            providers.add(entry);
                            break;
                        }
                        default:
                            break;
                    }
                }
            }

            int totalExported = activities.size() + services.size() + receivers.size() + providers.size();

            Map<String, Object> result = new LinkedHashMap<>();
            result.put("activities", activities);
            result.put("services", services);
            result.put("receivers", receivers);
            result.put("providers", providers);
            result.put("custom_permissions", customPermissions);
            result.put("dangerous_permissions_used", dangerousPermissionsUsed);
            result.put("deeplink_summary", new ArrayList<>(deeplinkSummary));
            result.put("total_exported", totalExported);
            result.put("note", "Based on explicit android:exported='true' only; implicit exports via intent-filter not included");

            ctx.json(result);
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Failed to analyze attack surface: " + e.getMessage(), e, logger);
        }
    }

    private List<Map<String, Object>> parseIntentFilters(Element componentEl, Set<String> deeplinkCollector) {
        List<Map<String, Object>> filters = new ArrayList<>();
        NodeList children = componentEl.getChildNodes();
        for (int i = 0; i < children.getLength(); i++) {
            Node n = children.item(i);
            if (!(n instanceof Element)) continue;
            Element el = (Element) n;
            if (!"intent-filter".equals(el.getTagName())) continue;

            String action = null;
            String category = null;
            String dataScheme = null;
            String dataHost = null;
            String dataPath = null;

            NodeList filterChildren = el.getChildNodes();
            for (int j = 0; j < filterChildren.getLength(); j++) {
                Node fn = filterChildren.item(j);
                if (!(fn instanceof Element)) continue;
                Element fe = (Element) fn;
                switch (fe.getTagName()) {
                    case "action":
                        if (action == null) action = getAndroidAttr(fe, "name");
                        break;
                    case "category":
                        if (category == null) category = getAndroidAttr(fe, "name");
                        break;
                    case "data":
                        if (dataScheme == null) dataScheme = getAndroidAttr(fe, "scheme");
                        if (dataHost == null) dataHost = getAndroidAttr(fe, "host");
                        if (dataPath == null) {
                            dataPath = getAndroidAttr(fe, "path");
                            if (dataPath == null) dataPath = getAndroidAttr(fe, "pathPattern");
                            if (dataPath == null) dataPath = getAndroidAttr(fe, "pathPrefix");
                        }
                        break;
                    default:
                        break;
                }
            }

            Map<String, Object> filterEntry = new LinkedHashMap<>();
            filterEntry.put("action", action);
            filterEntry.put("category", category);
            filterEntry.put("data_scheme", dataScheme);

            // Build deeplink string if scheme is present
            String deeplink = null;
            if (dataScheme != null) {
                StringBuilder sb = new StringBuilder(dataScheme).append("://");
                if (dataHost != null) sb.append(dataHost);
                if (dataPath != null) sb.append(dataPath);
                deeplink = sb.toString();
                if (deeplinkCollector != null) deeplinkCollector.add(deeplink);
            }
            filterEntry.put("deeplink", deeplink);
            filters.add(filterEntry);
        }
        return filters;
    }

    private List<String> parseReceiverActions(Element componentEl) {
        List<String> actions = new ArrayList<>();
        NodeList children = componentEl.getChildNodes();
        for (int i = 0; i < children.getLength(); i++) {
            Node n = children.item(i);
            if (!(n instanceof Element)) continue;
            Element el = (Element) n;
            if (!"intent-filter".equals(el.getTagName())) continue;
            NodeList filterChildren = el.getChildNodes();
            for (int j = 0; j < filterChildren.getLength(); j++) {
                Node fn = filterChildren.item(j);
                if (!(fn instanceof Element)) continue;
                Element fe = (Element) fn;
                if ("action".equals(fe.getTagName())) {
                    String actionName = getAndroidAttr(fe, "name");
                    if (actionName != null) actions.add(actionName);
                }
            }
        }
        return actions;
    }

    private String resolveProtectionLevel(String raw) {
        if (raw == null) return "normal";
        // protectionLevel is often stored as a hex string
        try {
            int val = Integer.decode(raw) & 0xF;
            switch (val) {
                case 0: return "normal";
                case 1: return "dangerous";
                case 2: return "signature";
                case 3: return "signatureOrSystem";
                default: return raw;
            }
        } catch (NumberFormatException e) {
            return raw;
        }
    }

    // -------------------------------------------------------------------------
    // GET /search-string-literals
    // -------------------------------------------------------------------------

    /**
     * GET /search-string-literals
     *
     * Scans already-cached decompiled class code for string literals matching
     * the given pattern. Does NOT trigger new decompilation.
     *
     * Query params:
     *   pattern   (required) — substring or regex to match
     *   regex     (optional, default false) — treat pattern as regex
     *   min_length (optional, default 8)
     *   class     (optional) — filter by class name prefix/contains
     *   limit     (optional, default 200)
     */
    public void handleSearchStringLiterals(Context ctx) {
        String pattern = ctx.queryParam("pattern");
        if (pattern == null || pattern.isEmpty()) {
            JadxAIMCPPluginError.handleError(ctx, 400, "Missing required parameter 'pattern'", logger);
            return;
        }

        boolean useRegex = "true".equalsIgnoreCase(ctx.queryParam("regex"));
        int minLength;
        try {
            String ml = ctx.queryParam("min_length");
            minLength = (ml != null && !ml.isEmpty()) ? Integer.parseInt(ml) : 8;
        } catch (NumberFormatException e) {
            minLength = 8;
        }

        int limit;
        try {
            String lm = ctx.queryParam("limit");
            limit = (lm != null && !lm.isEmpty()) ? Integer.parseInt(lm) : 200;
        } catch (NumberFormatException e) {
            limit = 200;
        }

        String classFilter = ctx.queryParam("class");

        try {
            JadxWrapper wrapper = mainWindow.getWrapper();
            if (wrapper == null) {
                JadxAIMCPPluginError.handleError(ctx, 503, "JADX wrapper not initialized", logger);
                return;
            }

            // Pre-compile the string-literal extraction pattern
            Pattern literalPattern = Pattern.compile("\"([^\"\n]{" + minLength + ",})\"");

            // Pre-compile or prepare user pattern
            Pattern userRegex = null;
            String userSubstring = null;
            if (useRegex) {
                try {
                    userRegex = Pattern.compile(pattern);
                } catch (Exception e) {
                    JadxAIMCPPluginError.handleError(ctx, 400, "Invalid regex pattern: " + e.getMessage(), logger);
                    return;
                }
            } else {
                userSubstring = pattern.toLowerCase(Locale.ROOT);
            }

            List<JavaClass> allClasses = wrapper.getIncludedClassesWithInners();
            int totalClasses = allClasses.size();
            int scannedCount = 0;
            int cachedCount = 0;

            List<Map<String, Object>> results = new ArrayList<>();
            boolean truncated = false;

            // Count total cached for reporting
            for (JavaClass cls : allClasses) {
                try {
                    if (cls.getClassNode() != null && cls.getClassNode().getState().isProcessComplete()) {
                        cachedCount++;
                    }
                } catch (Exception ignored) {
                }
            }

            for (JavaClass cls : allClasses) {
                if (results.size() >= limit) {
                    truncated = true;
                    break;
                }

                // Apply class filter
                String fullName = cls.getFullName();
                if (classFilter != null && !classFilter.isEmpty()) {
                    if (!fullName.contains(classFilter)) continue;
                }

                // Only scan cached classes
                boolean isCached = false;
                try {
                    isCached = cls.getClassNode() != null && cls.getClassNode().getState().isProcessComplete();
                } catch (Exception ignored) {
                }
                if (!isCached) continue;

                scannedCount++;

                // Read cached code without triggering decompilation
                String code = ClassCacheManager.getCachedCodeDirect(cls);
                if (code == null || code.isEmpty()) continue;

                Matcher litMatcher = literalPattern.matcher(code);
                String[] lines = null; // lazy split

                while (litMatcher.find()) {
                    if (results.size() >= limit) {
                        truncated = true;
                        break;
                    }
                    String literal = litMatcher.group(1);
                    boolean matches;
                    if (useRegex) {
                        matches = userRegex.matcher(literal).find();
                    } else {
                        matches = literal.toLowerCase(Locale.ROOT).contains(userSubstring);
                    }
                    if (!matches) continue;

                    // Calculate approximate line number
                    if (lines == null) lines = code.split("\n", -1);
                    int lineNum = findLineNumber(code, litMatcher.start());

                    Map<String, Object> entry = new LinkedHashMap<>();
                    entry.put("class_name", fullName);
                    entry.put("literal", literal);
                    entry.put("line_number", lineNum);
                    results.add(entry);
                }
            }

            int cachedPct = totalClasses > 0 ? (cachedCount * 100 / totalClasses) : 0;

            Map<String, Object> response = new LinkedHashMap<>();
            response.put("results", results);
            response.put("total", results.size());
            response.put("truncated", truncated);
            response.put("limit", limit);
            response.put("scanned_classes", scannedCount);
            response.put("cached_percentage_at_scan", cachedPct);
            ctx.json(response);

        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Failed to search string literals: " + e.getMessage(), e, logger);
        }
    }

    private int findLineNumber(String code, int charPos) {
        int line = 1;
        for (int i = 0; i < charPos && i < code.length(); i++) {
            if (code.charAt(i) == '\n') line++;
        }
        return line;
    }

    // -------------------------------------------------------------------------
    // GET /export-callgraph
    // -------------------------------------------------------------------------

    /**
     * GET /export-callgraph
     *
     * BFS call-graph export starting from a specified method.
     *
     * Query params:
     *   class   (required)
     *   method  (required)
     *   depth   (optional, default 3, max 6)
     *   format  (optional, "json" or "dot", default "json")
     */
    public void handleExportCallgraph(Context ctx) {
        String className = ctx.queryParam("class");
        String methodName = ctx.queryParam("method");

        if (className == null || className.isEmpty()) {
            JadxAIMCPPluginError.handleError(ctx, 400, "Missing required parameter 'class'", logger);
            return;
        }
        if (methodName == null || methodName.isEmpty()) {
            JadxAIMCPPluginError.handleError(ctx, 400, "Missing required parameter 'method'", logger);
            return;
        }

        int maxDepth;
        try {
            String dp = ctx.queryParam("depth");
            maxDepth = (dp != null && !dp.isEmpty()) ? Integer.parseInt(dp) : 3;
        } catch (NumberFormatException e) {
            maxDepth = 3;
        }
        if (maxDepth < 1) maxDepth = 1;
        if (maxDepth > 6) maxDepth = 6;

        String format = ctx.queryParam("format");
        if (format == null || format.isEmpty()) format = "json";
        format = format.toLowerCase(Locale.ROOT);

        try {
            JadxWrapper wrapper = mainWindow.getWrapper();
            if (wrapper == null) {
                JadxAIMCPPluginError.handleError(ctx, 503, "JADX wrapper not initialized", logger);
                return;
            }

            // Initialize cache if needed
            if (ClassCacheManager.getStatus() == ClassCacheManager.CacheStatus.NOT_INITIALIZED) {
                ClassCacheManager.initCache(wrapper);
            }

            Map<String, JavaClass> classMap = ClassCacheManager.getCache();
            JavaClass cls = ClassCacheManager.findClass(classMap, className);
            if (cls == null) {
                JadxAIMCPPluginError.handleError(ctx, 404, "Class not found: " + className, logger);
                return;
            }

            // Find root method
            JavaMethod rootMethod = null;
            String strippedName = methodName.contains("(") ? methodName.substring(0, methodName.indexOf('(')) : methodName;
            for (JavaMethod m : cls.getMethods()) {
                if (JadxApiAdapter.matchesMethodName(m, strippedName)) {
                    rootMethod = m;
                    break;
                }
            }
            if (rootMethod == null) {
                JadxAIMCPPluginError.handleError(ctx, 404,
                    "Method '" + methodName + "' not found in class " + className, logger);
                return;
            }

            // We need decompile lock to safely walk method nodes
            if (!JadxSearchLock.tryAcquire(30)) {
                ctx.status(503).json(Map.of(
                    "error", "Decompilation operation in progress, retry later",
                    "retry_after", JadxSearchLock.RETRY_AFTER_SECONDS
                ));
                return;
            }

            Map<String, Map<String, Object>> nodes = new LinkedHashMap<>();
            List<Map<String, String>> edges = new ArrayList<>();
            boolean truncated = false;

            // Declare rootId outside try so it's accessible after the finally block
            final String rootId = buildMethodId(cls.getFullName(), rootMethod);

            try {
                // BFS
                Map<String, Object> rootNode = buildNodeEntry(cls.getFullName(), rootMethod);
                nodes.put(rootId, rootNode);

                // Queue entries: [methodId, JavaMethod, currentDepth]
                Queue<Object[]> queue = new ArrayDeque<>();
                queue.add(new Object[]{rootId, rootMethod, 0});
                Set<String> visited = new LinkedHashSet<>();
                visited.add(rootId);

                final int MAX_NODES = 500;

                while (!queue.isEmpty()) {
                    Object[] entry = queue.poll();
                    String fromId = (String) entry[0];
                    JavaMethod fromMethod = (JavaMethod) entry[1];
                    int depth = (int) entry[2];

                    if (depth >= maxDepth) continue;

                    List<Map<String, Object>> callees = collectCalleesForMethod(fromMethod);
                    for (Map<String, Object> callee : callees) {
                        String toClass = (String) callee.get("class_name");
                        String toMethod = (String) callee.get("method_name");
                        String toId = toClass + "#" + toMethod;

                        // Add edge
                        Map<String, String> edge = new LinkedHashMap<>();
                        edge.put("from", fromId);
                        edge.put("to", toId);
                        edges.add(edge);

                        if (!visited.contains(toId)) {
                            visited.add(toId);
                            // Build node entry from callee info
                            Map<String, Object> nodeEntry = new LinkedHashMap<>();
                            nodeEntry.put("id", toId);
                            nodeEntry.put("class", toClass);
                            nodeEntry.put("method", toMethod);
                            nodeEntry.put("signature", callee.getOrDefault("short_id", ""));
                            nodes.put(toId, nodeEntry);

                            if (nodes.size() >= MAX_NODES) {
                                truncated = true;
                                break;
                            }

                            // Look up JavaMethod to recurse
                            JavaClass toJavaCls = ClassCacheManager.findClass(classMap, toClass);
                            if (toJavaCls != null && depth + 1 < maxDepth) {
                                JavaMethod toJavaMethod = null;
                                String calleeMethodSimple = toMethod.contains("(")
                                    ? toMethod.substring(0, toMethod.indexOf('(')) : toMethod;
                                for (JavaMethod m : toJavaCls.getMethods()) {
                                    if (JadxApiAdapter.matchesMethodName(m, calleeMethodSimple)) {
                                        toJavaMethod = m;
                                        break;
                                    }
                                }
                                if (toJavaMethod != null) {
                                    queue.add(new Object[]{toId, toJavaMethod, depth + 1});
                                }
                            }
                        }
                    }

                    if (truncated) break;
                }
            } finally {
                JadxSearchLock.release();
            }

            String finalFormat = format;
            if ("dot".equals(finalFormat)) {
                String dot = buildDotGraph(rootId, nodes, edges);
                Map<String, Object> response = new LinkedHashMap<>();
                response.put("format", "dot");
                response.put("dot", dot);
                ctx.json(response);
            } else {
                Map<String, Object> response = new LinkedHashMap<>();
                response.put("format", "json");
                response.put("root", rootId);
                response.put("depth", maxDepth);
                response.put("nodes", new ArrayList<>(nodes.values()));
                response.put("edges", edges);
                response.put("truncated", truncated);
                ctx.json(response);
            }

        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Failed to export call graph: " + e.getMessage(), e, logger);
        }
    }

    private String buildMethodId(String clsName, JavaMethod method) {
        String name = method.getName();
        JadxApiAdapter.MethodInfoSnapshot info = JadxApiAdapter.getMethodInfo(method);
        String shortId = info != null ? info.getShortId() : null;
        return clsName + "#" + (shortId != null ? shortId : name + "()");
    }

    private Map<String, Object> buildNodeEntry(String clsName, JavaMethod method) {
        String name = method.getName();
        JadxApiAdapter.MethodInfoSnapshot info = JadxApiAdapter.getMethodInfo(method);
        String shortId = info != null ? info.getShortId() : null;
        String id = clsName + "#" + (shortId != null ? shortId : name + "()");
        Map<String, Object> node = new LinkedHashMap<>();
        node.put("id", id);
        node.put("class", clsName);
        node.put("method", name);
        node.put("signature", shortId != null ? shortId : "");
        return node;
    }

    /**
     * Collect callee method info maps from a JavaMethod using instruction walking.
     * Uses the same fallback approach as MethodRoutes.
     */
    private List<Map<String, Object>> collectCalleesForMethod(JavaMethod method) {
        List<Map<String, Object>> callees = new ArrayList<>();
        MethodNode methodNode = JadxApiAdapter.getInternalMethodNode(method);
        if (methodNode == null) return callees;

        InsnNode[] instructions = methodNode.getInstructions();
        if (instructions == null) return callees;

        Set<String> seen = new HashSet<>();
        for (InsnNode insn : instructions) {
            collectInvokeCalleesFromInsn(methodNode, insn, callees, seen);
        }
        return callees;
    }

    private void collectInvokeCalleesFromInsn(
            MethodNode callerNode,
            InsnNode insn,
            List<Map<String, Object>> out,
            Set<String> seen) {
        if (insn == null) return;
        if (insn instanceof BaseInvokeNode) {
            jadx.core.dex.info.MethodInfo calledMethodInfo = ((BaseInvokeNode) insn).getCallMth();
            if (calledMethodInfo != null) {
                String calleeClass = calledMethodInfo.getDeclClass().getFullName();
                String calleeMethod = calledMethodInfo.getName();
                String key = calleeClass + "#" + calledMethodInfo.getShortId();
                if (seen.add(key)) {
                    Map<String, Object> entry = new LinkedHashMap<>();
                    entry.put("class_name", calleeClass);
                    entry.put("method_name", calleeMethod);
                    entry.put("short_id", calledMethodInfo.getShortId());
                    out.add(entry);
                }
            }
        }
        for (InsnArg arg : insn.getArguments()) {
            if (arg.isInsnWrap()) {
                collectInvokeCalleesFromInsn(callerNode, ((InsnWrapArg) arg).getWrapInsn(), out, seen);
            }
        }
    }

    private String buildDotGraph(String rootId,
                                  Map<String, Map<String, Object>> nodes,
                                  List<Map<String, String>> edges) {
        StringBuilder sb = new StringBuilder("digraph callgraph {\n");
        sb.append("  rankdir=LR;\n");
        sb.append("  node [shape=box];\n");
        for (Map.Entry<String, Map<String, Object>> e : nodes.entrySet()) {
            String id = e.getKey();
            String label = id.equals(rootId) ? id + " [ROOT]" : id;
            sb.append("  \"").append(escapeForDot(id)).append("\" [label=\"")
              .append(escapeForDot(label)).append("\"];\n");
        }
        for (Map<String, String> edge : edges) {
            sb.append("  \"").append(escapeForDot(edge.get("from")))
              .append("\" -> \"").append(escapeForDot(edge.get("to")))
              .append("\";\n");
        }
        sb.append("}");
        return sb.toString();
    }

    private String escapeForDot(String s) {
        if (s == null) return "";
        return s.replace("\\", "\\\\").replace("\"", "\\\"");
    }

    // -------------------------------------------------------------------------
    // XML helpers (shared with ManifestInfoService pattern)
    // -------------------------------------------------------------------------

    private Document parseXml(String xmlContent) {
        try {
            DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
            factory.setFeature(XMLConstants.FEATURE_SECURE_PROCESSING, true);
            factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
            factory.setFeature("http://xml.org/sax/features/external-general-entities", false);
            factory.setFeature("http://xml.org/sax/features/external-parameter-entities", false);
            factory.setFeature("http://apache.org/xml/features/nonvalidating/load-external-dtd", false);
            factory.setNamespaceAware(true);
            factory.setXIncludeAware(false);
            factory.setExpandEntityReferences(false);
            DocumentBuilder builder = factory.newDocumentBuilder();
            try (StringReader reader = new StringReader(xmlContent)) {
                return builder.parse(new InputSource(reader));
            }
        } catch (Exception e) {
            logger.debug("parseXml failed: {}", e.getMessage());
            return null;
        }
    }

    private Element getFirstElement(Document doc, String tagName) {
        NodeList nodes = doc.getElementsByTagName(tagName);
        if (nodes.getLength() == 0) return null;
        Node n = nodes.item(0);
        return n instanceof Element ? (Element) n : null;
    }

    private String getAndroidAttr(Element el, String localName) {
        if (el == null) return null;
        String val = emptyToNull(el.getAttributeNS(ANDROID_NS, localName));
        if (val != null) return val;
        return emptyToNull(el.getAttribute("android:" + localName));
    }

    private String normalizeComponentName(String pkgName, String componentName) {
        String val = emptyToNull(componentName);
        if (val == null) return null;
        if (val.startsWith(".")) return pkgName == null ? val : pkgName + val;
        if (val.contains(".")) return val;
        return pkgName == null ? val : pkgName + "." + val;
    }

    private String emptyToNull(String value) {
        if (value == null) return null;
        String t = value.trim();
        return t.isEmpty() ? null : t;
    }
}
