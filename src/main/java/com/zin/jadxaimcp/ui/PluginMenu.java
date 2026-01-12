package com.zin.jadxaimcp.ui;

import com.zin.jadxaimcp.JadxAIMCP;
import jadx.gui.ui.MainWindow;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import javax.swing.*;
import java.awt.*;

public class PluginMenu {
    private static final Logger logger = LoggerFactory.getLogger(PluginMenu.class);
    private MainWindow mainWindow;
    private final JadxAIMCP plugin;

    public PluginMenu(MainWindow mainWindow, JadxAIMCP plugin) {
        this.mainWindow = mainWindow;
        this.plugin = plugin;
    }

    /**
     * @return void
     * 
     * This method creates and adds plugin UI menu items to the JADX menu bar.
     * 1. It runs on the Swing EDT thread using SwingUtilities.invokeLater()
     * 2. It retrieves the main window's menu bar
     * 3. It finds or creates a "Plugins" menu in the menu bar
     * 4. It creates a "JADX AI MCP Server" submenu with the following items:
     *    - Configure Port: Opens dialog to change server port
     *    - Default Port: Resets to default port (8650) and restarts server
     *    - Restart Server: Manually restarts the MCP server
     *    - Server Status: Shows current server status and connection details
     * 5. It adds the submenu to the plugins menu
     * 
     * All UI operations are performed on the EDT to ensure thread safety.
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

                // 1. Configure Port
                JMenuItem portItem = new JMenuItem("Configure Port...");
                portItem.addActionListener(e -> showPortConfigDialog());

                // 2. Default Port
                JMenuItem defaultPortItem = new JMenuItem("Default Port");
                defaultPortItem.addActionListener(e -> {
                    plugin.resetToDefaultPort();
                    plugin.restartServer();
                });

                // 3. Restart Server
                JMenuItem restartItem = new JMenuItem("Restart Server");
                restartItem.addActionListener(e -> plugin.restartServer());

                // 4. Server Status
                JMenuItem statusItem = new JMenuItem("Server Status");
                statusItem.addActionListener(e -> showServerStatus());

                // 5. Authentication Settings
                JMenuItem authItem = new JMenuItem("Authentication Settings...");
                authItem.addActionListener(e -> showAuthSettingsDialog());

                mcpMenu.add(portItem);
                mcpMenu.add(defaultPortItem);
                mcpMenu.addSeparator();
                mcpMenu.add(restartItem);
                mcpMenu.add(statusItem);
                mcpMenu.addSeparator();
                mcpMenu.add(authItem);
                pluginsMenu.add(mcpMenu);
                
                logger.debug("JADX-AI-MCP Plugin: Menu items added");
            } catch (Exception e) {

            }
        });
    }
    
    /**
     * @param menuBar The main window's menu bar
     * @return JMenu The existing or newly created Plugins menu
     * 
     * This method locates or creates the "Plugins" menu in the JADX menu bar.
     * 1. It searches through existing menus for one named "Plugins" or "Plugin"
     * 2. If found, it returns the existing menu
     * 3. If not found, it creates a new "Plugins" menu
     * 4. It attempts to insert the new menu before the "Help" menu if it exists
     * 5. Otherwise, it appends the menu to the end of the menu bar
     * 
     * This ensures consistent menu organization across different JADX versions.
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
     * @return void
     * 
     * This method displays a dialog for configuring the server port.
     * 1. It shows an input dialog with the current port as default value
     * 2. It validates the input is a valid integer
     * 3. It ensures the port is in the valid range (1024-65535)
     * 4. If the port differs from current port, it:
     *    - Updates the port configuration
     *    - Restarts the server on the new port
     * 5. It displays error messages for invalid input or out-of-range values
     * 
     * Ports below 1024 are reserved and require root privileges.
     */
    private void showPortConfigDialog() {
        String input = JOptionPane.showInputDialog(mainWindow,
            "Enter Server Port (1024-65535):", String.valueOf(plugin.getCurrentPort())
        );

        if (input != null) {
            try {
                int newPort = Integer.parseInt(input.trim());
                if (newPort >= 1024 && newPort <= 65535) {
                    if (newPort != plugin.getCurrentPort()) {
                        plugin.updatePort(newPort);
                        plugin.restartServer();
                    }
                } else {
                    JOptionPane.showMessageDialog(mainWindow, "Port must be between 1024 and 65535",
                        "Ivalid Port", JOptionPane.ERROR_MESSAGE);
                }
            } catch (NumberFormatException ex) {
                JOptionPane.showMessageDialog(mainWindow, "Invalid number format",
                    "Error", JOptionPane.ERROR_MESSAGE
                );
            }
        }
    }

    /**
     * @return void
     *
     * This method displays the current server status in a dialog.
     * 1. It checks whether the server is currently running
     * 2. It retrieves the configured port number
     * 3. It constructs the server URL if running (http://127.0.0.1:<port>/)
     * 4. It displays a dialog showing:
     *    - Status (Running/Stopped)
     *    - Port number
     *    - Server URL (or N/A if stopped)
     *
     * This provides users with quick access to connection information.
     */
    private void showServerStatus() {
        boolean running = plugin.isServerRunning();
        String status = running ? "Running" : "Stopped";
        String url = running ? "http://127.0.0.1:" + plugin.getCurrentPort() + "/" : "N/A";

        JOptionPane.showMessageDialog(mainWindow,
            "Status " + status + "\nPort: " + plugin.getCurrentPort() + "\nURL: " + url,
            "MCP Server Status", JOptionPane.INFORMATION_MESSAGE);
    }

