package com.jadxtest.library.model;

/**
 * User model for testing POJO/DTO detection.
 * Tests: get_fields, get_methods
 */
public class User {
    
    private int id;
    private String username;
    private String email;
    private boolean active;
    private long createdAt;
    
    public User() {}
    
    public User(int id, String username, String email) {
        this.id = id;
        this.username = username;
        this.email = email;
        this.active = true;
        this.createdAt = System.currentTimeMillis();
    }
    
    // Getters
    public int getId() { return id; }
    public String getUsername() { return username; }
    public String getEmail() { return email; }
    public boolean isActive() { return active; }
    public long getCreatedAt() { return createdAt; }
    
    // Setters
    public void setId(int id) { this.id = id; }
    public void setUsername(String username) { this.username = username; }
    public void setEmail(String email) { this.email = email; }
    public void setActive(boolean active) { this.active = active; }
    
    @Override
    public String toString() {
        return "User{id=" + id + ", username='" + username + "', email='" + email + "'}";
    }
}
