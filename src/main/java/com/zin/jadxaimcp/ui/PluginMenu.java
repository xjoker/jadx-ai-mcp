package com.zin.jadxaimcp.ui;

import com.zin.jadxaimcp.JadxAIMCP;
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
    private MainWindow mainWindow;
    private final JadxAIMCP plugin;

    public PluginMenu(MainWindow mainWindow, JadxAIMCP plugin) {
        this.mainWindow = mainWindow;
        this.plugin = plugin;
    }

    /**
     * Add plugin menu items to JADX menu bar
     */
    public void addMenuItems() {
        SwingUtilities.invokeLater(() -> {
            try {
                JMenuBar menuBar = mainWindow.getJMenuBar();
                if (menuBar == null) {
                    logger.warn("JADX-AI-MCP Plugin: Menu bar not found");
                    return;
                }

                JMenu pluginsMenu = findOrCreatePluginsMenu(menuBar);
                JMenu mcpMenu = new JMenu("JADX AI MCP Server");

                // Settings entry
                JMenuItem settingsItem = new JMenuItem("Settings...");
                settingsItem.addActionListener(e -> {
                    SettingsDialog dialog = new SettingsDialog(mainWindow, plugin);
                    dialog.setVisible(true);
                });
                mcpMenu.add(settingsItem);

                // Quick status display
                JMenuItem statusItem = new JMenuItem("Server Status");
                statusItem.addActionListener(e -> showQuickStatus());
                mcpMenu.add(statusItem);

                pluginsMenu.add(mcpMenu);
                
                logger.debug("JADX-AI-MCP Plugin: Menu items added");
            } catch (Exception e) {
                logger.error("JADX-AI-MCP Plugin: Failed to add menu items", e);
            }
        });
    }
    
    /**
     * Find or create Plugins menu
     */
    private JMenu findOrCreatePluginsMenu(JMenuBar menuBar) {
        // Look for existing "Plugins" menu
        for (int i = 0; i < menuBar.getMenuCount(); i++) {
            JMenu menu = menuBar.getMenu(i);
            if (menu != null && ("Plugins".equals(menu.getText()) || "Plugin".equals(menu.getText()))) {
                return menu;
            }
        }

        // Create new if not found, inserting before "Help" if possible
        JMenu pluginsMenu = new JMenu("Plugins");
        for (int i = 0; i < menuBar.getMenuCount(); i++) {
            if ("Help".equals(menuBar.getMenu(i).getText())) {
                menuBar.add(pluginsMenu, i);
                return pluginsMenu;
            }
        }
        menuBar.add(pluginsMenu);
        return pluginsMenu;
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

        JOptionPane.showMessageDialog(mainWindow, msg.toString(),
            "MCP Server Status", JOptionPane.INFORMATION_MESSAGE);
    }
}
