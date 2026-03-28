package com.zin.jadxaimcp.utils;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

/**
 * 单元测试 - JadxApiAdapter 的空值防护逻辑。
 *
 * 所有 adapter 方法在接收 null 入参时应安全返回 null 或空集合，
 * 而不是抛出 NullPointerException。
 */
class JadxApiAdapterTest {

    // -------------------------------------------------------------------------
    // JavaClass 相关方法 — null 输入
    // -------------------------------------------------------------------------

    @Test
    void getClassAliasName_nullClass_returnsNull() {
        assertNull(JadxApiAdapter.getClassAliasName(null));
    }

    @Test
    void getClassRawName_nullClass_returnsNull() {
        assertNull(JadxApiAdapter.getClassRawName(null));
    }

    @Test
    void getClassAliasSimpleName_nullClass_returnsNull() {
        assertNull(JadxApiAdapter.getClassAliasSimpleName(null));
    }

    @Test
    void getClassRawSimpleName_nullClass_returnsNull() {
        assertNull(JadxApiAdapter.getClassRawSimpleName(null));
    }

    @Test
    void matchesClassName_nullClass_returnsFalse() {
        assertFalse(JadxApiAdapter.matchesClassName(null, "com.example.Foo"));
    }

    @Test
    void matchesClassName_nullRequestedName_returnsFalse() {
        // null 类 + null 请求名均应返回 false，不抛异常
        assertFalse(JadxApiAdapter.matchesClassName(null, null));
    }

    @Test
    void getAccessFlags_nullClass_returnsNull() {
        assertNull(JadxApiAdapter.getAccessFlags(null));
    }

    @Test
    void getSuperClass_nullClass_returnsNull() {
        assertNull(JadxApiAdapter.getSuperClass(null));
    }

    @Test
    void getInterfaces_nullClass_returnsEmptyList() {
        List<String> result = JadxApiAdapter.getInterfaces(null);
        assertNotNull(result);
        assertTrue(result.isEmpty());
    }

    @Test
    void isProcessComplete_nullClass_returnsFalse() {
        assertFalse(JadxApiAdapter.isProcessComplete(null));
    }

    @Test
    void getDeclaredMethodInfos_nullClass_returnsEmptyList() {
        List<JadxApiAdapter.MethodInfoSnapshot> result = JadxApiAdapter.getDeclaredMethodInfos(null);
        assertNotNull(result);
        assertTrue(result.isEmpty());
    }

    @Test
    void getDeclaredFieldInfos_nullClass_returnsEmptyList() {
        List<JadxApiAdapter.FieldInfoSnapshot> result = JadxApiAdapter.getDeclaredFieldInfos(null);
        assertNotNull(result);
        assertTrue(result.isEmpty());
    }

    @Test
    void getClassUseInMethods_nullClass_returnsEmptyList() {
        List<?> result = JadxApiAdapter.getClassUseInMethods(null);
        assertNotNull(result);
        assertTrue(result.isEmpty());
    }

    // -------------------------------------------------------------------------
    // JavaMethod 相关方法 — null 输入
    // -------------------------------------------------------------------------

    @Test
    void getMethodAliasName_nullMethod_returnsNull() {
        assertNull(JadxApiAdapter.getMethodAliasName(null));
    }

    @Test
    void getMethodRawName_nullMethod_returnsNull() {
        assertNull(JadxApiAdapter.getMethodRawName(null));
    }

    @Test
    void getMethodFullId_nullMethod_returnsNull() {
        assertNull(JadxApiAdapter.getMethodFullId(null));
    }

    @Test
    void getMethodRawFullId_nullMethod_returnsNull() {
        assertNull(JadxApiAdapter.getMethodRawFullId(null));
    }

    @Test
    void matchesMethodName_nullMethod_returnsFalse() {
        assertFalse(JadxApiAdapter.matchesMethodName(null, "foo"));
    }

    @Test
    void getMethodInfo_nullMethod_returnsNull() {
        assertNull(JadxApiAdapter.getMethodInfo((jadx.api.JavaMethod) null));
    }

    @Test
    void getInternalMethodNode_nullMethod_returnsNull() {
        assertNull(JadxApiAdapter.getInternalMethodNode(null));
    }

    // -------------------------------------------------------------------------
    // JavaField 相关方法 — null 输入
    // -------------------------------------------------------------------------

    @Test
    void getFieldType_nullField_returnsNull() {
        assertNull(JadxApiAdapter.getFieldType(null));
    }

    @Test
    void getFieldAliasName_nullField_returnsNull() {
        assertNull(JadxApiAdapter.getFieldAliasName(null));
    }

    @Test
    void getFieldRawName_nullField_returnsNull() {
        assertNull(JadxApiAdapter.getFieldRawName(null));
    }

    @Test
    void getFieldRawFullId_nullField_returnsNull() {
        assertNull(JadxApiAdapter.getFieldRawFullId(null));
    }

    @Test
    void matchesFieldName_nullField_returnsFalse() {
        assertFalse(JadxApiAdapter.matchesFieldName(null, "field"));
    }
}
