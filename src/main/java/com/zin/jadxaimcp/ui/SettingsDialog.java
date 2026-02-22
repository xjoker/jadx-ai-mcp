package com.zin.jadxaimcp.ui;

import com.zin.jadxaimcp.JadxAIMCP;
import com.zin.jadxaimcp.server.AuthConfig;
import jadx.gui.ui.MainWindow;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import javax.swing.*;
import javax.swing.border.TitledBorder;
import java.awt.*;
import java.awt.datatransfer.StringSelection;
import java.awt.event.WindowAdapter;
import java.awt.event.WindowEvent;

/**
 * Unified Settings Dialog
 * 
 * Integrates all plugin configurations into a single interface:
 * - Server configuration (address, port, status)
 * - Instance information (name, APK info)
 * - Authentication configuration (Token, enable switch)
 *
 * @author JADX AI MCP Team
 */
public class SettingsDialog extends JDialog {
    private static final Logger logger = LoggerFactory.getLogger(SettingsDialog.class);
    
    private final MainWindow mainWindow;
    private final JadxAIMCP plugin;
    
    // Server configuration components
    private JLabel statusLabel;
    private JComboBox<String> bindAddressCombo;
    private JTextField portField;
    private JButton restartButton;
    private JButton stopButton;
    
    // Instance information components
    private JTextField instanceNameField;
    private JLabel apkInfoLabel;
    
    // Authentication configuration components
    private JCheckBox authEnabledCheckbox;
    private JTextField tokenField;
    private JButton copyTokenButton;
    private JButton regenerateButton;
    
    public SettingsDialog(MainWindow mainWindow, JadxAIMCP plugin) {
        super(mainWindow, "JADX AI MCP Plugin Settings", true);
        this.mainWindow = mainWindow;
        this.plugin = plugin;
        
        initComponents();
        loadCurrentSettings();
        pack();
        setLocationRelativeTo(mainWindow);
        setResizable(false);
    }
    
    private void initComponents() {
        JPanel mainPanel = new JPanel();
        mainPanel.setLayout(new BoxLayout(mainPanel, BoxLayout.Y_AXIS));
        mainPanel.setBorder(BorderFactory.createEmptyBorder(15, 15, 15, 15));
        
        // Server configuration panel
        mainPanel.add(createServerConfigPanel());
        mainPanel.add(Box.createVerticalStrut(10));
        
        // Instance information panel
        mainPanel.add(createInstanceInfoPanel());
        mainPanel.add(Box.createVerticalStrut(10));
        
        // Authentication configuration panel
        mainPanel.add(createAuthConfigPanel());
        mainPanel.add(Box.createVerticalStrut(15));
        
        // Bottom buttons
        mainPanel.add(createBottomButtonPanel());
        
        setContentPane(mainPanel);
        
        // Window close event
        addWindowListener(new WindowAdapter() {
            @Override
            public void windowClosing(WindowEvent e) {
                dispose();
            }
        });
    }
    
