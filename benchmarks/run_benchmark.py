#!/usr/bin/env python3
"""
Container-friendly benchmark runner for JADX AI MCP.

Designed to run against a live all-in-one container or a split plugin/MCP stack.
The script collects a reproducible baseline before optimization and can generate
before/after comparison reports from saved JSON outputs.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import re
import statistics
import subprocess
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from fastmcp import Client


DEFAULT_CONFIG = {
    "sample_discovery": {
        "candidate_limit": 60,
        "class_page_limit": 200,
        "request_timeout_seconds": 120,
        "sample_override": {},
    },
    "targets": [
        {"name": "plugin", "enabled": True},
        {"name": "mcp", "enabled": True},
    ],
    "scenarios": [
        {
            "name": "cold_start",
            "warmup": False,
            "iterations_per_worker": 1,
            "concurrency_levels": [1],
            "workloads": ["metadata", "decompile", "code_search_only", "xref_only", "search_xref", "mixed"],
        },
        {
            "name": "warm_cache",
            "warmup": True,
            "iterations_per_worker": 3,
            "concurrency_levels": [1, 8, 24],
            "workloads": ["metadata", "decompile", "code_search_only", "xref_only", "search_xref", "mixed"],
        },
        {
            "name": "degraded_pressure",
            "warmup": True,
            "iterations_per_worker": 4,
            "concurrency_levels": [24, 48],
            "workloads": ["code_search_only", "xref_only", "search_xref", "mixed"],
        },
    ],
}


@dataclass(frozen=True)
class OperationSpec:
    name: str
    plugin_path: str
    plugin_params: dict[str, Any]
    mcp_tool: str
    mcp_args: dict[str, Any]


@dataclass
class SampleSet:
    apk_info: dict[str, Any]
    primary_class: str
    secondary_class: str
    primary_method: str
    primary_field: str
    search_term: str
    package_filter: str
    class_source_hint: str
    class_candidates_checked: list[str] = field(default_factory=list)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    position = (len(ordered) - 1) * (pct / 100.0)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    lower_value = ordered[lower]
    upper_value = ordered[upper]
    return lower_value + (upper_value - lower_value) * (position - lower)


def merge_config(defaults: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = dict(defaults)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_config(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Benchmark config not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        user_config = json.load(handle)
    return merge_config(DEFAULT_CONFIG, user_config)


def safe_filename(label: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", label).strip("-") or "benchmark"


def short_text(value: str, limit: int = 140) -> str:
    value = value.strip()
    return value if len(value) <= limit else value[: limit - 3] + "..."


def repo_git_value(args: list[str]) -> str:
    try:
        completed = subprocess.run(
            args,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return "unknown"
    return completed.stdout.strip() or "unknown"


def detect_package(class_name: str) -> str:
    if "." not in class_name:
        return ""
    return class_name.rsplit(".", 1)[0]


def class_basename(class_name: str) -> str:
    last = class_name.rsplit(".", 1)[-1]
    return last.split("$", 1)[0]


def normalize_class_names(payload: Any) -> list[str]:
    classes = []
    if isinstance(payload, dict):
        payload = payload.get("classes", payload.get("class_names", []))
    if not isinstance(payload, list):
        return classes
    for item in payload:
        if isinstance(item, dict):
            name = item.get("name") or item.get("class_name")
        else:
            name = item
        if isinstance(name, str) and name:
            classes.append(name)
    return classes


def choose_class_candidate(classes: list[str]) -> list[str]:
    ranked: list[str] = []
    fallback: list[str] = []
    for name in classes:
        if ".R" in name or name.endswith(".R") or name.endswith("BuildConfig"):
            fallback.append(name)
            continue
        if "$" in name:
            fallback.append(name)
            continue
        simple_name = class_basename(name)
        if len(simple_name) < 3:
            fallback.append(name)
            continue
        ranked.append(name)
    return ranked + fallback


async def request_json(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
) -> tuple[int, Any]:
    response = await client.request(method, url, headers=headers, params=params)
    try:
        payload = response.json()
    except ValueError:
        payload = {"raw_text": response.text}
    return response.status_code, payload


async def wait_for_endpoint(
    url: str,
    *,
    headers: dict[str, str],
    ready_codes: set[int],
    timeout_seconds: int,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    async with httpx.AsyncClient(timeout=10.0) as client:
        while time.monotonic() < deadline:
            try:
                response = await client.get(url, headers=headers)
                if response.status_code in ready_codes:
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(2)
    raise TimeoutError(f"Timed out waiting for endpoint: {url}")


async def wait_for_mcp_ready(
    base_url: str,
    *,
    token: str,
    timeout_seconds: int,
) -> None:
    if not base_url:
        return

    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    deadline = time.monotonic() + timeout_seconds
    async with httpx.AsyncClient(timeout=10.0) as client:
        while time.monotonic() < deadline:
            try:
                response = await client.get(f"{base_url.rstrip('/')}/status.json", headers=headers)
                if response.status_code == 200:
                    payload = response.json()
                    summary = payload.get("summary", {}) if isinstance(payload, dict) else {}
                    pending = int((summary.get("status_counts") or {}).get("pending", 0))
                    total_instances = int(summary.get("total_instances", 0))
                    if total_instances > 0 and pending == 0:
                        return
                elif response.status_code == 401:
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(2)

    raise TimeoutError(f"Timed out waiting for MCP instances to become ready: {base_url}")


def build_plugin_headers(token: str) -> dict[str, str]:
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def build_mcp_auth(token: str) -> str | None:
    return token or None


def normalize_mcp_urls(raw_url: str) -> tuple[str, str]:
    if not raw_url:
        return "", ""
    root = raw_url.rstrip("/")
    if root.endswith("/mcp"):
        return root[:-4] or root, root
    return root, f"{root}/mcp"


async def collect_plugin_state(base_url: str, token: str, timeout: float) -> dict[str, Any]:
    headers = build_plugin_headers(token)
    async with httpx.AsyncClient(timeout=timeout) as client:
        status: dict[str, Any] = {}
        for endpoint in ("health", "apk-info", "decompile-status"):
            try:
                code, payload = await request_json(client, "GET", f"{base_url}/{endpoint}", headers=headers)
                status[endpoint.replace("-", "_")] = {
                    "http_status": code,
                    "payload": payload,
                }
            except Exception as exc:  # pragma: no cover - defensive instrumentation
                status[endpoint.replace("-", "_")] = {
                    "http_status": 0,
                    "error": f"{type(exc).__name__}: {exc}",
                }
        return status


async def collect_mcp_state(base_url: str, token: str, timeout: float) -> dict[str, Any]:
    if not base_url:
        return {}
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            code, payload = await request_json(client, "GET", f"{base_url}/status.json", headers=headers)
            return {
                "status_json": {
                    "http_status": code,
                    "payload": payload,
                }
            }
        except Exception as exc:  # pragma: no cover - defensive instrumentation
            return {
                "status_json": {
                    "http_status": 0,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            }


def classify_plugin_response(status_code: int, payload: Any) -> tuple[str, str]:
    if status_code == 200:
        return "ok", ""
    if status_code == 503:
        if isinstance(payload, dict) and (payload.get("busy") or "busy" in str(payload.get("error", "")).lower()):
            return "busy", short_text(json.dumps(payload, ensure_ascii=False))
        return "error", short_text(json.dumps(payload, ensure_ascii=False))
    if isinstance(payload, dict):
        message = payload.get("error") or payload.get("message") or json.dumps(payload, ensure_ascii=False)
    else:
        message = str(payload)
    return "error", short_text(message)


def classify_mcp_result(result: Any) -> tuple[str, str, Any]:
    structured = getattr(result, "structured_content", None)
    is_error = bool(getattr(result, "is_error", False))
    if isinstance(structured, dict):
        structured_error = str(structured.get("error", "")).strip()
        structured_message = str(structured.get("message", "")).strip()
        lowered_error = structured_error.lower()
        lowered_message = structured_message.lower()
        if structured_error == "INSTANCE_BUSY" or "busy" in lowered_error or "busy" in lowered_message:
            return "busy", short_text(structured_message or structured_error), structured
        if structured_error:
            return "error", short_text(structured_message or structured_error), structured
    if not is_error:
        return "ok", "", structured

    content = getattr(result, "content", [])
    text_chunks = []
    for item in content or []:
        text = getattr(item, "text", None)
        if text:
            text_chunks.append(text)
    joined = " ".join(text_chunks)
    lowered = joined.lower()
    if "busy" in lowered or "instance_busy" in lowered:
        return "busy", short_text(joined), structured
    return "error", short_text(joined or str(structured)), structured


async def discover_samples(
    base_url: str,
    *,
    plugin_token: str,
    timeout: float,
    candidate_limit: int,
    class_page_limit: int,
    sample_override: dict[str, Any] | None = None,
) -> SampleSet:
    headers = build_plugin_headers(plugin_token)
    async with httpx.AsyncClient(timeout=timeout) as client:
        _, apk_info = await request_json(client, "GET", f"{base_url}/apk-info", headers=headers)
        if sample_override:
            primary_class = str(sample_override.get("primary_class", "")).strip()
            primary_method = str(sample_override.get("primary_method", "")).strip()
            if not primary_class or not primary_method:
                raise RuntimeError("sample_override requires primary_class and primary_method")
            secondary_class = str(sample_override.get("secondary_class", "")).strip() or primary_class
            primary_field = str(sample_override.get("primary_field", "")).strip()
            search_term = str(sample_override.get("search_term", "")).strip() or primary_method
            package_filter = str(sample_override.get("package_filter", "")).strip() or detect_package(primary_class)
            class_source_hint = (
                str(sample_override.get("class_source_hint", "")).strip()
                or class_basename(primary_class)
            )
            checked = [primary_class]
            if secondary_class != primary_class:
                checked.append(secondary_class)
            return SampleSet(
                apk_info=apk_info if isinstance(apk_info, dict) else {},
                primary_class=primary_class,
                secondary_class=secondary_class,
                primary_method=primary_method,
                primary_field=primary_field,
                search_term=search_term,
                package_filter=package_filter,
                class_source_hint=class_source_hint,
                class_candidates_checked=checked,
            )

        class_pool: list[str] = []

        status_code, main_activity_payload = await request_json(
            client, "GET", f"{base_url}/main-activity", headers=headers
        )
        if status_code == 200 and isinstance(main_activity_payload, dict):
            main_activity_name = main_activity_payload.get("name")
            if isinstance(main_activity_name, str) and main_activity_name:
                class_pool.append(main_activity_name)

        status_code, preferred_payload = await request_json(
            client, "GET", f"{base_url}/main-application-classes-names", headers=headers
        )
        if status_code == 200:
            class_pool.extend(normalize_class_names(preferred_payload))

        if not class_pool:
            _, all_classes_payload = await request_json(
                client,
                "GET",
                f"{base_url}/all-classes",
                headers=headers,
                params={"offset": 0, "limit": class_page_limit},
            )
            class_pool.extend(normalize_class_names(all_classes_payload))

        if not class_pool:
            raise RuntimeError("Unable to discover classes from plugin endpoints")

        candidates = choose_class_candidate(class_pool[:candidate_limit])
        checked: list[str] = []

        for class_name in candidates:
            checked.append(class_name)
            _, methods_payload = await request_json(
                client,
                "GET",
                f"{base_url}/methods-of-class",
                headers=headers,
                params={"class_name": class_name},
            )
            methods = methods_payload.get("methods", []) if isinstance(methods_payload, dict) else []
            picked_method = ""
            for item in methods:
                if not isinstance(item, dict):
                    continue
                method_name = item.get("name", "")
                if item.get("is_constructor"):
                    continue
                if method_name in {"equals", "hashCode", "toString"}:
                    continue
                if len(method_name) < 2:
                    continue
                picked_method = method_name
                break
            if not picked_method:
                continue

            _, fields_payload = await request_json(
                client,
                "GET",
                f"{base_url}/fields-of-class",
                headers=headers,
                params={"class_name": class_name},
            )
            fields = fields_payload.get("fields", []) if isinstance(fields_payload, dict) else []
            picked_field = ""
            for item in fields:
                if isinstance(item, dict) and item.get("name"):
                    picked_field = item["name"]
                    break

            primary_class = class_name
            secondary_class = next((name for name in candidates if name != primary_class), primary_class)
            base_name = class_basename(primary_class)
            package_filter = detect_package(primary_class)
            search_term = picked_method if len(picked_method) >= 4 else base_name
            return SampleSet(
                apk_info=apk_info if isinstance(apk_info, dict) else {},
                primary_class=primary_class,
                secondary_class=secondary_class,
                primary_method=picked_method,
                primary_field=picked_field,
                search_term=search_term,
                package_filter=package_filter,
                class_source_hint=base_name,
                class_candidates_checked=checked,
            )

    raise RuntimeError("Unable to find a class with a usable non-constructor method")


def build_operations(sample: SampleSet) -> dict[str, list[OperationSpec]]:
    metadata = [
        OperationSpec(
            name="list-all-classes",
            plugin_path="/all-classes",
            plugin_params={"offset": 0, "limit": 50},
            mcp_tool="get_all_classes",
            mcp_args={"offset": 0, "count": 50},
        ),
        OperationSpec(
            name="class-search-metadata",
            plugin_path="/search-classes-by-keyword",
            plugin_params={
                "search_term": sample.class_source_hint,
                "search_in": "class",
                "package": sample.package_filter,
                "count": 20,
            },
            mcp_tool="search_classes_by_keyword",
            mcp_args={
                "search_term": sample.class_source_hint,
                "search_in": "class",
                "package": sample.package_filter,
                "count": 20,
            },
        ),
        OperationSpec(
            name="methods-of-class",
            plugin_path="/methods-of-class",
            plugin_params={"class_name": sample.primary_class},
            mcp_tool="get_methods_of_class",
            mcp_args={"class_name": sample.primary_class},
        ),
        OperationSpec(
            name="fields-of-class",
            plugin_path="/fields-of-class",
            plugin_params={"class_name": sample.primary_class},
            mcp_tool="get_fields_of_class",
            mcp_args={"class_name": sample.primary_class},
        ),
        OperationSpec(
            name="class-info",
            plugin_path="/class-info",
            plugin_params={"class_name": sample.primary_class},
            mcp_tool="get_class_info",
            mcp_args={"class_name": sample.primary_class},
        ),
    ]

    decompile = [
        OperationSpec(
            name="class-source",
            plugin_path="/class-source",
            plugin_params={"class_name": sample.primary_class, "chunk": 0},
            mcp_tool="get_class_source",
            mcp_args={"class_name": sample.primary_class, "chunk": 0},
        ),
        OperationSpec(
            name="smali-of-class",
            plugin_path="/smali-of-class",
            plugin_params={"class_name": sample.primary_class, "chunk": 0},
            mcp_tool="get_smali_of_class",
            mcp_args={"class_name": sample.primary_class, "chunk": 0},
        ),
        OperationSpec(
            name="method-by-name",
            plugin_path="/method-by-name",
            plugin_params={"class_name": sample.primary_class, "method_name": sample.primary_method},
            mcp_tool="get_method_by_name",
            mcp_args={"class_name": sample.primary_class, "method_name": sample.primary_method},
        ),
    ]

    code_search_only = [
        OperationSpec(
            name="code-search",
            plugin_path="/search-classes-by-keyword",
            plugin_params={
                "search_term": sample.search_term,
                "search_in": "code",
                "package": sample.package_filter,
                "count": 20,
            },
            mcp_tool="search_classes_by_keyword",
            mcp_args={
                "search_term": sample.search_term,
                "search_in": "code",
                "package": sample.package_filter,
                "count": 20,
            },
        ),
    ]

    xref_only = [
        OperationSpec(
            name="xrefs-to-class",
            plugin_path="/xrefs-to-class",
            plugin_params={"class_name": sample.primary_class, "offset": 0, "count": 20},
            mcp_tool="get_xrefs",
            mcp_args={
                "target_type": "class",
                "class_name": sample.primary_class,
                "offset": 0,
                "count": 20,
            },
        ),
        OperationSpec(
            name="xrefs-to-method",
            plugin_path="/xrefs-to-method",
            plugin_params={"class_name": sample.primary_class, "method_name": sample.primary_method, "offset": 0, "count": 20},
            mcp_tool="get_xrefs",
            mcp_args={
                "target_type": "method",
                "class_name": sample.primary_class,
                "member_name": sample.primary_method,
                "offset": 0,
                "count": 20,
            },
        ),
    ]

    search_xref = [
        OperationSpec(
            name="search-method",
            plugin_path="/search-method",
            plugin_params={"method_name": sample.primary_method, "offset": 0, "count": 20},
            mcp_tool="search_method_by_name",
            mcp_args={"method_name": sample.primary_method, "offset": 0, "count": 20},
        ),
        code_search_only[0],
        xref_only[0],
        xref_only[1],
    ]

    mixed = [
        metadata[1],
        metadata[2],
        decompile[0],
        decompile[2],
        search_xref[0],
        code_search_only[0],
    ]

    if sample.primary_field:
        field_xref = OperationSpec(
            name="xrefs-to-field",
            plugin_path="/xrefs-to-field",
            plugin_params={"class_name": sample.primary_class, "field_name": sample.primary_field, "offset": 0, "count": 20},
            mcp_tool="get_xrefs",
            mcp_args={
                "target_type": "field",
                "class_name": sample.primary_class,
                "member_name": sample.primary_field,
                "offset": 0,
                "count": 20,
            },
        )
        xref_only.append(field_xref)
        search_xref.append(field_xref)

    return {
        "metadata": metadata,
        "decompile": decompile,
        "code_search_only": code_search_only,
        "xref_only": xref_only,
        "search_xref": search_xref,
        "mixed": mixed,
    }


async def warmup_target(
    target: str,
    operations: dict[str, list[OperationSpec]],
    *,
    plugin_base_url: str,
    plugin_token: str,
    mcp_transport_url: str,
    mcp_token: str,
    timeout: float,
) -> list[str]:
    messages: list[str] = []
    warmup_ops = operations["metadata"][:2] + operations["decompile"][:1]

    if target == "plugin":
        headers = build_plugin_headers(plugin_token)
        async with httpx.AsyncClient(timeout=timeout) as client:
            for spec in warmup_ops:
                status_code, payload = await request_json(
                    client,
                    "GET",
                    f"{plugin_base_url}{spec.plugin_path}",
                    headers=headers,
                    params=spec.plugin_params,
                )
                outcome, detail = classify_plugin_response(status_code, payload)
                messages.append(f"{spec.name}:{outcome}")
                if detail:
                    messages.append(detail)
    else:
        try:
            async with Client(mcp_transport_url, auth=build_mcp_auth(mcp_token), timeout=timeout) as client:
                for spec in warmup_ops:
                    try:
                        result = await client.call_tool(spec.mcp_tool, spec.mcp_args, raise_on_error=False)
                        outcome, detail, _ = classify_mcp_result(result)
                    except Exception as exc:
                        outcome = "error"
                        detail = short_text(f"{type(exc).__name__}: {exc}")
                    messages.append(f"{spec.name}:{outcome}")
                    if detail:
                        messages.append(detail)
        except Exception as exc:
            messages.append(f"mcp-session:error:{short_text(f'{type(exc).__name__}: {exc}')}")

    return messages


async def run_plugin_case(
    operations: list[OperationSpec],
    *,
    base_url: str,
    token: str,
    concurrency: int,
    iterations_per_worker: int,
    timeout: float,
) -> tuple[list[dict[str, Any]], float]:
    headers = build_plugin_headers(token)
    results: list[dict[str, Any]] = []
    lock = asyncio.Lock()

    async def worker(worker_id: int) -> None:
        async with httpx.AsyncClient(timeout=timeout) as client:
            for iteration in range(iterations_per_worker):
                spec = operations[(worker_id * iterations_per_worker + iteration) % len(operations)]
                started = time.perf_counter()
                try:
                    status_code, payload = await request_json(
                        client,
                        "GET",
                        f"{base_url}{spec.plugin_path}",
                        headers=headers,
                        params=spec.plugin_params,
                    )
                    outcome, detail = classify_plugin_response(status_code, payload)
                    record = {
                        "operation": spec.name,
                        "outcome": outcome,
                        "latency_ms": (time.perf_counter() - started) * 1000.0,
                        "status_code": status_code,
                        "detail": detail,
                    }
                except Exception as exc:
                    record = {
                        "operation": spec.name,
                        "outcome": "error",
                        "latency_ms": (time.perf_counter() - started) * 1000.0,
                        "status_code": 0,
                        "detail": short_text(f"{type(exc).__name__}: {exc}"),
                    }
                async with lock:
                    results.append(record)

    wall_started = time.perf_counter()
    await asyncio.gather(*(worker(index) for index in range(concurrency)))
    wall_seconds = time.perf_counter() - wall_started
    return results, wall_seconds


async def run_mcp_case(
    operations: list[OperationSpec],
    *,
    mcp_transport_url: str,
    token: str,
    concurrency: int,
    iterations_per_worker: int,
    timeout: float,
) -> tuple[list[dict[str, Any]], float]:
    results: list[dict[str, Any]] = []
    lock = asyncio.Lock()

    async def worker(worker_id: int) -> None:
        completed_iterations = 0
        try:
            async with Client(mcp_transport_url, auth=build_mcp_auth(token), timeout=timeout) as client:
                for iteration in range(iterations_per_worker):
                    spec = operations[(worker_id * iterations_per_worker + iteration) % len(operations)]
                    started = time.perf_counter()
                    try:
                        result = await client.call_tool(spec.mcp_tool, spec.mcp_args, raise_on_error=False)
                        outcome, detail, structured = classify_mcp_result(result)
                        record = {
                            "operation": spec.name,
                            "outcome": outcome,
                            "latency_ms": (time.perf_counter() - started) * 1000.0,
                            "status_code": 200,
                            "detail": detail,
                            "structured_preview": short_text(json.dumps(structured, ensure_ascii=False)) if structured else "",
                        }
                    except Exception as exc:
                        record = {
                            "operation": spec.name,
                            "outcome": "error",
                            "latency_ms": (time.perf_counter() - started) * 1000.0,
                            "status_code": 0,
                            "detail": short_text(f"{type(exc).__name__}: {exc}"),
                        }
                    async with lock:
                        results.append(record)
                    completed_iterations += 1
        except Exception as exc:
            detail = short_text(f"{type(exc).__name__}: {exc}")
            for iteration in range(completed_iterations, iterations_per_worker):
                spec = operations[(worker_id * iterations_per_worker + iteration) % len(operations)]
                async with lock:
                    results.append(
                        {
                            "operation": spec.name,
                            "outcome": "error",
                            "latency_ms": 0.0,
                            "status_code": 0,
                            "detail": detail,
                        }
                    )

    wall_started = time.perf_counter()
    await asyncio.gather(*(worker(index) for index in range(concurrency)))
    wall_seconds = time.perf_counter() - wall_started
    return results, wall_seconds


def summarize_case_results(
    *,
    target: str,
    scenario: str,
    workload: str,
    concurrency: int,
    iterations_per_worker: int,
    wall_seconds: float,
    results: list[dict[str, Any]],
    pre_state: dict[str, Any],
    post_state: dict[str, Any],
    warmup_trace: list[str],
) -> dict[str, Any]:
    latencies = [item["latency_ms"] for item in results]
    status_codes = Counter(str(item.get("status_code", 0)) for item in results)
    outcome_counts = Counter(item["outcome"] for item in results)
    detail_counts = Counter(item["detail"] for item in results if item.get("detail"))

    total = len(results)
    ok_count = outcome_counts.get("ok", 0)
    busy_count = outcome_counts.get("busy", 0)
    error_count = outcome_counts.get("error", 0)

    return {
        "target": target,
        "scenario": scenario,
        "workload": workload,
        "concurrency": concurrency,
        "iterations_per_worker": iterations_per_worker,
        "total_requests": total,
        "ok_count": ok_count,
        "busy_count": busy_count,
        "error_count": error_count,
        "ok_rate": round((ok_count / total) if total else 0.0, 4),
        "busy_rate": round((busy_count / total) if total else 0.0, 4),
        "error_rate": round((error_count / total) if total else 0.0, 4),
        "wall_seconds": round(wall_seconds, 4),
        "total_rps": round((total / wall_seconds) if wall_seconds else 0.0, 2),
        "ok_rps": round((ok_count / wall_seconds) if wall_seconds else 0.0, 2),
        "latency_ms": {
            "mean": round(statistics.fmean(latencies), 2) if latencies else 0.0,
            "p50": round(percentile(latencies, 50), 2),
            "p95": round(percentile(latencies, 95), 2),
            "p99": round(percentile(latencies, 99), 2),
            "max": round(max(latencies), 2) if latencies else 0.0,
        },
        "status_codes": dict(status_codes),
        "operation_mix": dict(Counter(item["operation"] for item in results)),
        "top_errors": [{"message": key, "count": value} for key, value in detail_counts.most_common(5)],
        "warmup_trace": warmup_trace,
        "pre_state": pre_state,
        "post_state": post_state,
    }


async def benchmark_target(
    target_name: str,
    config: dict[str, Any],
    operations: dict[str, list[OperationSpec]],
    *,
    plugin_base_url: str,
    plugin_token: str,
    mcp_root_url: str,
    mcp_transport_url: str,
    mcp_token: str,
    timeout: float,
) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    warm_state: list[str] = []

    for scenario in config["scenarios"]:
        if scenario.get("warmup"):
            warm_state = await warmup_target(
                target_name,
                operations,
                plugin_base_url=plugin_base_url,
                plugin_token=plugin_token,
                mcp_transport_url=mcp_transport_url,
                mcp_token=mcp_token,
                timeout=timeout,
            )
        else:
            warm_state = []

        for workload in scenario["workloads"]:
            workload_ops = operations[workload]
            for concurrency in scenario["concurrency_levels"]:
                pre_plugin = await collect_plugin_state(plugin_base_url, plugin_token, timeout)
                pre_mcp = await collect_mcp_state(mcp_root_url, mcp_token, timeout) if mcp_root_url else {}
                if target_name == "plugin":
                    results, wall_seconds = await run_plugin_case(
                        workload_ops,
                        base_url=plugin_base_url,
                        token=plugin_token,
                        concurrency=concurrency,
                        iterations_per_worker=scenario["iterations_per_worker"],
                        timeout=timeout,
                    )
                else:
                    results, wall_seconds = await run_mcp_case(
                        workload_ops,
                        mcp_transport_url=mcp_transport_url,
                        token=mcp_token,
                        concurrency=concurrency,
                        iterations_per_worker=scenario["iterations_per_worker"],
                        timeout=timeout,
                    )
                post_plugin = await collect_plugin_state(plugin_base_url, plugin_token, timeout)
                post_mcp = await collect_mcp_state(mcp_root_url, mcp_token, timeout) if mcp_root_url else {}
                cases.append(
                    summarize_case_results(
                        target=target_name,
                        scenario=scenario["name"],
                        workload=workload,
                        concurrency=concurrency,
                        iterations_per_worker=scenario["iterations_per_worker"],
                        wall_seconds=wall_seconds,
                        results=results,
                        pre_state={"plugin": pre_plugin, "mcp": pre_mcp},
                        post_state={"plugin": post_plugin, "mcp": post_mcp},
                        warmup_trace=warm_state,
                    )
                )

    return {
        "target": target_name,
        "cases": cases,
    }


def summarize_report(report: dict[str, Any]) -> dict[str, Any]:
    all_cases = [case for target in report["targets"] for case in target["cases"]]
    if not all_cases:
        return {"case_count": 0}

    return {
        "case_count": len(all_cases),
        "ok_rps_mean": round(statistics.fmean(case["ok_rps"] for case in all_cases), 2),
        "max_p95_ms": round(max(case["latency_ms"]["p95"] for case in all_cases), 2),
        "busy_cases": sum(1 for case in all_cases if case["busy_count"] > 0),
        "error_cases": sum(1 for case in all_cases if case["error_count"] > 0),
    }


def flatten_cases(report: dict[str, Any]) -> dict[tuple[str, str, str, int], dict[str, Any]]:
    flattened = {}
    for target in report.get("targets", []):
        for case in target.get("cases", []):
            key = (
                case["target"],
                case["scenario"],
                case["workload"],
                int(case["concurrency"]),
            )
            flattened[key] = case
    return flattened


def build_compare_summary(current: dict[str, Any], baseline: dict[str, Any]) -> list[dict[str, Any]]:
    baseline_cases = flatten_cases(baseline)
    comparisons: list[dict[str, Any]] = []
    for key, current_case in flatten_cases(current).items():
        if key not in baseline_cases:
            continue
        baseline_case = baseline_cases[key]
        comparisons.append(
            {
                "target": key[0],
                "scenario": key[1],
                "workload": key[2],
                "concurrency": key[3],
                "ok_rps_delta": round(current_case["ok_rps"] - baseline_case["ok_rps"], 2),
                "p95_delta_ms": round(
                    current_case["latency_ms"]["p95"] - baseline_case["latency_ms"]["p95"],
                    2,
                ),
                "busy_rate_delta": round(current_case["busy_rate"] - baseline_case["busy_rate"], 4),
                "error_rate_delta": round(current_case["error_rate"] - baseline_case["error_rate"], 4),
                "verdict": (
                    "pass"
                    if current_case["ok_rps"] >= baseline_case["ok_rps"]
                    and current_case["latency_ms"]["p95"] <= baseline_case["latency_ms"]["p95"]
                    and current_case["busy_rate"] <= baseline_case["busy_rate"]
                    and current_case["error_rate"] <= baseline_case["error_rate"]
                    else "regression"
                ),
            }
        )
    return comparisons


def render_markdown(report: dict[str, Any], compare_rows: list[dict[str, Any]] | None = None) -> str:
    lines = [
        f"# Benchmark Report: {report['label']}",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- Git commit: `{report['environment']['git_commit']}`",
        f"- Git branch: `{report['environment']['git_branch']}`",
        f"- Image tag: `{report['environment'].get('image_tag', 'unknown')}`",
        f"- APK package: `{report['environment']['sample']['apk_info'].get('apk_package', '-')}`",
        f"- Primary class: `{report['environment']['sample']['primary_class']}`",
        f"- Primary method: `{report['environment']['sample']['primary_method']}`",
        "",
        "## Summary",
        "",
        f"- Cases: `{report['summary']['case_count']}`",
        f"- Mean ok_rps: `{report['summary'].get('ok_rps_mean', 0)}`",
        f"- Max p95: `{report['summary'].get('max_p95_ms', 0)} ms`",
        f"- Cases with busy: `{report['summary'].get('busy_cases', 0)}`",
        f"- Cases with errors: `{report['summary'].get('error_cases', 0)}`",
        "",
        "## Cases",
        "",
        "| Target | Scenario | Workload | Concurrency | OK/Busy/Error | ok_rps | p95 ms | p99 ms |",
        "| --- | --- | --- | ---: | --- | ---: | ---: | ---: |",
    ]

    for target in report["targets"]:
        for case in target["cases"]:
            lines.append(
                "| {target} | {scenario} | {workload} | {concurrency} | {ok}/{busy}/{error} | {ok_rps} | {p95} | {p99} |".format(
                    target=case["target"],
                    scenario=case["scenario"],
                    workload=case["workload"],
                    concurrency=case["concurrency"],
                    ok=case["ok_count"],
                    busy=case["busy_count"],
                    error=case["error_count"],
                    ok_rps=case["ok_rps"],
                    p95=case["latency_ms"]["p95"],
                    p99=case["latency_ms"]["p99"],
                )
            )

    if compare_rows:
        lines.extend(
            [
                "",
                "## Comparison",
                "",
                "| Target | Scenario | Workload | Concurrency | Verdict | ok_rps delta | p95 delta ms | busy rate delta | error rate delta |",
                "| --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: |",
            ]
        )
        for row in compare_rows:
            lines.append(
                "| {target} | {scenario} | {workload} | {concurrency} | {verdict} | {ok_rps_delta} | {p95_delta_ms} | {busy_rate_delta} | {error_rate_delta} |".format(
                    **row
                )
            )

    return "\n".join(lines) + "\n"


async def main_async(args: argparse.Namespace) -> int:
    config = load_config(Path(args.config))
    timeout = float(config["sample_discovery"]["request_timeout_seconds"])
    mcp_root_url, mcp_transport_url = normalize_mcp_urls(args.mcp_base_url)

    await wait_for_endpoint(
        f"{args.plugin_base_url}/health",
        headers=build_plugin_headers(args.plugin_auth_token),
        ready_codes={200},
        timeout_seconds=args.wait_timeout,
    )
    if mcp_root_url:
        mcp_headers = {}
        if args.mcp_auth_token:
            mcp_headers["Authorization"] = f"Bearer {args.mcp_auth_token}"
        await wait_for_endpoint(
            f"{mcp_root_url}/status.json",
            headers=mcp_headers,
            ready_codes={200, 401},
            timeout_seconds=args.wait_timeout,
        )
        await wait_for_mcp_ready(
            mcp_root_url,
            token=args.mcp_auth_token,
            timeout_seconds=args.wait_timeout,
        )

    sample = await discover_samples(
        args.plugin_base_url,
        plugin_token=args.plugin_auth_token,
        timeout=timeout,
        candidate_limit=int(config["sample_discovery"]["candidate_limit"]),
        class_page_limit=int(config["sample_discovery"]["class_page_limit"]),
        sample_override=config["sample_discovery"].get("sample_override") or None,
    )
    operations = build_operations(sample)

    enabled_targets = [item["name"] for item in config["targets"] if item.get("enabled", True)]
    targets: list[dict[str, Any]] = []

    for target_name in enabled_targets:
        if target_name == "mcp" and not mcp_root_url:
            continue
        if target_name == "mcp" and not args.mcp_auth_token:
            probe = await collect_mcp_state(mcp_root_url, "", timeout)
            http_status = probe.get("status_json", {}).get("http_status")
            if http_status == 401:
                targets.append(
                    {
                        "target": "mcp",
                        "skipped": True,
                        "reason": "MCP auth required but no --mcp-auth-token provided",
                        "cases": [],
                    }
                )
                continue

        targets.append(
            await benchmark_target(
                target_name,
                config,
                operations,
                plugin_base_url=args.plugin_base_url,
                plugin_token=args.plugin_auth_token,
                mcp_root_url=mcp_root_url,
                mcp_transport_url=mcp_transport_url,
                mcp_token=args.mcp_auth_token,
                timeout=timeout,
            )
        )

    report = {
        "generated_at": utc_now_iso(),
        "label": args.label,
        "config": config,
        "environment": {
            "git_commit": args.git_commit or repo_git_value(["git", "rev-parse", "HEAD"]),
            "git_branch": args.git_branch or repo_git_value(["git", "rev-parse", "--abbrev-ref", "HEAD"]),
            "image_tag": args.image_tag or "unknown",
            "plugin_base_url": args.plugin_base_url,
            "mcp_base_url": mcp_root_url,
            "mcp_transport_url": mcp_transport_url,
            "sample": asdict(sample),
        },
        "targets": targets,
    }
    report["summary"] = summarize_report(report)

    compare_rows: list[dict[str, Any]] | None = None
    if args.compare:
        with Path(args.compare).open("r", encoding="utf-8") as handle:
            baseline_report = json.load(handle)
        compare_rows = build_compare_summary(report, baseline_report)
        report["compare"] = compare_rows

    output_dir = Path(args.results_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}_{safe_filename(args.label)}"
    json_path = output_dir / f"{prefix}.json"
    md_path = output_dir / f"{prefix}.md"

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report, compare_rows), encoding="utf-8")

    if args.compare and compare_rows is not None:
        compare_path = output_dir / f"{prefix}_compare.md"
        compare_path.write_text(render_markdown(report, compare_rows), encoding="utf-8")

    print(f"Benchmark JSON: {json_path}")
    print(f"Benchmark Markdown: {md_path}")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run JADX AI MCP benchmarks")
    parser.add_argument("--config", default="benchmarks/default_matrix.json", help="Path to benchmark config JSON")
    parser.add_argument("--label", default="baseline", help="Result label")
    parser.add_argument("--results-dir", default="temp/benchmark-results", help="Directory for JSON and Markdown reports")
    parser.add_argument("--plugin-base-url", required=True, help="Plugin base URL, e.g. http://127.0.0.1:8650")
    parser.add_argument("--plugin-auth-token", default="", help="Plugin Bearer token")
    parser.add_argument("--mcp-base-url", default="", help="MCP base URL, e.g. http://127.0.0.1:8651")
    parser.add_argument("--mcp-auth-token", default="", help="MCP Bearer token")
    parser.add_argument("--wait-timeout", type=int, default=240, help="Seconds to wait for endpoints")
    parser.add_argument("--image-tag", default="", help="Image tag used for the benchmark run")
    parser.add_argument("--git-commit", default="", help="Git commit for this run")
    parser.add_argument("--git-branch", default="", help="Git branch for this run")
    parser.add_argument("--compare", default="", help="Optional baseline JSON path for diff report")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
