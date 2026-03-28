package com.zin.jadxaimcp.utils;

import jadx.api.ResourceFile;
import jadx.core.utils.android.AndroidManifestParser;
import jadx.core.xmlgen.ResContainer;
import jadx.gui.JadxWrapper;

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
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.WeakHashMap;

/**
 * Shared AndroidManifest.xml parsing service with cached results.
 */
public final class ManifestInfoService {
    private static final Logger logger = LoggerFactory.getLogger(ManifestInfoService.class);
    private static final String ANDROID_NS = "http://schemas.android.com/apk/res/android";
    private static final ManifestInfoService INSTANCE = new ManifestInfoService();

    private final Map<ResourceFile, Optional<ManifestInfo>> manifestInfoCache =
            Collections.synchronizedMap(new WeakHashMap<>());

    private ManifestInfoService() {
    }

    public static ManifestInfoService getInstance() {
        return INSTANCE;
    }

    public ResourceFile getManifestFile(JadxWrapper wrapper) {
        if (wrapper == null) {
            return null;
        }
        List<ResourceFile> resources = wrapper.getResources();
        if (resources == null || resources.isEmpty()) {
            return null;
        }
        return AndroidManifestParser.getAndroidManifest(resources);
    }

    public boolean hasManifest(JadxWrapper wrapper) {
        return getManifestFile(wrapper) != null;
    }

    public String getManifestContent(JadxWrapper wrapper) {
        return getManifestContent(getManifestFile(wrapper));
    }

    public String getManifestContent(ResourceFile manifestFile) {
        return loadManifestContent(manifestFile);
    }

    public Optional<ManifestInfo> getManifestInfo(JadxWrapper wrapper) {
        return getManifestInfo(getManifestFile(wrapper));
    }

    public Optional<ManifestInfo> getManifestInfo(ResourceFile manifestFile) {
        if (manifestFile == null) {
            return Optional.empty();
        }

        synchronized (manifestInfoCache) {
            if (manifestInfoCache.containsKey(manifestFile)) {
                return manifestInfoCache.get(manifestFile);
            }
        }

        Optional<ManifestInfo> parsedInfo = parseManifestInfo(manifestFile);
        synchronized (manifestInfoCache) {
            manifestInfoCache.put(manifestFile, parsedInfo);
        }
        return parsedInfo;
    }

    public String getPackageName(JadxWrapper wrapper) {
        return getManifestInfo(wrapper).map(ManifestInfo::getPackageName).orElse(null);
    }

    public String getPackageName(ResourceFile manifestFile) {
        return getManifestInfo(manifestFile).map(ManifestInfo::getPackageName).orElse(null);
    }

    public String getVersionName(JadxWrapper wrapper) {
        return getManifestInfo(wrapper).map(ManifestInfo::getVersionName).orElse(null);
    }

    public String getVersionName(ResourceFile manifestFile) {
        return getManifestInfo(manifestFile).map(ManifestInfo::getVersionName).orElse(null);
    }

    public String getVersionCode(JadxWrapper wrapper) {
        return getManifestInfo(wrapper).map(ManifestInfo::getVersionCode).orElse(null);
    }

    public String getVersionCode(ResourceFile manifestFile) {
        return getManifestInfo(manifestFile).map(ManifestInfo::getVersionCode).orElse(null);
    }

    public String getApplicationLabel(JadxWrapper wrapper) {
        return getManifestInfo(wrapper).map(ManifestInfo::getApplicationLabel).orElse(null);
    }

    public String getApplicationLabel(ResourceFile manifestFile) {
        return getManifestInfo(manifestFile).map(ManifestInfo::getApplicationLabel).orElse(null);
    }

    public String getMinSdkVersion(JadxWrapper wrapper) {
        return getManifestInfo(wrapper).map(ManifestInfo::getMinSdkVersion).orElse(null);
    }

    public String getMinSdkVersion(ResourceFile manifestFile) {
        return getManifestInfo(manifestFile).map(ManifestInfo::getMinSdkVersion).orElse(null);
    }

    public String getTargetSdkVersion(JadxWrapper wrapper) {
        return getManifestInfo(wrapper).map(ManifestInfo::getTargetSdkVersion).orElse(null);
    }

