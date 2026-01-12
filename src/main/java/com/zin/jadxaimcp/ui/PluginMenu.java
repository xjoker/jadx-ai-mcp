package com.zin.jadxaimcp.ui;

import com.zin.jadxaimcp.JadxAIMCP;
import jadx.gui.ui.MainWindow;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import javax.swing.*;

/**
 * 插件菜单
 * 
 * 简化后的菜单，只有单个 "设置" 入口，
 * 所有配置整合到 SettingsDialog 中。
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
     * 添加插件菜单项到 JADX 菜单栏
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

                // 单一设置入口
                JMenuItem settingsItem = new JMenuItem("设置...");
                settingsItem.addActionListener(e -> {
                    SettingsDialog dialog = new SettingsDialog(mainWindow, plugin);
                    dialog.setVisible(true);
                });
                mcpMenu.add(settingsItem);

                // 快速状态显示
                JMenuItem statusItem = new JMenuItem("服务器状态");
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
     * 查找或创建 Plugins 菜单
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
     * 显示快速状态信息
     */
    private void showQuickStatus() {
        boolean running = plugin.isServerRunning();
        String status = running ? "● 运行中" : "○ 已停止";
        String bindAddr = plugin.getCurrentBindAddress();
        String url = running ? "http://" + bindAddr + ":" + plugin.getCurrentPort() + "/" : "N/A";

        String instanceName = plugin.getInstanceName();
        if (instanceName == null || instanceName.isEmpty()) {
            instanceName = plugin.getAutoInstanceName();
        }
        
        String apkInfo = plugin.getApkInfo();

        StringBuilder msg = new StringBuilder();
        msg.append("状态: ").append(status).append("\n");
        msg.append("地址: ").append(bindAddr).append(":").append(plugin.getCurrentPort()).append("\n");
        msg.append("URL: ").append(url).append("\n");
        msg.append("实例名称: ").append(instanceName != null ? instanceName : "未设置").append("\n");
        msg.append("APK: ").append(apkInfo != null ? apkInfo : "未加载");

        JOptionPane.showMessageDialog(mainWindow, msg.toString(),
            "MCP Server 状态", JOptionPane.INFORMATION_MESSAGE);
    }
}
