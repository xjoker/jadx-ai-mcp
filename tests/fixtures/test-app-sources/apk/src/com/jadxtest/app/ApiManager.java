package com.jadxtest.app;

import android.content.Context;
import android.net.ConnectivityManager;
import android.net.NetworkInfo;
import android.os.AsyncTask;

/**
 * API Manager for testing network-related code analysis.
 * Tests: get_cross_references, search_by_code
 */
public class ApiManager {
    
    public static final String BASE_URL = "https://api.jadxtest.com/v1";
    private static final String API_KEY = "jadx_test_api_key_secret_123";
    private static final String AUTH_HEADER = "Authorization";
    
    private Context context;
    private boolean connected = false;
    
    public interface Callback {
        void onSuccess(String data);
        void onError(String error);
    }
    
    public ApiManager(Context context) {
        this.context = context;
        checkConnection();
    }
    
    private void checkConnection() {
        ConnectivityManager cm = (ConnectivityManager) 
            context.getSystemService(Context.CONNECTIVITY_SERVICE);
        NetworkInfo info = cm.getActiveNetworkInfo();
        connected = info != null && info.isConnected();
    }
    
    public boolean isConnected() {
        return connected;
    }
    
    public void fetchData(final Callback callback) {
        if (!connected) {
            callback.onError("No network connection");
            return;
        }
        
        new AsyncTask<Void, Void, String>() {
            @Override
            protected String doInBackground(Void... params) {
                try {
                    // Simulate API call
                    Thread.sleep(1000);
                    return "{\"status\": \"ok\", \"data\": \"sample\"}";
                } catch (Exception e) {
                    return null;
                }
            }
            
            @Override
            protected void onPostExecute(String result) {
                if (result != null) {
                    callback.onSuccess(result);
                } else {
                    callback.onError("Request failed");
                }
            }
        }.execute();
    }
    
    public void login(String username, String password, Callback callback) {
        // Insecure: plaintext password handling (for testing security scanning)
        String credentials = username + ":" + password;
        String token = encodeBase64(credentials);
        
        // Make login request
        callback.onSuccess("token_" + token);
    }
    
    private String encodeBase64(String input) {
        // Simple mock implementation
        return input.replace(":", "_");
    }
}