    public String getTargetSdkVersion(ResourceFile manifestFile) {
        return getManifestInfo(manifestFile).map(ManifestInfo::getTargetSdkVersion).orElse(null);
    }

    public List<String> getPermissions(JadxWrapper wrapper) {
        return getManifestInfo(wrapper).map(ManifestInfo::getPermissions).orElse(Collections.emptyList());
    }

    public List<String> getPermissions(ResourceFile manifestFile) {
        return getManifestInfo(manifestFile).map(ManifestInfo::getPermissions).orElse(Collections.emptyList());
    }

    public List<String> getActivities(JadxWrapper wrapper) {
        return getManifestInfo(wrapper).map(ManifestInfo::getActivities).orElse(Collections.emptyList());
    }

    public List<String> getActivities(ResourceFile manifestFile) {
        return getManifestInfo(manifestFile).map(ManifestInfo::getActivities).orElse(Collections.emptyList());
    }

    public List<String> getServices(JadxWrapper wrapper) {
        return getManifestInfo(wrapper).map(ManifestInfo::getServices).orElse(Collections.emptyList());
    }

    public List<String> getServices(ResourceFile manifestFile) {
        return getManifestInfo(manifestFile).map(ManifestInfo::getServices).orElse(Collections.emptyList());
    }

    public List<String> getReceivers(JadxWrapper wrapper) {
        return getManifestInfo(wrapper).map(ManifestInfo::getReceivers).orElse(Collections.emptyList());
    }

    public List<String> getReceivers(ResourceFile manifestFile) {
        return getManifestInfo(manifestFile).map(ManifestInfo::getReceivers).orElse(Collections.emptyList());
    }

    public List<String> getProviders(JadxWrapper wrapper) {
        return getManifestInfo(wrapper).map(ManifestInfo::getProviders).orElse(Collections.emptyList());
    }

    public List<String> getProviders(ResourceFile manifestFile) {
        return getManifestInfo(manifestFile).map(ManifestInfo::getProviders).orElse(Collections.emptyList());
    }

    public String getMainActivity(JadxWrapper wrapper) {
        return getManifestInfo(wrapper).map(ManifestInfo::getMainActivity).orElse(null);
    }

    public String getMainActivity(ResourceFile manifestFile) {
        return getManifestInfo(manifestFile).map(ManifestInfo::getMainActivity).orElse(null);
    }

    public boolean isDebuggable(JadxWrapper wrapper) {
        return getManifestInfo(wrapper).map(ManifestInfo::isDebuggable).orElse(false);
    }

    public boolean isDebuggable(ResourceFile manifestFile) {
        return getManifestInfo(manifestFile).map(ManifestInfo::isDebuggable).orElse(false);
    }

    private Optional<ManifestInfo> parseManifestInfo(ResourceFile manifestFile) {
        try {
            String manifestContent = loadManifestContent(manifestFile);
            if (manifestContent == null || manifestContent.trim().isEmpty()) {
                return Optional.empty();
            }

            Document document = parseXml(manifestContent);
            Element manifestElement = getFirstElement(document, "manifest");
            if (manifestElement == null) {
                return Optional.empty();
            }

            String packageName = emptyToNull(manifestElement.getAttribute("package"));
            Element applicationElement = getFirstElement(document, "application");
            Element usesSdkElement = getFirstElement(document, "uses-sdk");

            String versionName = getAndroidAttribute(manifestElement, "versionName");
            String versionCode = getAndroidAttribute(manifestElement, "versionCode");
            String applicationLabel = applicationElement != null ? getAndroidAttribute(applicationElement, "label") : null;
            String minSdkVersion = usesSdkElement != null ? getAndroidAttribute(usesSdkElement, "minSdkVersion") : null;
            String targetSdkVersion = usesSdkElement != null ? getAndroidAttribute(usesSdkElement, "targetSdkVersion") : null;
            boolean debuggable = applicationElement != null
                    && Boolean.parseBoolean(getAndroidAttribute(applicationElement, "debuggable"));

            List<String> permissions = parsePermissions(manifestElement);
            List<String> activities = parseComponents(applicationElement, "activity", packageName);
            List<String> services = parseComponents(applicationElement, "service", packageName);
            List<String> receivers = parseComponents(applicationElement, "receiver", packageName);
            List<String> providers = parseComponents(applicationElement, "provider", packageName);
            String mainActivity = detectMainActivity(applicationElement, packageName);

            return Optional.of(new ManifestInfo(
                    manifestContent,
                    packageName,
                    versionName,
                    versionCode,
                    applicationLabel,
                    minSdkVersion,
                    targetSdkVersion,
                    permissions,
                    activities,
                    services,
                    receivers,
                    providers,
                    mainActivity,
                    debuggable));
        } catch (Exception e) {
            logger.debug("Failed to parse AndroidManifest.xml: {}", e.getMessage());
            return Optional.empty();
        }
    }

