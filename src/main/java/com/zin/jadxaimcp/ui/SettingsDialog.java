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
 * 统一设置对话框
 * 
 * 整合所有插件配置到单个界面：
 * - 服务器配置（地址、端口、状态）
 * - 实例信息（名称、APK信息）
 * - 认证配置（Token、启用开关）
 *
 * @author JADX AI MCP Team
 */
public class SettingsDialog extends JDialog {
    private static final Logger logger = LoggerFactory.getLogger(SettingsDialog.class);
    
    private final MainWindow mainWindow;
    private final JadxAIMCP plugin;
    
    // 服务器配置组件
    private JLabel statusLabel;
    private JComboBox<String> bindAddressCombo;
    private JTextField portField;
    private JButton restartButton;
    private JButton stopButton;
    
    // 实例信息组件
    private JTextField instanceNameField;
    private JLabel apkInfoLabel;
    
    // 认证配置组件
    private JCheckBox authEnabledCheckbox;
    private JTextField tokenField;
    private JButton copyTokenButton;
    private JButton regenerateButton;
    
    public SettingsDialog(MainWindow mainWindow, JadxAIMCP plugin) {
        super(mainWindow, "JADX AI MCP Plugin 设置", true);
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
        
        // 服务器配置面板
        mainPanel.add(createServerConfigPanel());
        mainPanel.add(Box.createVerticalStrut(10));
        
        // 实例信息面板
        mainPanel.add(createInstanceInfoPanel());
        mainPanel.add(Box.createVerticalStrut(10));
        
        // 认证配置面板
        mainPanel.add(createAuthConfigPanel());
        mainPanel.add(Box.createVerticalStrut(15));
        
        // 底部按钮
        mainPanel.add(createBottomButtonPanel());
        
        setContentPane(mainPanel);
        
        // 窗口关闭事件
        addWindowListener(new WindowAdapter() {
            @Override
            public void windowClosing(WindowEvent e) {
                dispose();
            }
        });
    }
    
    /**
     * 创建服务器配置面板
     */
    private JPanel createServerConfigPanel() {
        JPanel panel = new JPanel(new GridBagLayout());
        panel.setBorder(BorderFactory.createTitledBorder(
            BorderFactory.createEtchedBorder(), 
            "服务器配置",
            TitledBorder.LEFT, 
            TitledBorder.TOP
        ));
        
        GridBagConstraints gbc = new GridBagConstraints();
        gbc.insets = new Insets(5, 5, 5, 5);
        gbc.anchor = GridBagConstraints.WEST;
        
        // 状态显示
        gbc.gridx = 0; gbc.gridy = 0;
        panel.add(new JLabel("状态:"), gbc);
        
        gbc.gridx = 1; gbc.gridy = 0; gbc.gridwidth = 2;
        statusLabel = new JLabel();
        statusLabel.setFont(statusLabel.getFont().deriveFont(Font.BOLD));
        panel.add(statusLabel, gbc);
        
        gbc.gridwidth = 1;
        gbc.gridx = 3; gbc.gridy = 0;
        restartButton = new JButton("重启");
        restartButton.addActionListener(e -> restartServer());
        panel.add(restartButton, gbc);
        
        gbc.gridx = 4; gbc.gridy = 0;
        stopButton = new JButton("停止");
        stopButton.addActionListener(e -> stopServer());
        panel.add(stopButton, gbc);
        
        // 绑定地址
        gbc.gridx = 0; gbc.gridy = 1;
        panel.add(new JLabel("绑定地址:"), gbc);
        
        gbc.gridx = 1; gbc.gridy = 1; gbc.gridwidth = 2;
        String[] addresses = {"127.0.0.1 (仅本地)", "0.0.0.0 (允许远程)"};
        bindAddressCombo = new JComboBox<>(addresses);
        bindAddressCombo.setEditable(true);
        panel.add(bindAddressCombo, gbc);
        
        // 端口
        gbc.gridwidth = 1;
        gbc.gridx = 3; gbc.gridy = 1;
        panel.add(new JLabel("端口:"), gbc);
        
        gbc.gridx = 4; gbc.gridy = 1;
        portField = new JTextField(6);
        panel.add(portField, gbc);
        
        // 警告标签
        gbc.gridx = 0; gbc.gridy = 2; gbc.gridwidth = 5;
        JLabel warningLabel = new JLabel("<html><font color='#CC6600'>⚠ 绑定到 0.0.0.0 会将服务暴露到网络</font></html>");
        warningLabel.setFont(warningLabel.getFont().deriveFont(Font.PLAIN, 11f));
        panel.add(warningLabel, gbc);
        
        return panel;
    }
    