    /**
     * Create server configuration panel
     */
    private JPanel createServerConfigPanel() {
        JPanel panel = new JPanel(new GridBagLayout());
        
        // Include version and build commit in panel title
        String versionInfo = String.format("Server Configuration  [v%s | %s]",
            com.zin.jadxaimcp.utils.JadxAIMCPBanner.VERSION,
            com.zin.jadxaimcp.utils.JadxAIMCPBanner.BUILD_COMMIT);
        
        panel.setBorder(BorderFactory.createTitledBorder(
            BorderFactory.createEtchedBorder(), 
            versionInfo,
            TitledBorder.LEFT, 
            TitledBorder.TOP
        ));
        
        GridBagConstraints gbc = new GridBagConstraints();
        gbc.insets = new Insets(5, 5, 5, 5);
        gbc.anchor = GridBagConstraints.WEST;
        
        // Status display
        gbc.gridx = 0; gbc.gridy = 0;
        panel.add(new JLabel("Status:"), gbc);
        
        gbc.gridx = 1; gbc.gridy = 0; gbc.gridwidth = 2;
        statusLabel = new JLabel();
        statusLabel.setFont(statusLabel.getFont().deriveFont(Font.BOLD));
        panel.add(statusLabel, gbc);
        
        gbc.gridwidth = 1;
        gbc.gridx = 3; gbc.gridy = 0;
        restartButton = new JButton("Restart");
        restartButton.addActionListener(e -> restartServer());
        panel.add(restartButton, gbc);
        
        gbc.gridx = 4; gbc.gridy = 0;
        stopButton = new JButton("Stop");
        stopButton.addActionListener(e -> stopServer());
        panel.add(stopButton, gbc);
        
        // Bind address
        gbc.gridx = 0; gbc.gridy = 1;
        panel.add(new JLabel("Bind Address:"), gbc);
        
        gbc.gridx = 1; gbc.gridy = 1; gbc.gridwidth = 2;
        String[] addresses = {"127.0.0.1 (Local Only)", "0.0.0.0 (Allow Remote)"};
        bindAddressCombo = new JComboBox<>(addresses);
        bindAddressCombo.setEditable(true);
        panel.add(bindAddressCombo, gbc);
        
        // Port
        gbc.gridwidth = 1;
        gbc.gridx = 3; gbc.gridy = 1;
        panel.add(new JLabel("Port:"), gbc);
        
        gbc.gridx = 4; gbc.gridy = 1;
        portField = new JTextField(6);
        panel.add(portField, gbc);
        
        // Warning label
        gbc.gridx = 0; gbc.gridy = 2; gbc.gridwidth = 5;
        JLabel warningLabel = new JLabel("<html><font color='#CC6600'>[!] Binding to 0.0.0.0 exposes service to network</font></html>");
        warningLabel.setFont(warningLabel.getFont().deriveFont(Font.PLAIN, 11f));
        panel.add(warningLabel, gbc);

        // Auto-rename notice
        gbc.gridx = 0; gbc.gridy = 3; gbc.gridwidth = 5;
        JLabel renameNoticeLabel = new JLabel(
            "<html><font color='#0055AA'>[i] Auto-rename is disabled when the server starts — " +
            "method/field names will match actual APK bytecode names (required for Frida/Xposed hooks). " +
            "Reload your APK if display names appear obfuscated after start.</font></html>"
        );
        renameNoticeLabel.setFont(renameNoticeLabel.getFont().deriveFont(Font.PLAIN, 11f));
        panel.add(renameNoticeLabel, gbc);

        return panel;
    }
    
    /**
     * Create instance information panel
     */
    private JPanel createInstanceInfoPanel() {
        JPanel panel = new JPanel(new GridBagLayout());
        panel.setBorder(BorderFactory.createTitledBorder(
            BorderFactory.createEtchedBorder(),
            "Instance Information",
            TitledBorder.LEFT,
            TitledBorder.TOP
        ));
        
        GridBagConstraints gbc = new GridBagConstraints();
        gbc.insets = new Insets(5, 5, 5, 5);
        gbc.anchor = GridBagConstraints.WEST;
        
        // Instance name
        gbc.gridx = 0; gbc.gridy = 0;
        panel.add(new JLabel("Instance Name:"), gbc);
        
        gbc.gridx = 1; gbc.gridy = 0; gbc.fill = GridBagConstraints.HORIZONTAL; gbc.weightx = 1.0;
        instanceNameField = new JTextField(25);
        instanceNameField.setToolTipText("Custom instance name for multi-instance management. Leave empty to auto-use APK name+version");
        panel.add(instanceNameField, gbc);
        
        // APK info (read-only)
        gbc.gridx = 0; gbc.gridy = 1; gbc.fill = GridBagConstraints.NONE; gbc.weightx = 0;
        panel.add(new JLabel("APK Info:"), gbc);
        
        gbc.gridx = 1; gbc.gridy = 1; gbc.fill = GridBagConstraints.HORIZONTAL; gbc.weightx = 1.0;
        apkInfoLabel = new JLabel("Not loaded");
        apkInfoLabel.setForeground(Color.GRAY);
        panel.add(apkInfoLabel, gbc);
        
        return panel;
    }
    