    private String loadManifestContent(ResourceFile manifestFile) {
        if (manifestFile == null) {
            return null;
        }
        try {
            ResContainer container = manifestFile.loadContent();
            if (container == null || container.getText() == null) {
                return null;
            }
            return container.getText().getCodeStr();
        } catch (Exception e) {
            logger.debug("Failed to load AndroidManifest.xml content: {}", e.getMessage());
            return null;
        }
    }

    private Document parseXml(String xmlContent) throws Exception {
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
            InputSource source = new InputSource(reader);
            return builder.parse(source);
        }
    }

    private Element getFirstElement(Document document, String tagName) {
        NodeList nodes = document.getElementsByTagName(tagName);
        if (nodes.getLength() == 0) {
            return null;
        }
        Node node = nodes.item(0);
        return node instanceof Element ? (Element) node : null;
    }

    private List<String> parsePermissions(Element manifestElement) {
        if (manifestElement == null) {
            return Collections.emptyList();
        }
        LinkedHashSet<String> permissions = new LinkedHashSet<>();
        NodeList children = manifestElement.getChildNodes();
        for (int i = 0; i < children.getLength(); i++) {
            Node node = children.item(i);
            if (!(node instanceof Element)) {
                continue;
            }
            Element element = (Element) node;
            String tagName = element.getTagName();
            if (!"uses-permission".equals(tagName) && !"uses-permission-sdk-23".equals(tagName)) {
                continue;
            }
            String permission = getAndroidAttribute(element, "name");
            if (permission != null) {
                permissions.add(permission);
            }
        }
        return Collections.unmodifiableList(new ArrayList<>(permissions));
    }

    private List<String> parseComponents(Element applicationElement, String tagName, String packageName) {
        if (applicationElement == null) {
            return Collections.emptyList();
        }
        LinkedHashSet<String> components = new LinkedHashSet<>();
        NodeList children = applicationElement.getChildNodes();
        for (int i = 0; i < children.getLength(); i++) {
            Node node = children.item(i);
            if (!(node instanceof Element)) {
                continue;
            }
            Element element = (Element) node;
            if (!tagName.equals(element.getTagName())) {
                continue;
            }
            String componentName = normalizeComponentName(packageName, getAndroidAttribute(element, "name"));
            if (componentName != null) {
                components.add(componentName);
            }
        }
        return Collections.unmodifiableList(new ArrayList<>(components));
    }

    private String detectMainActivity(Element applicationElement, String packageName) {
        if (applicationElement == null) {
            return null;
        }
        NodeList children = applicationElement.getChildNodes();
        for (int i = 0; i < children.getLength(); i++) {
            Node node = children.item(i);
            if (!(node instanceof Element)) {
                continue;
            }
            Element component = (Element) node;
            String tagName = component.getTagName();
            if (!"activity".equals(tagName) && !"activity-alias".equals(tagName)) {
                continue;
            }
            if (!hasLauncherIntentFilter(component)) {
                continue;
            }

            String attributeName = "activity-alias".equals(tagName) ? "targetActivity" : "name";
            String mainActivity = normalizeComponentName(packageName, getAndroidAttribute(component, attributeName));
            if (mainActivity != null) {
                return mainActivity;
            }
            if ("activity-alias".equals(tagName)) {
                return normalizeComponentName(packageName, getAndroidAttribute(component, "name"));
            }
        }
        return null;
    }

    private boolean hasLauncherIntentFilter(Element componentElement) {
        NodeList children = componentElement.getChildNodes();
        for (int i = 0; i < children.getLength(); i++) {
            Node node = children.item(i);
            if (!(node instanceof Element)) {
                continue;
            }
            Element intentFilter = (Element) node;
            if (!"intent-filter".equals(intentFilter.getTagName())) {
                continue;
            }
            boolean hasMainAction = false;
            boolean hasLauncherCategory = false;
            NodeList filterChildren = intentFilter.getChildNodes();
            for (int j = 0; j < filterChildren.getLength(); j++) {
                Node filterNode = filterChildren.item(j);
                if (!(filterNode instanceof Element)) {
                    continue;
                }
                Element filterElement = (Element) filterNode;
                if ("action".equals(filterElement.getTagName())) {
                    hasMainAction |= "android.intent.action.MAIN".equals(getAndroidAttribute(filterElement, "name"));
                } else if ("category".equals(filterElement.getTagName())) {
                    String categoryName = getAndroidAttribute(filterElement, "name");
                    hasLauncherCategory |= "android.intent.category.LAUNCHER".equals(categoryName)
                            || "android.intent.category.LEANBACK_LAUNCHER".equals(categoryName);
                }
            }
            if (hasMainAction && hasLauncherCategory) {
                return true;
            }
        }
        return false;
    }

    private String getAndroidAttribute(Element element, String localName) {
        if (element == null) {
            return null;
        }
        String value = emptyToNull(element.getAttributeNS(ANDROID_NS, localName));
        if (value != null) {
            return value;
        }
        return emptyToNull(element.getAttribute("android:" + localName));
    }

    private String normalizeComponentName(String packageName, String componentName) {
        String value = emptyToNull(componentName);
        if (value == null) {
            return null;
        }
        if (value.startsWith(".")) {
            return packageName == null ? value : packageName + value;
        }
        if (value.contains(".")) {
            return value;
        }
        return packageName == null ? value : packageName + "." + value;
    }

    private String emptyToNull(String value) {
        if (value == null) {
            return null;
        }
        String trimmed = value.trim();
        return trimmed.isEmpty() ? null : trimmed;
    }

    public static final class ManifestInfo {
        private final String manifestContent;
        private final String packageName;
        private final String versionName;
        private final String versionCode;
        private final String applicationLabel;
        private final String minSdkVersion;
        private final String targetSdkVersion;
        private final List<String> permissions;
        private final List<String> activities;
        private final List<String> services;
        private final List<String> receivers;
        private final List<String> providers;
        private final String mainActivity;
        private final boolean debuggable;

        private ManifestInfo(
                String manifestContent,
                String packageName,
                String versionName,
                String versionCode,
                String applicationLabel,
                String minSdkVersion,
                String targetSdkVersion,
                List<String> permissions,
                List<String> activities,
                List<String> services,
                List<String> receivers,
                List<String> providers,
                String mainActivity,
                boolean debuggable) {
            this.manifestContent = manifestContent;
            this.packageName = packageName;
            this.versionName = versionName;
            this.versionCode = versionCode;
            this.applicationLabel = applicationLabel;
            this.minSdkVersion = minSdkVersion;
            this.targetSdkVersion = targetSdkVersion;
            this.permissions = permissions;
            this.activities = activities;
            this.services = services;
            this.receivers = receivers;
            this.providers = providers;
            this.mainActivity = mainActivity;
            this.debuggable = debuggable;
        }

        public String getManifestContent() {
            return manifestContent;
        }

        public String getPackageName() {
            return packageName;
        }

        public String getVersionName() {
            return versionName;
        }

        public String getVersionCode() {
            return versionCode;
        }

        public String getApplicationLabel() {
            return applicationLabel;
        }

        public String getMinSdkVersion() {
            return minSdkVersion;
        }

        public String getTargetSdkVersion() {
            return targetSdkVersion;
        }

        public List<String> getPermissions() {
            return permissions;
        }

        public List<String> getActivities() {
            return activities;
        }

        public List<String> getServices() {
            return services;
        }

        public List<String> getReceivers() {
            return receivers;
        }

        public List<String> getProviders() {
            return providers;
        }

        public String getMainActivity() {
            return mainActivity;
        }

        public boolean isDebuggable() {
            return debuggable;
        }
    }
}