    /**
     * 创建实例信息面板
     */
    private JPanel createInstanceInfoPanel() {
        JPanel panel = new JPanel(new GridBagLayout());
        panel.setBorder(BorderFactory.createTitledBorder(
            BorderFactory.createEtchedBorder(),
            "实例信息",
            TitledBorder.LEFT,
            TitledBorder.TOP
        ));
        
        GridBagConstraints gbc = new GridBagConstraints();
        gbc.insets = new Insets(5, 5, 5, 5);
        gbc.anchor = GridBagConstraints.WEST;
        
        // 实例名称
        gbc.gridx = 0; gbc.gridy = 0;
        panel.add(new JLabel("实例名称:"), gbc);
        
        gbc.gridx = 1; gbc.gridy = 0; gbc.fill = GridBagConstraints.HORIZONTAL; gbc.weightx = 1.0;
        instanceNameField = new JTextField(25);
        instanceNameField.setToolTipText("自定义实例名称，用于多实例管理时区分。留空则自动使用 APK 名称+版本");
        panel.add(instanceNameField, gbc);
        
        // APK 信息（只读）
        gbc.gridx = 0; gbc.gridy = 1; gbc.fill = GridBagConstraints.NONE; gbc.weightx = 0;
        panel.add(new JLabel("APK 信息:"), gbc);
        
        gbc.gridx = 1; gbc.gridy = 1; gbc.fill = GridBagConstraints.HORIZONTAL; gbc.weightx = 1.0;
        apkInfoLabel = new JLabel("未加载");
        apkInfoLabel.setForeground(Color.GRAY);
        panel.add(apkInfoLabel, gbc);
        
        return panel;
    }
    
    /**
     * 创建认证配置面板
     */
    private JPanel createAuthConfigPanel() {
        JPanel panel = new JPanel(new GridBagLayout());
        panel.setBorder(BorderFactory.createTitledBorder(
            BorderFactory.createEtchedBorder(),
            "认证配置",
            TitledBorder.LEFT,
            TitledBorder.TOP
        ));
        
        GridBagConstraints gbc = new GridBagConstraints();
        gbc.insets = new Insets(5, 5, 5, 5);
        gbc.anchor = GridBagConstraints.WEST;
        
        // 启用认证
        gbc.gridx = 0; gbc.gridy = 0; gbc.gridwidth = 4;
        authEnabledCheckbox = new JCheckBox("启用认证");
        authEnabledCheckbox.addActionListener(e -> updateAuthUI());
        panel.add(authEnabledCheckbox, gbc);
        
        // Token
        gbc.gridwidth = 1;
        gbc.gridx = 0; gbc.gridy = 1;
        panel.add(new JLabel("Token:"), gbc);
        
        gbc.gridx = 1; gbc.gridy = 1; gbc.fill = GridBagConstraints.HORIZONTAL; gbc.weightx = 1.0;
        tokenField = new JTextField(30);
        tokenField.setFont(new Font("Monospaced", Font.PLAIN, 12));
        tokenField.setToolTipText("可手工编辑 Token");
        panel.add(tokenField, gbc);
        
        gbc.fill = GridBagConstraints.NONE; gbc.weightx = 0;
        gbc.gridx = 2; gbc.gridy = 1;
        copyTokenButton = new JButton("复制");
        copyTokenButton.addActionListener(e -> copyToken());
        panel.add(copyTokenButton, gbc);
        
        gbc.gridx = 3; gbc.gridy = 1;
        regenerateButton = new JButton("重新生成");
        regenerateButton.addActionListener(e -> regenerateToken());
        panel.add(regenerateButton, gbc);
        
        // 提示信息
        gbc.gridx = 0; gbc.gridy = 2; gbc.gridwidth = 4;
        JLabel noteLabel = new JLabel("<html><font color='gray'>提示: MCP Server 需使用 --auth-token 参数配置相同的 Token</font></html>");
        noteLabel.setFont(noteLabel.getFont().deriveFont(Font.PLAIN, 11f));
        panel.add(noteLabel, gbc);
        
        return panel;
    }
    
