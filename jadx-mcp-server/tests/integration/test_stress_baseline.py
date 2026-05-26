"""
Layer 3 Stress Test & GUI Baseline Capture

Runs against a live JADX instance (default: http://10.0.5.31:8650) with XHS APK loaded.
Results are saved to tests/integration/fixtures/baseline_gui_results.json for comparison
against future headless mode deployments.

Run with:
    pytest tests/integration/test_stress_baseline.py -m "integration and stress" -v -s

Save baseline:
    pytest tests/integration/test_stress_baseline.py -m "integration and stress" -v -s \
        --tb=short 2>&1 | tee baseline_run.log
"""

import asyncio
import json
import statistics
import time
from datetime import datetime
from pathlib import Path

import httpx
import pytest
import pytest_asyncio

pytestmark = [pytest.mark.integration, pytest.mark.stress]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _p95(latencies: list[float]) -> float:
    """Return the 95th percentile from a list of latency values."""
    if not latencies:
        return 0.0
    s = sorted(latencies)
    idx = max(0, int(len(s) * 0.95) - 1)
    return s[idx]


async def _fetch_class_names(base_url: str, headers: dict, count: int = 20) -> list[str]:
    """Fetch class names from /all-classes endpoint."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{base_url}/all-classes",
            headers=headers,
            params={"offset": 0, "count": count},
        )
        resp.raise_for_status()
        data = resp.json()
        raw = data.get("classes", [])
        return [c.get("name") if isinstance(c, dict) else str(c) for c in raw]


async def _timed_get(client: httpx.AsyncClient, url: str, headers: dict, params: dict | None = None) -> float:
    """Execute a GET request and return elapsed time in milliseconds."""
    t0 = time.time()
    resp = await client.get(url, headers=headers, params=params or {})
    elapsed_ms = (time.time() - t0) * 1000
    resp.raise_for_status()
    return elapsed_ms


# ---------------------------------------------------------------------------
# 1. Concurrent class source
# ---------------------------------------------------------------------------

class TestConcurrentClassSource:
    """10 并发 class-source 请求，采集 P50/P95 延迟作为基线。"""

    @pytest.mark.asyncio
    async def test_concurrent_10(self, xhs_jadx_url, xhs_auth_headers):
        # 1. 取 10 个类名
        class_names = await _fetch_class_names(xhs_jadx_url, xhs_auth_headers, count=10)
        assert len(class_names) >= 1, "无法从 /all-classes 获取类名"

        # 填充到 10 个（如果不够则循环复用）
        while len(class_names) < 10:
            class_names.append(class_names[0])
        class_names = class_names[:10]

        print(f"\n[concurrent-10] 使用类名: {class_names[:3]}...")

        # 2. asyncio.gather 并发请求
        async def fetch_one(class_name: str) -> float | None:
            async with httpx.AsyncClient(timeout=120.0) as client:
                t0 = time.time()
                resp = await client.get(
                    f"{xhs_jadx_url}/class-source",
                    headers=xhs_auth_headers,
                    params={"class_name": class_name},
                )
                elapsed_ms = (time.time() - t0) * 1000
                if resp.status_code == 200:
                    return elapsed_ms
                print(f"[concurrent-10] {class_name} → {resp.status_code} ({elapsed_ms:.0f}ms)")
                return None  # 503/404 计入失败率，不终止测试

        raw = await asyncio.gather(*[fetch_one(cn) for cn in class_names])
        latencies = [r for r in raw if r is not None]
        failed_count = sum(1 for r in raw if r is None)
        print(f"[concurrent-10] 成功={len(latencies)}/10  失败={failed_count}/10")

        # 3. 计算 P50/P95（至少 1 个成功才有意义）
        assert len(latencies) >= 1, f"10 个并发请求全部失败（全是 503/404），服务器无法处理并发"
        p50 = statistics.median(latencies)
        p95 = _p95(latencies)

        # 4. 打印指标
        print(f"[concurrent-10] 延迟 (ms): {[round(l, 1) for l in latencies]}")
        print(f"[concurrent-10] P50={p50:.1f}ms  P95={p95:.1f}ms  max={max(latencies):.1f}ms")

        # 5. 只断言 P95 < 30s（成功请求中）
        assert p95 < 30_000, f"P95={p95:.1f}ms 超过 30s 上限"


# ---------------------------------------------------------------------------
# 2. Search performance
# ---------------------------------------------------------------------------

class TestSearchPerformance:
    """元数据 vs 代码搜索延迟对比。"""

    @pytest.mark.asyncio
    async def test_metadata_search_p95(self, xhs_jadx_url, xhs_auth_headers):
        """5 并发 metadata search，P95 < 5s。"""
        async def one_search(_: int) -> float:
            async with httpx.AsyncClient(timeout=30.0) as client:
                return await _timed_get(
                    client,
                    f"{xhs_jadx_url}/search-classes-by-keyword",
                    xhs_auth_headers,
                    params={"search_term": "Activity", "search_in": "class", "limit": 10},
                )

        latencies = list(await asyncio.gather(*[one_search(i) for i in range(5)]))
        p50 = statistics.median(latencies)
        p95 = _p95(latencies)

        print(f"\n[metadata-search] 延迟 (ms): {[round(l, 1) for l in latencies]}")
        print(f"[metadata-search] P50={p50:.1f}ms  P95={p95:.1f}ms")

        assert p95 < 5_000, f"metadata search P95={p95:.1f}ms 超过 5s 上限"

    @pytest.mark.asyncio
    async def test_code_search_p95(self, xhs_jadx_url, xhs_auth_headers):
        """3 并发 code search，P95 < 120s（code search 较慢）。"""
        async def one_search(_: int) -> float:
            async with httpx.AsyncClient(timeout=180.0) as client:
                return await _timed_get(
                    client,
                    f"{xhs_jadx_url}/search-classes-by-keyword",
                    xhs_auth_headers,
                    params={"search_term": "onCreate", "search_in": "code", "limit": 10},
                )

        latencies = list(await asyncio.gather(*[one_search(i) for i in range(3)]))
        p50 = statistics.median(latencies)
        p95 = _p95(latencies)

        print(f"\n[code-search] 延迟 (ms): {[round(l, 1) for l in latencies]}")
        print(f"[code-search] P50={p50:.1f}ms  P95={p95:.1f}ms")

        assert p95 < 120_000, f"code search P95={p95:.1f}ms 超过 120s 上限"

    @pytest.mark.asyncio
    async def test_search_speed_comparison(self, xhs_jadx_url, xhs_auth_headers):
        """对比单次 metadata vs code search 速度差异（仅打印，不 assert 具体比值）。"""
        async with httpx.AsyncClient(timeout=180.0) as client:
            meta_ms = await _timed_get(
                client,
                f"{xhs_jadx_url}/search-classes-by-keyword",
                xhs_auth_headers,
                params={"search_term": "Service", "search_in": "class", "limit": 10},
            )
            code_ms = await _timed_get(
                client,
                f"{xhs_jadx_url}/search-classes-by-keyword",
                xhs_auth_headers,
                params={"search_term": "onResume", "search_in": "code", "limit": 10},
            )

        ratio = code_ms / meta_ms if meta_ms > 0 else float("inf")
        print(f"\n[search-comparison] metadata={meta_ms:.1f}ms  code={code_ms:.1f}ms  ratio={ratio:.1f}x")

        # 元数据搜索应显著快于代码搜索（或至少不慢于代码搜索的 2000 倍）
        assert meta_ms < 5_000, f"metadata search 单次耗时 {meta_ms:.1f}ms 超过预期"


# ---------------------------------------------------------------------------
# 3. Decompile status stability
# ---------------------------------------------------------------------------

class TestDecompileStatusStability:
    """连续 20 次 decompile-status，验证 total_classes 不漂移，内存不 OOM。"""

    @pytest.mark.asyncio
    async def test_status_stability_20(self, xhs_jadx_url, xhs_auth_headers):
        total_classes_values = []
        memory_values = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            for i in range(20):
                t0 = time.time()
                resp = await client.get(
                    f"{xhs_jadx_url}/decompile-status",
                    headers=xhs_auth_headers,
                )
                elapsed_ms = (time.time() - t0) * 1000

                assert resp.status_code == 200, f"第 {i+1} 次请求返回 {resp.status_code}"

                data = resp.json()
                tc = data.get("total_classes", 0)
                mem_pct = data.get("memory", {}).get("usage_percentage", 0)

                total_classes_values.append(tc)
                memory_values.append(mem_pct)

                if i % 5 == 0:
                    print(f"\n[status-stability] 第{i+1:02d}次: total_classes={tc}, memory={mem_pct:.1f}%, elapsed={elapsed_ms:.1f}ms")

                await asyncio.sleep(0.5)

        # total_classes 全程一致（不漂移）
        unique_tc = set(total_classes_values)
        assert len(unique_tc) == 1, f"total_classes 不一致: {unique_tc}"

        max_memory = max(memory_values)
        print(f"\n[status-stability] total_classes 稳定: {total_classes_values[0]}")
        print(f"[status-stability] memory 最大值: {max_memory:.1f}%  平均值: {statistics.mean(memory_values):.1f}%")

        # 防 OOM
        assert max_memory < 90, f"内存最大使用率 {max_memory:.1f}% 超过 90% 阈值"


# ---------------------------------------------------------------------------
# 4. Batch operations
# ---------------------------------------------------------------------------

class TestBatchOperations:
    """批量请求性能对比。"""

    @pytest.mark.asyncio
    async def test_batch_10(self, xhs_jadx_url, xhs_auth_headers):
        """POST /batch-class-source，10 个类名。"""
        class_names = await _fetch_class_names(xhs_jadx_url, xhs_auth_headers, count=10)
        assert len(class_names) >= 1

        while len(class_names) < 10:
            class_names.append(class_names[0])
        batch_10 = class_names[:10]

        async with httpx.AsyncClient(timeout=120.0) as client:
            t0 = time.time()
            resp = await client.get(
                f"{xhs_jadx_url}/batch-class-source",
                headers=xhs_auth_headers,
                params={"class_names": ",".join(batch_10)},
            )
            elapsed_ms = (time.time() - t0) * 1000

        assert resp.status_code == 200, f"batch-10 返回 {resp.status_code}"
        print(f"\n[batch-10] 耗时: {elapsed_ms:.1f}ms  ({elapsed_ms/10:.1f}ms/class)")

        self.__class__._batch_10_ms = elapsed_ms

    @pytest.mark.asyncio
    async def test_batch_20(self, xhs_jadx_url, xhs_auth_headers):
        """POST /batch-class-source，20 个类名。"""
        class_names = await _fetch_class_names(xhs_jadx_url, xhs_auth_headers, count=20)
        assert len(class_names) >= 1

        while len(class_names) < 20:
            class_names.append(class_names[0])
        batch_20 = class_names[:20]

        async with httpx.AsyncClient(timeout=120.0) as client:
            t0 = time.time()
            resp = await client.get(
                f"{xhs_jadx_url}/batch-class-source",
                headers=xhs_auth_headers,
                params={"class_names": ",".join(batch_20)},
            )
            elapsed_ms = (time.time() - t0) * 1000

        assert resp.status_code == 200, f"batch-20 返回 {resp.status_code}"
        print(f"\n[batch-20] 耗时: {elapsed_ms:.1f}ms  ({elapsed_ms/20:.1f}ms/class)")

        batch_10_ms = getattr(self.__class__, "_batch_10_ms", None)
        if batch_10_ms is not None:
            overhead_ratio = elapsed_ms / batch_10_ms
            print(f"[batch-comparison] batch-10={batch_10_ms:.1f}ms  batch-20={elapsed_ms:.1f}ms  ratio={overhead_ratio:.2f}x")
        else:
            print(f"[batch-comparison] batch-20={elapsed_ms:.1f}ms（batch-10 未记录，单独运行时无对比）")

        self.__class__._batch_20_ms = elapsed_ms


# ---------------------------------------------------------------------------
# 5. Baseline capture
# ---------------------------------------------------------------------------

class TestBaselineCapture:
    """采集所有基线指标并写入 fixtures/baseline_gui_results.json。"""

    @pytest.mark.asyncio
    async def test_capture_baseline(self, xhs_jadx_url, xhs_auth_headers):
        """采集所有基线指标并写入 fixture 文件。"""
        results: dict = {}

        # 1. 运行 class-source（3 个样本取中位数）
        class_names = await _fetch_class_names(xhs_jadx_url, xhs_auth_headers, count=3)
        assert len(class_names) >= 1
        while len(class_names) < 3:
            class_names.append(class_names[0])

        cs_latencies = []
        for cn in class_names[:3]:
            async with httpx.AsyncClient(timeout=120.0) as client:
                ms = await _timed_get(
                    client,
                    f"{xhs_jadx_url}/class-source",
                    xhs_auth_headers,
                    params={"class_name": cn},
                )
                cs_latencies.append(ms)
        class_source_p50 = statistics.median(cs_latencies)

        # 2. 运行 metadata search（3 个样本）
        meta_latencies = []
        for _ in range(3):
            async with httpx.AsyncClient(timeout=30.0) as client:
                ms = await _timed_get(
                    client,
                    f"{xhs_jadx_url}/search-classes-by-keyword",
                    xhs_auth_headers,
                    params={"search_term": "Activity", "search_in": "class", "limit": 10},
                )
                meta_latencies.append(ms)
        metadata_search_p50 = statistics.median(meta_latencies)

        # 3. 获取最终 decompile-status
        async with httpx.AsyncClient(timeout=30.0) as client:
            status_resp = await client.get(
                f"{xhs_jadx_url}/decompile-status",
                headers=xhs_auth_headers,
            )
            status_resp.raise_for_status()
            status_data = status_resp.json()

        total_classes = status_data.get("total_classes", 0)
        cached_percentage = status_data.get("cached_percentage", 0.0)
        memory_usage_pct = status_data.get("memory", {}).get("usage_percentage", 0.0)

        # 4. 获取 index-stats
        trigram_coverage_pct = 0.0
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                idx_resp = await client.get(
                    f"{xhs_jadx_url}/index-stats",
                    headers=xhs_auth_headers,
                )
                if idx_resp.status_code == 200:
                    idx_data = idx_resp.json()
                    trigram = idx_data.get("trigram_index", {})
                    indexed = trigram.get("indexed_classes", 0)
                    total = trigram.get("total_classes", total_classes) or total_classes
                    if total > 0:
                        trigram_coverage_pct = round(indexed / total * 100, 2)
        except Exception as e:
            print(f"\n[baseline] index-stats 获取失败（非致命）: {e}")

        results = {
            "version": "6.5.6",
            "mode": "gui",
            "apk": "xhs_237k_classes",
            "timestamp": datetime.utcnow().isoformat(),
            "server_url": xhs_jadx_url,
            "results": {
                "class_source_p50_ms": round(class_source_p50, 1),
                "metadata_search_p50_ms": round(metadata_search_p50, 1),
                "total_classes": total_classes,
                "cached_percentage": cached_percentage,
                "memory_usage_pct": round(memory_usage_pct, 2),
                "trigram_coverage_pct": trigram_coverage_pct,
            },
        }

        # 写入 fixtures 目录
        fixtures_dir = Path(__file__).parent / "fixtures"
        fixtures_dir.mkdir(exist_ok=True)
        output_path = fixtures_dir / "baseline_gui_results.json"
        output_path.write_text(json.dumps(results, indent=2))

        print(f"\nBaseline saved to: {output_path}")
        print(json.dumps(results, indent=2))

        assert results["results"]["total_classes"] > 200_000, (
            f"total_classes={total_classes} 低于预期（XHS APK 应有 237k+ 类）"
        )
