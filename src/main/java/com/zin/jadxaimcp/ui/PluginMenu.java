package com.zin.jadxaimcp.ui;

import com.zin.jadxaimcp.JadxAIMCP;
import jadx.api.plugins.gui.JadxGuiContext;
import jadx.gui.ui.MainWindow;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import javax.swing.*;

/**
 * Plugin Menu
 * 
 * Simplified menu with single "Settings" entry,
 * all configurations are integrated into SettingsDialog.
 *
 * @author JADX AI MCP Team
 */
public class PluginMenu {
    private static final Logger logger = LoggerFactory.getLogger(PluginMenu.class);
    private static final String SETTINGS_MENU_TITLE = "JADX AI MCP Server: Settings...";
    private static final String STATUS_MENU_TITLE = "JADX AI MCP Server: Server Status";

    private final JadxGuiContext guiContext;
    private final MainWindow mainWindow;
    private final JadxAIMCP plugin;

    public PluginMenu(JadxGuiContext guiContext, MainWindow mainWindow, JadxAIMCP plugin) {
        this.guiContext = guiContext;
        this.mainWindow = mainWindow;
        this.plugin = plugin;
    }

    /**
     * Add plugin menu items to JADX menu bar
     */
    public void addMenuItems() {
        try {
            guiContext.addMenuAction(SETTINGS_MENU_TITLE, this::openSettingsDialog);
            guiContext.addMenuAction(STATUS_MENU_TITLE, this::showQuickStatus);
            logger.debug("JADX-AI-MCP Plugin: Menu items registered via JadxGuiContext");
        } catch (Exception e) {
            logger.error("JADX-AI-MCP Plugin: Failed to register menu items", e);
        }
    }

    /**
     * Show quick status information
     */
    private void showQuickStatus() {
        boolean running = plugin.isServerRunning();
        String status = running ? "● Running" : "○ Stopped";
        String bindAddr = plugin.getCurrentBindAddress();
        String url = running ? "http://" + bindAddr + ":" + plugin.getCurrentPort() + "/" : "N/A";

        String instanceName = plugin.getInstanceName();
        if (instanceName == null || instanceName.isEmpty()) {
            instanceName = plugin.getAutoInstanceName();
        }
        
        String apkInfo = plugin.getApkInfo();

        StringBuilder msg = new StringBuilder();
        msg.append("Status: ").append(status).append("\n");
        msg.append("Address: ").append(bindAddr).append(":").append(plugin.getCurrentPort()).append("\n");
        msg.append("URL: ").append(url).append("\n");
        msg.append("Instance: ").append(instanceName != null ? instanceName : "Not set").append("\n");
        msg.append("APK: ").append(apkInfo != null ? apkInfo : "Not loaded");

        guiContext.uiRun(() -> JOptionPane.showMessageDialog(mainWindow, msg.toString(),
            "MCP Server Status", JOptionPane.INFORMATION_MESSAGE));
    }

    private void openSettingsDialog() {
        guiContext.uiRun(() -> {
            SettingsDialog dialog = new SettingsDialog(mainWindow, plugin);
            dialog.setVisible(true);
        });
    }
}