    /**
     * 创建底部按钮面板
     */
    private JPanel createBottomButtonPanel() {
        JPanel panel = new JPanel(new FlowLayout(FlowLayout.RIGHT));
        
        JButton saveButton = new JButton("保存并应用");
        saveButton.addActionListener(e -> saveAndApply());
        
        JButton cancelButton = new JButton("取消");
        cancelButton.addActionListener(e -> dispose());
        
        panel.add(saveButton);
        panel.add(cancelButton);
        
        return panel;
    }
    
    /**
     * 加载当前设置到 UI
     */
    private void loadCurrentSettings() {
        // 服务器状态
        updateServerStatus();
        
        // 绑定地址
        String currentAddr = plugin.getCurrentBindAddress();
        if ("127.0.0.1".equals(currentAddr)) {
            bindAddressCombo.setSelectedIndex(0);
        } else if ("0.0.0.0".equals(currentAddr)) {
            bindAddressCombo.setSelectedIndex(1);
        } else {
            bindAddressCombo.setSelectedItem(currentAddr);
        }
        
        // 端口
        portField.setText(String.valueOf(plugin.getCurrentPort()));
        
        // 实例名称
        String instanceName = plugin.getInstanceName();
        instanceNameField.setText(instanceName != null ? instanceName : "");
        
        // APK 信息
        updateApkInfo();
        
        // 认证配置
        AuthConfig authConfig = plugin.getAuthConfig();
        if (authConfig != null) {
            authEnabledCheckbox.setSelected(authConfig.isAuthEnabled());
            tokenField.setText(authConfig.getAuthToken());
        }
        
        updateAuthUI();
    }
    
    /**
     * 更新服务器状态显示
     */
    private void updateServerStatus() {
        boolean running = plugin.isServerRunning();
        if (running) {
            statusLabel.setText("● 运行中");
            statusLabel.setForeground(new Color(0, 128, 0));
            stopButton.setEnabled(true);
        } else {
            statusLabel.setText("○ 已停止");
            statusLabel.setForeground(Color.GRAY);
            stopButton.setEnabled(false);
        }
    }
    
    /**
     * 更新 APK 信息显示
     */
    private void updateApkInfo() {
        String apkInfo = plugin.getApkInfo();
        if (apkInfo != null && !apkInfo.isEmpty()) {
            apkInfoLabel.setText(apkInfo);
            apkInfoLabel.setForeground(Color.BLACK);
        } else {
            apkInfoLabel.setText("未加载 APK");
            apkInfoLabel.setForeground(Color.GRAY);
        }
    }
    
    /**
     * 更新认证 UI 状态
     */
    private void updateAuthUI() {
        boolean enabled = authEnabledCheckbox.isSelected();
        tokenField.setEnabled(enabled);
        copyTokenButton.setEnabled(enabled);
        regenerateButton.setEnabled(enabled);
    }
    
    /**
     * 重启服务器
     */
    private void restartServer() {
        plugin.restartServer();
        // 延迟更新状态
        SwingUtilities.invokeLater(() -> {
            try {
                Thread.sleep(1500);
            } catch (InterruptedException ignored) {}
            updateServerStatus();
        });
    }
    