    /**
     * Create authentication configuration panel
     */
    private JPanel createAuthConfigPanel() {
        JPanel panel = new JPanel(new GridBagLayout());
        panel.setBorder(BorderFactory.createTitledBorder(
            BorderFactory.createEtchedBorder(),
            "Authentication",
            TitledBorder.LEFT,
            TitledBorder.TOP
        ));
        
        GridBagConstraints gbc = new GridBagConstraints();
        gbc.insets = new Insets(5, 5, 5, 5);
        gbc.anchor = GridBagConstraints.WEST;
        
        // Enable authentication
        gbc.gridx = 0; gbc.gridy = 0; gbc.gridwidth = 4;
        authEnabledCheckbox = new JCheckBox("Enable Authentication");
        authEnabledCheckbox.addActionListener(e -> updateAuthUI());
        panel.add(authEnabledCheckbox, gbc);
        
        // Token
        gbc.gridwidth = 1;
        gbc.gridx = 0; gbc.gridy = 1;
        panel.add(new JLabel("Token:"), gbc);
        
        gbc.gridx = 1; gbc.gridy = 1; gbc.fill = GridBagConstraints.HORIZONTAL; gbc.weightx = 1.0;
        tokenField = new JTextField(30);
        tokenField.setFont(new Font("Monospaced", Font.PLAIN, 12));
        tokenField.setToolTipText("You can manually edit the token");
        panel.add(tokenField, gbc);
        
        gbc.fill = GridBagConstraints.NONE; gbc.weightx = 0;
        gbc.gridx = 2; gbc.gridy = 1;
        copyTokenButton = new JButton("Copy");
        copyTokenButton.addActionListener(e -> copyToken());
        panel.add(copyTokenButton, gbc);
        
        gbc.gridx = 3; gbc.gridy = 1;
        regenerateButton = new JButton("Regenerate");
        regenerateButton.addActionListener(e -> regenerateToken());
        panel.add(regenerateButton, gbc);
        
        // Note
        gbc.gridx = 0; gbc.gridy = 2; gbc.gridwidth = 4;
        JLabel noteLabel = new JLabel("<html><font color='gray'>Note: MCP Server requires --auth-token parameter with the same token</font></html>");
        noteLabel.setFont(noteLabel.getFont().deriveFont(Font.PLAIN, 11f));
        panel.add(noteLabel, gbc);
        
        return panel;
    }
    
    /**
     * Create bottom button panel
     */
    private JPanel createBottomButtonPanel() {
        JPanel panel = new JPanel(new FlowLayout(FlowLayout.RIGHT));
        
        JButton saveButton = new JButton("Save & Apply");
        saveButton.addActionListener(e -> saveAndApply());
        
        JButton cancelButton = new JButton("Cancel");
        cancelButton.addActionListener(e -> dispose());
        
        panel.add(saveButton);
        panel.add(cancelButton);
        
        return panel;
    }
    
    /**
     * Load current settings to UI
     */
    private void loadCurrentSettings() {
        // Server status
        updateServerStatus();
        
        // Bind address
        String currentAddr = plugin.getCurrentBindAddress();
        if ("127.0.0.1".equals(currentAddr)) {
            bindAddressCombo.setSelectedIndex(0);
        } else if ("0.0.0.0".equals(currentAddr)) {
            bindAddressCombo.setSelectedIndex(1);
        } else {
            bindAddressCombo.setSelectedItem(currentAddr);
        }
        
        // Port
        portField.setText(String.valueOf(plugin.getCurrentPort()));
        
        // Instance name
        String instanceName = plugin.getInstanceName();
        instanceNameField.setText(instanceName != null ? instanceName : "");
        
        // APK info
        updateApkInfo();
        
        // Authentication configuration
        AuthConfig authConfig = plugin.getAuthConfig();
        if (authConfig != null) {
            authEnabledCheckbox.setSelected(authConfig.isAuthEnabled());
            tokenField.setText(authConfig.getAuthToken());
        }
        
        updateAuthUI();
    }
    
    /**
     * Update server status display
     */
    private void updateServerStatus() {
        boolean running = plugin.isServerRunning();
        if (running) {
            statusLabel.setText("● Running");
            statusLabel.setForeground(new Color(0, 128, 0));
            stopButton.setEnabled(true);
        } else {
            statusLabel.setText("○ Stopped");
            statusLabel.setForeground(Color.GRAY);
            stopButton.setEnabled(false);
        }
    }
    
    /**
     * Update APK info display
     */
    private void updateApkInfo() {
        String apkInfo = plugin.getApkInfo();
        if (apkInfo != null && !apkInfo.isEmpty()) {
            apkInfoLabel.setText(apkInfo);
            apkInfoLabel.setForeground(Color.BLACK);
        } else {
            apkInfoLabel.setText("No APK loaded");
            apkInfoLabel.setForeground(Color.GRAY);
        }
    }
    
