package com.jadxtest.app;

import android.app.Activity;
import android.os.Bundle;
import android.view.View;
import android.widget.Button;
import android.widget.TextView;

/**
 * Main activity for testing Android-specific features.
 * Tests: get_class_source, get_manifest, activity detection
 */
public class MainActivity extends Activity {
    
    private static final String TAG = "MainActivity";
    private static final int REQUEST_CODE_SETTINGS = 100;
    
    private TextView statusText;
    private Button actionButton;
    private ApiManager apiManager;
    
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        
        // Initialize components
        statusText = new TextView(this);
        actionButton = new Button(this);
        apiManager = new ApiManager(this);
        
        // Setup UI
        statusText.setText("Ready");
        actionButton.setText("Start");
        actionButton.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                onActionClicked();
            }
        });
    }
    
    private void onActionClicked() {
        statusText.setText("Processing...");
        apiManager.fetchData(new ApiManager.Callback() {
            @Override
            public void onSuccess(String data) {
                statusText.setText("Success: " + data);
            }
            
            @Override
            public void onError(String error) {
                statusText.setText("Error: " + error);
            }
        });
    }
    
    @Override
    protected void onResume() {
        super.onResume();
        updateStatus();
    }
    
    private void updateStatus() {
        if (apiManager.isConnected()) {
            statusText.setText("Connected");
        } else {
            statusText.setText("Disconnected");
        }
    }
}
