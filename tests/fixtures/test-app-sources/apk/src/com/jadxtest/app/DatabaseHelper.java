package com.jadxtest.app;

import android.content.Context;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;

/**
 * Database helper for testing SQLite operations.
 * Tests: search_by_code (SQL queries)
 */
public class DatabaseHelper extends SQLiteOpenHelper {
    
    private static final String DATABASE_NAME = "jadxtest.db";
    private static final int DATABASE_VERSION = 1;
    
    // Table names
    public static final String TABLE_USERS = "users";
    public static final String TABLE_SESSIONS = "sessions";
    
    // Column names
    public static final String COL_ID = "_id";
    public static final String COL_USERNAME = "username";
    public static final String COL_EMAIL = "email";
    public static final String COL_PASSWORD_HASH = "password_hash";
    public static final String COL_TOKEN = "token";
    public static final String COL_CREATED_AT = "created_at";
    
    private static final String CREATE_USERS_TABLE = 
        "CREATE TABLE " + TABLE_USERS + " (" +
        COL_ID + " INTEGER PRIMARY KEY AUTOINCREMENT, " +
        COL_USERNAME + " TEXT NOT NULL, " +
        COL_EMAIL + " TEXT UNIQUE, " +
        COL_PASSWORD_HASH + " TEXT NOT NULL, " +
        COL_CREATED_AT + " INTEGER DEFAULT (strftime('%s', 'now')))";
    
    private static final String CREATE_SESSIONS_TABLE =
        "CREATE TABLE " + TABLE_SESSIONS + " (" +
        COL_ID + " INTEGER PRIMARY KEY AUTOINCREMENT, " +
        COL_TOKEN + " TEXT NOT NULL, " +
        COL_CREATED_AT + " INTEGER DEFAULT (strftime('%s', 'now')))";
    
    public DatabaseHelper(Context context) {
        super(context, DATABASE_NAME, null, DATABASE_VERSION);
    }
    
    @Override
    public void onCreate(SQLiteDatabase db) {
        db.execSQL(CREATE_USERS_TABLE);
        db.execSQL(CREATE_SESSIONS_TABLE);
    }
    
    @Override
    public void onUpgrade(SQLiteDatabase db, int oldVersion, int newVersion) {
        db.execSQL("DROP TABLE IF EXISTS " + TABLE_USERS);
        db.execSQL("DROP TABLE IF EXISTS " + TABLE_SESSIONS);
        onCreate(db);
    }
    
    public void insertUser(String username, String email, String passwordHash) {
        SQLiteDatabase db = getWritableDatabase();
        db.execSQL("INSERT INTO " + TABLE_USERS + " (" + 
            COL_USERNAME + ", " + COL_EMAIL + ", " + COL_PASSWORD_HASH + 
            ") VALUES (?, ?, ?)", 
            new Object[]{username, email, passwordHash});
    }
}