    /**
     * @return void
     *
     * This method displays the authentication settings dialog with options to:
     * 1. View the current authentication token
     * 2. Enable/disable authentication
     * 3. Regenerate the authentication token
     * 4. Copy token to clipboard
     *
     * The dialog shows:
     * - Current authentication status (Enabled/Disabled)
     * - Authentication token (with copy button)
     * - Config file location
     * - Options to toggle auth and regenerate token
     */
    private void showAuthSettingsDialog() {
        var authConfig = plugin.getAuthConfig();
        if (authConfig == null) {
            JOptionPane.showMessageDialog(mainWindow,
                "Authentication configuration not available",
                "Error", JOptionPane.ERROR_MESSAGE);
            return;
        }

        JPanel panel = new JPanel();
        panel.setLayout(new BoxLayout(panel, BoxLayout.Y_AXIS));
        panel.setBorder(BorderFactory.createEmptyBorder(10, 10, 10, 10));

        // Status
        JLabel statusLabel = new JLabel("Status: " + (authConfig.isAuthEnabled() ? "ENABLED" : "DISABLED"));
        statusLabel.setFont(statusLabel.getFont().deriveFont(Font.BOLD, 14f));
        if (authConfig.isAuthEnabled()) {
            statusLabel.setForeground(new Color(0, 128, 0));
        } else {
            statusLabel.setForeground(new Color(200, 100, 0));
        }

        // Token display
        JPanel tokenPanel = new JPanel(new BorderLayout(5, 0));
        JTextField tokenField = new JTextField(authConfig.getAuthToken());
        tokenField.setEditable(false);
        tokenField.setFont(new Font("Monospaced", Font.PLAIN, 12));

        JButton copyButton = new JButton("Copy");
        copyButton.addActionListener(e -> {
            Toolkit.getDefaultToolkit().getSystemClipboard()
                .setContents(new java.awt.datatransfer.StringSelection(authConfig.getAuthToken()), null);
            JOptionPane.showMessageDialog(mainWindow, "Token copied to clipboard!",
                "Success", JOptionPane.INFORMATION_MESSAGE);
        });

        tokenPanel.add(new JLabel("Token: "), BorderLayout.WEST);
        tokenPanel.add(tokenField, BorderLayout.CENTER);
        tokenPanel.add(copyButton, BorderLayout.EAST);

        // Config file location
        JLabel configLabel = new JLabel("Config: " + authConfig.getConfigFilePath());
        configLabel.setFont(new Font("Dialog", Font.PLAIN, 10));
        configLabel.setForeground(Color.GRAY);

        // Buttons
        JPanel buttonPanel = new JPanel(new FlowLayout(FlowLayout.CENTER, 10, 10));

        JButton toggleButton = new JButton(authConfig.isAuthEnabled() ? "Disable Auth" : "Enable Auth");
        toggleButton.addActionListener(e -> {
            authConfig.setAuthEnabled(!authConfig.isAuthEnabled());
            JOptionPane.showMessageDialog(mainWindow,
                "Authentication " + (authConfig.isAuthEnabled() ? "enabled" : "disabled") +
                ".\n\nPlease restart the server for changes to take effect.\n" +
                "Make sure to update your MCP client configuration with the token if enabling auth.",
                "Authentication Updated", JOptionPane.INFORMATION_MESSAGE);
        });

        JButton regenerateButton = new JButton("Regenerate Token");
        regenerateButton.addActionListener(e -> {
            int confirm = JOptionPane.showConfirmDialog(mainWindow,
                "Are you sure you want to regenerate the token?\n" +
                "This will invalidate the current token and you'll need to update your MCP client.",
                "Confirm Regeneration", JOptionPane.YES_NO_OPTION, JOptionPane.WARNING_MESSAGE);

            if (confirm == JOptionPane.YES_OPTION) {
                authConfig.regenerateToken();
                JOptionPane.showMessageDialog(mainWindow,
                    "Token regenerated successfully!\n\n" +
                    "New token: " + authConfig.getAuthToken() + "\n\n" +
                    "Please restart the server and update your MCP client configuration.",
                    "Token Regenerated", JOptionPane.INFORMATION_MESSAGE);
            }
        });

        buttonPanel.add(toggleButton);
        buttonPanel.add(regenerateButton);

        // Add all components
        panel.add(statusLabel);
        panel.add(Box.createVerticalStrut(15));
        panel.add(tokenPanel);
        panel.add(Box.createVerticalStrut(5));
        panel.add(configLabel);
        panel.add(Box.createVerticalStrut(15));
        panel.add(new JLabel("<html><b>Note:</b> Update your jadx_mcp_server.py configuration with --auth-token parameter</html>"));
        panel.add(Box.createVerticalStrut(10));
        panel.add(buttonPanel);

        JOptionPane.showMessageDialog(mainWindow, panel,
            "Authentication Settings", JOptionPane.PLAIN_MESSAGE);
    }
}
