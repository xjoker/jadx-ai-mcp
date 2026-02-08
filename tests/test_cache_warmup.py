#!/usr/bin/env python3
"""任务#11: 验证缓存预热机制"""
import sys
import json
import logging
import requests
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8650"


def test_strings_immediate_success():
    """验证首次调用 get_strings 是否立即成功"""
    logger.info("测试 #11.1: 首次调用 get_strings")

    try:
        response = requests.get(f"{BASE_URL}/strings", params={"mode": "summary"}, timeout=10)
        response.raise_for_status()
        result = response.json()
        logger.info(f"✓ get_strings 立即成功返回")
        logger.info(f"  总字符串数: {result.get('total_strings', 'N/A')}")
        return True
    except Exception as e:
        logger.error(f"✗ get_strings 失败: {e}")
        return False


def test_xrefs_graceful_503():
    """验证首次调用 get_xrefs 是否返回友好 503"""
    logger.info("测试 #11.2: 首次调用 get_xrefs 响应")

    try:
        response = requests.get(
            f"{BASE_URL}/xrefs-to-class",
            params={
                "class_name": "android.support.v4.app.INotificationSideChannel"
            },
            timeout=10
        )

        # 如果成功，说明缓存已预热
        if response.status_code == 200:
            result = response.json()
            logger.info(f"✓ get_xrefs 成功返回 (缓存已预热)")
            logger.info(f"  找到 {len(result.get('xrefs', []))} 个引用")
            return True
        elif response.status_code == 503:
            logger.info(f"✓ get_xrefs 返回友好 503: {response.text}")
            return True
        else:
            logger.error(f"✗ get_xrefs 返回非预期状态码: {response.status_code}")
            return False

    except Exception as e:
        error_msg = str(e)
        if "503" in error_msg or "cache" in error_msg.lower():
            logger.info(f"✓ get_xrefs 返回友好错误: {error_msg}")
            return True
        else:
            logger.error(f"✗ get_xrefs 返回非预期错误: {e}")
            return False


def test_decompile_status():
    """检查反编译状态和缓存百分比"""
    logger.info("测试 #11.3: 检查反编译和缓存状态")

    try:
        response = requests.get(f"{BASE_URL}/decompile-status", timeout=10)
        response.raise_for_status()
        status = response.json()
        logger.info(f"✓ 反编译状态获取成功")
        logger.info(f"  总类数: {status.get('total_classes')}")
        logger.info(f"  已缓存: {status.get('cached_classes')}")
        logger.info(f"  缓存百分比: {status.get('cached_percentage')}%")
        logger.info(f"  内存使用: {status.get('memory', {}).get('usage_percentage')}%")

        # 验证状态端点可用且返回有效数据
        total_classes = status.get('total_classes', 0)
        cached_pct = status.get('cached_percentage', 0)
        if total_classes > 0:
            logger.info(f"✓ 反编译状态正常 (总类数: {total_classes}, 缓存: {cached_pct}%)")
            return True
        else:
            logger.warning(f"⚠ 未检测到类信息")
            return False

    except Exception as e:
        logger.error(f"✗ 获取状态失败: {e}")
        return False


def test_health_endpoint():
    """检查健康端点响应"""
    logger.info("测试 #11.4: 检查健康端点")

    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        response.raise_for_status()
        health = response.json()

        logger.info(f"✓ 健康检查成功")
        logger.info(f"  状态: {health.get('status')}")
        logger.info(f"  类总数: {health.get('jadx', {}).get('classes_total')}")
        logger.info(f"  内存: {health.get('memory', {}).get('used_mb')}MB / {health.get('memory', {}).get('max_mb')}MB")
        return True

    except Exception as e:
        logger.error(f"✗ 健康检查失败: {e}")
        return False


def main():
    """执行所有缓存预热验证测试"""
    logger.info("=" * 60)
    logger.info("任务 #11: 验证缓存预热机制")
    logger.info("=" * 60)

    results = {
        "strings_immediate": test_strings_immediate_success(),
        "xrefs_graceful": test_xrefs_graceful_503(),
        "decompile_status": test_decompile_status(),
        "health_check": test_health_endpoint(),
    }

    logger.info("\n" + "=" * 60)
    logger.info("测试结果汇总:")
    logger.info("=" * 60)

    passed = sum(results.values())
    total = len(results)

    for test_name, result in results.items():
        status = "✓ 通过" if result else "✗ 失败"
        logger.info(f"{status} - {test_name}")

    logger.info(f"\n总计: {passed}/{total} 测试通过")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
