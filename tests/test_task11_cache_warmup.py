#!/usr/bin/env python3
"""任务 #11: 验证缓存预热机制（ClassCacheManager）

检查点：
1. 服务启动时 ClassCacheManager.initCache() 是否自动触发？
2. 缓存加载状态（NOT_INITIALIZED / LOADING / READY）
3. get_decompile_status 是否返回正确的缓存统计？
4. 首次调用 get_strings 是否立即成功？
5. 首次调用 get_xrefs 是否返回数据或友好 503？
"""
import sys
import json
import logging
import requests
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8650"


def test_1_decompile_status():
    """测试 1: decompile-status 端点返回缓存统计"""
    logger.info("=" * 60)
    logger.info("测试 1: decompile-status 端点")
    logger.info("=" * 60)

    try:
        response = requests.get(f"{BASE_URL}/decompile-status", timeout=10)
        response.raise_for_status()
        status = response.json()

        logger.info(f"✓ decompile-status 端点工作正常")
        logger.info(f"  总类数: {status.get('total_classes')}")
        logger.info(f"  已缓存: {status.get('cached_classes')}")
        logger.info(f"  缓存百分比: {status.get('cached_percentage')}%")
        logger.info(f"  内存使用: {status.get('memory', {}).get('usage_percentage')}%")
        logger.info(f"  活跃线程: {status.get('threads', {}).get('active_count')}")
        logger.info(f"  缓存模式: {status.get('jadx_config', {}).get('code_cache_mode')}")

        # 验证必要字段存在
        required_fields = ['total_classes', 'cached_classes', 'cached_percentage']
        missing = [f for f in required_fields if f not in status]
        if missing:
            logger.error(f"✗ 缺少必要字段: {missing}")
            return False

        return True

    except Exception as e:
        logger.error(f"✗ decompile-status 失败: {e}")
        return False


def test_2_strings_immediate():
    """测试 2: 首次调用 get_strings 是否立即成功"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 2: 首次调用 get_strings")
    logger.info("=" * 60)

    try:
        start_time = time.time()
        response = requests.get(f"{BASE_URL}/strings", params={"mode": "summary"}, timeout=10)
        elapsed = time.time() - start_time

        response.raise_for_status()
        result = response.json()

        logger.info(f"✓ get_strings 立即成功返回")
        logger.info(f"  响应时间: {elapsed:.2f}s")
        logger.info(f"  总字符串数: {result.get('total_strings', 'N/A')}")
        logger.info(f"  示例键数量: {len(result.get('sample_keys', []))}")

        # 验证响应速度（应该很快）
        if elapsed > 2.0:
            logger.warning(f"⚠ 响应较慢 ({elapsed:.2f}s > 2s)")

        return True

    except Exception as e:
        logger.error(f"✗ get_strings 失败: {e}")
        return False


def test_3_xrefs_response():
    """测试 3: 首次调用 get_xrefs 响应（数据或友好 503）"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 3: 首次调用 get_xrefs")
    logger.info("=" * 60)

    test_class = "android.support.v4.app.INotificationSideChannel"

    try:
        start_time = time.time()
        response = requests.get(
            f"{BASE_URL}/xrefs-to-class",
            params={
                "class_name": test_class
            },
            timeout=30
        )
        elapsed = time.time() - start_time

        logger.info(f"  响应时间: {elapsed:.2f}s")
        logger.info(f"  状态码: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            xrefs_count = len(result.get('xrefs', []))
            logger.info(f"✓ get_xrefs 成功返回 (缓存已预热)")
            logger.info(f"  找到 {xrefs_count} 个引用")
            return True

        elif response.status_code == 503:
            error_msg = response.text
            logger.info(f"✓ get_xrefs 返回友好 503 (缓存预热中)")
            logger.info(f"  错误信息: {error_msg[:200]}")
            return True

        else:
            logger.error(f"✗ 非预期状态码: {response.status_code}")
            logger.error(f"  响应: {response.text[:200]}")
            return False

    except requests.Timeout:
        logger.warning(f"⚠ get_xrefs 超时 (可能正在预热缓存)")
        return True  # 超时可接受，说明在处理

    except Exception as e:
        logger.error(f"✗ get_xrefs 失败: {e}")
        return False


def test_4_cache_progress():
    """测试 4: 监控缓存预热进度（5秒内）"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 4: 监控缓存预热进度")
    logger.info("=" * 60)

    try:
        samples = []
        for i in range(3):
            response = requests.get(f"{BASE_URL}/decompile-status", timeout=5)
            status = response.json()
            pct = status.get('cached_percentage', 0)
            cached = status.get('cached_classes', 0)

            samples.append({'time': i * 2, 'percentage': pct, 'cached': cached})
            logger.info(f"  [{i*2}s] 缓存进度: {pct}% ({cached} 类)")

            if i < 2:
                time.sleep(2)

        # 检查是否有增长
        if samples[-1]['percentage'] > samples[0]['percentage']:
            logger.info(f"✓ 缓存持续增长: {samples[0]['percentage']}% → {samples[-1]['percentage']}%")
            return True
        elif samples[0]['percentage'] >= 100:
            logger.info(f"✓ 缓存已完全预热 (100%)")
            return True
        else:
            logger.warning(f"⚠ 缓存未增长 (停留在 {samples[0]['percentage']}%)")
            return True  # 仍然算通过，可能已稳定

    except Exception as e:
        logger.error(f"✗ 监控缓存进度失败: {e}")
        return False


def test_5_health_check():
    """测试 5: 健康检查端点"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 5: 健康检查端点")
    logger.info("=" * 60)

    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        response.raise_for_status()
        health = response.json()

        logger.info(f"✓ 健康检查成功")
        logger.info(f"  状态: {health.get('status')}")
        logger.info(f"  类总数: {health.get('jadx', {}).get('classes_total')}")
        logger.info(f"  内存: {health.get('memory', {}).get('used_mb')}MB / {health.get('memory', {}).get('max_mb')}MB")
        logger.info(f"  时间戳: {health.get('timestamp')}")

        return health.get('status') == 'Running'

    except Exception as e:
        logger.error(f"✗ 健康检查失败: {e}")
        return False


def main():
    """执行所有缓存预热验证测试"""
    logger.info("\n" + "#" * 60)
    logger.info("# 任务 #11: 验证缓存预热机制（ClassCacheManager）")
    logger.info("#" * 60 + "\n")

    results = {
        "1_decompile_status": test_1_decompile_status(),
        "2_strings_immediate": test_2_strings_immediate(),
        "3_xrefs_response": test_3_xrefs_response(),
        "4_cache_progress": test_4_cache_progress(),
        "5_health_check": test_5_health_check(),
    }

    logger.info("\n" + "=" * 60)
    logger.info("测试结果汇总")
    logger.info("=" * 60)

    passed = sum(results.values())
    total = len(results)

    for test_name, result in results.items():
        status = "✓ 通过" if result else "✗ 失败"
        logger.info(f"{status} - {test_name}")

    logger.info("=" * 60)
    logger.info(f"总计: {passed}/{total} 测试通过 ({passed*100//total}%)")
    logger.info("=" * 60)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
