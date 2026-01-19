package com.jadxtest.library.network;

import java.net.URL;
import java.net.HttpURLConnection;
import java.io.InputStream;
import java.io.BufferedReader;
import java.io.InputStreamReader;

/**
 * HTTP client for testing cross-package references.
 * Tests: get_cross_references, list_packages
 */
public class HttpClient {
    
    public static final String BASE_URL = "https://api.example.com";
    public static final String API_KEY_HEADER = "X-API-Key";
    private static final String USER_AGENT = "JadxTest/1.0";
    
    private String apiKey;
    private int timeout = 30000;
    
    public HttpClient(String apiKey) {
        this.apiKey = apiKey;
    }
    
    /**
     * Make GET request
     */
    public String get(String endpoint) throws Exception {
        URL url = new URL(BASE_URL + endpoint);
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        
        conn.setRequestMethod("GET");
        conn.setRequestProperty("User-Agent", USER_AGENT);
        conn.setRequestProperty(API_KEY_HEADER, apiKey);
        conn.setConnectTimeout(timeout);
        
        try (InputStream is = conn.getInputStream();
             BufferedReader reader = new BufferedReader(new InputStreamReader(is))) {
            StringBuilder response = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null) {
                response.append(line);
            }
            return response.toString();
        }
    }
    
    /**
     * Set connection timeout
     */
    public void setTimeout(int timeout) {
        this.timeout = timeout;
    }
    
    /**
     * Build URL with query parameters
     */
    public static String buildUrl(String base, String... params) {
        if (params.length == 0) return base;
        if (params.length % 2 != 0) {
            throw new IllegalArgumentException("Parameters must be key-value pairs");
        }
        
        StringBuilder url = new StringBuilder(base).append("?");
        for (int i = 0; i < params.length; i += 2) {
            if (i > 0) url.append("&");
            url.append(params[i]).append("=").append(params[i + 1]);
        }
        return url.toString();
    }
}
