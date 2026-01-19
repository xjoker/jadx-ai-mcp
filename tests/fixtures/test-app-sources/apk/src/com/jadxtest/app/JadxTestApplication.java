package com.jadxtest.app;

import android.app.Application;
import android.content.SharedPreferences;

/**
 * Application class for testing app initialization.
 * Tests: get_class_source, Application detection
 */
public class JadxTestApplication extends Application {
    
    private static final String PREFS_NAME = "jadx_test_prefs";
    private static final String KEY_FIRST_RUN = "first_run";
    private static final String KEY_USER_ID = "user_id";
    
    private static JadxTestApplication instance;
    private SharedPreferences preferences;
    private DatabaseHelper dbHelper;
    
    @Override
    public void onCreate() {
        super.onCreate();
        instance = this;
        
        // Initialize preferences
        preferences = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        
        // Initialize database
        dbHelper = new DatabaseHelper(this);
        
        // Check first run
        if (isFirstRun()) {
            onFirstRun();
        }
    }
    
    public static JadxTestApplication getInstance() {
        return instance;
    }
    
    public SharedPreferences getPreferences() {
        return preferences;
    }
    
    public DatabaseHelper getDatabase() {
        return dbHelper;
    }
    
    private boolean isFirstRun() {
        return preferences.getBoolean(KEY_FIRST_RUN, true);
    }
    
    private void onFirstRun() {
        preferences.edit()
            .putBoolean(KEY_FIRST_RUN, false)
            .putString(KEY_USER_ID, generateUserId())
            .apply();
    }
    
    private String generateUserId() {
        return "user_" + System.currentTimeMillis();
    }
}