    /**
     * 停止服务器
     */
    private void stopServer() {
        plugin.stopServer();
        updateServerStatus();
    }
    
    /**
     * 复制 Token 到剪贴板
     */
    private void copyToken() {
        String token = tokenField.getText();
        if (token != null && !token.isEmpty()) {
            Toolkit.getDefaultToolkit().getSystemClipboard()
                .setContents(new StringSelection(token), null);
            JOptionPane.showMessageDialog(this, "Token 已复制到剪贴板",
                "成功", JOptionPane.INFORMATION_MESSAGE);
        }
    }
    
    /**
     * 重新生成 Token
     */
    private void regenerateToken() {
        int confirm = JOptionPane.showConfirmDialog(this,
            "确定要重新生成 Token 吗？\n当前 Token 将失效，需要更新 MCP 客户端配置。",
            "确认", JOptionPane.YES_NO_OPTION, JOptionPane.WARNING_MESSAGE);
        
        if (confirm == JOptionPane.YES_OPTION) {
            AuthConfig authConfig = plugin.getAuthConfig();
            if (authConfig != null) {
                authConfig.regenerateToken();
                tokenField.setText(authConfig.getAuthToken());
                JOptionPane.showMessageDialog(this,
                    "Token 已重新生成，请更新 MCP 客户端配置。",
                    "成功", JOptionPane.INFORMATION_MESSAGE);
            }
        }
    }
    
    /**
     * 保存并应用设置
     */
    private void saveAndApply() {
        // 验证端口
        int newPort;
        try {
            newPort = Integer.parseInt(portField.getText().trim());
            if (newPort < 1024 || newPort > 65535) {
                JOptionPane.showMessageDialog(this,
                    "端口必须在 1024-65535 范围内",
                    "错误", JOptionPane.ERROR_MESSAGE);
                return;
            }
        } catch (NumberFormatException e) {
            JOptionPane.showMessageDialog(this,
                "端口格式无效",
                "错误", JOptionPane.ERROR_MESSAGE);
            return;
        }
        
        // 获取绑定地址
        String selectedAddr = (String) bindAddressCombo.getSelectedItem();
        String newBindAddress;
        if (selectedAddr.startsWith("127.0.0.1")) {
            newBindAddress = "127.0.0.1";
        } else if (selectedAddr.startsWith("0.0.0.0")) {
            newBindAddress = "0.0.0.0";
        } else {
            newBindAddress = selectedAddr.trim();
        }
        
        // 保存实例名称
        String instanceName = instanceNameField.getText().trim();
        plugin.setInstanceName(instanceName.isEmpty() ? null : instanceName);
        
        // 保存认证配置
        AuthConfig authConfig = plugin.getAuthConfig();
        if (authConfig != null) {
            authConfig.setAuthEnabled(authEnabledCheckbox.isSelected());
            // 手工修改 Token
            String newToken = tokenField.getText().trim();
            if (!newToken.isEmpty() && !newToken.equals(authConfig.getAuthToken())) {
                authConfig.setAuthToken(newToken);
            }
        }
        
        // 判断是否需要重启服务器
        boolean needRestart = newPort != plugin.getCurrentPort() ||
                             !newBindAddress.equals(plugin.getCurrentBindAddress());
        
        // 应用服务器配置
        plugin.updatePort(newPort);
        plugin.updateBindAddress(newBindAddress);
        
        if (needRestart && plugin.isServerRunning()) {
            int restart = JOptionPane.showConfirmDialog(this,
                "服务器配置已更改，需要重启服务器才能生效。\n是否立即重启？",
                "重启服务器", JOptionPane.YES_NO_OPTION);
            if (restart == JOptionPane.YES_OPTION) {
                plugin.restartServer();
            }
        }
        
        dispose();
    }
}