    /**
     * Update authentication UI state
     */
    private void updateAuthUI() {
        boolean enabled = authEnabledCheckbox.isSelected();
        tokenField.setEnabled(enabled);
        copyTokenButton.setEnabled(enabled);
        regenerateButton.setEnabled(enabled);
    }
    
    /**
     * Restart server
     */
    private void restartServer() {
        plugin.restartServer();
        // Delayed status update
        SwingUtilities.invokeLater(() -> {
            try {
                Thread.sleep(1500);
            } catch (InterruptedException ignored) {}
            updateServerStatus();
        });
    }
    
    /**
     * Stop server
     */
    private void stopServer() {
        plugin.stopServer();
        updateServerStatus();
    }
    
    /**
     * Copy token to clipboard
     */
    private void copyToken() {
        String token = tokenField.getText();
        if (token != null && !token.isEmpty()) {
            Toolkit.getDefaultToolkit().getSystemClipboard()
                .setContents(new StringSelection(token), null);
            JOptionPane.showMessageDialog(this, "Token copied to clipboard",
                "Success", JOptionPane.INFORMATION_MESSAGE);
        }
    }
    
    /**
     * Regenerate token
     */
    private void regenerateToken() {
        int confirm = JOptionPane.showConfirmDialog(this,
            "Are you sure you want to regenerate the token?\nCurrent token will be invalidated, MCP client config needs update.",
            "Confirm", JOptionPane.YES_NO_OPTION, JOptionPane.WARNING_MESSAGE);
        
        if (confirm == JOptionPane.YES_OPTION) {
            AuthConfig authConfig = plugin.getAuthConfig();
            if (authConfig != null) {
                authConfig.regenerateToken();
                tokenField.setText(authConfig.getAuthToken());
                JOptionPane.showMessageDialog(this,
                    "Token regenerated. Please update MCP client configuration.",
                    "Success", JOptionPane.INFORMATION_MESSAGE);
            }
        }
    }
    
    /**
     * Save and apply settings
     */
    private void saveAndApply() {
        // Validate port
        int newPort;
        try {
            newPort = Integer.parseInt(portField.getText().trim());
            if (newPort < 1024 || newPort > 65535) {
                JOptionPane.showMessageDialog(this,
                    "Port must be between 1024-65535",
                    "Error", JOptionPane.ERROR_MESSAGE);
                return;
            }
        } catch (NumberFormatException e) {
            JOptionPane.showMessageDialog(this,
                "Invalid port format",
                "Error", JOptionPane.ERROR_MESSAGE);
            return;
        }
        
        // Get bind address
        String selectedAddr = (String) bindAddressCombo.getSelectedItem();
        String newBindAddress;
        if (selectedAddr.startsWith("127.0.0.1")) {
            newBindAddress = "127.0.0.1";
        } else if (selectedAddr.startsWith("0.0.0.0")) {
            newBindAddress = "0.0.0.0";
        } else {
            newBindAddress = selectedAddr.trim();
        }
        
        // Save instance name
        String instanceName = instanceNameField.getText().trim();
        plugin.setInstanceName(instanceName.isEmpty() ? null : instanceName);
        
        // Save authentication configuration
        AuthConfig authConfig = plugin.getAuthConfig();
        if (authConfig != null) {
            authConfig.setAuthEnabled(authEnabledCheckbox.isSelected());
            // Manual token modification
            String newToken = tokenField.getText().trim();
            if (!newToken.isEmpty() && !newToken.equals(authConfig.getAuthToken())) {
                authConfig.setAuthToken(newToken);
            }
        }
        
        // Check if server restart is needed
        boolean needRestart = newPort != plugin.getCurrentPort() ||
                             !newBindAddress.equals(plugin.getCurrentBindAddress());
        
        // Apply server configuration
        plugin.updatePort(newPort);
        plugin.updateBindAddress(newBindAddress);
        
        if (needRestart && plugin.isServerRunning()) {
            int restart = JOptionPane.showConfirmDialog(this,
                "Server configuration changed. Restart required for changes to take effect.\nRestart now?",
                "Restart Server", JOptionPane.YES_NO_OPTION);
            if (restart == JOptionPane.YES_OPTION) {
                plugin.restartServer();
            }
        }
        
        dispose();
    }
}
