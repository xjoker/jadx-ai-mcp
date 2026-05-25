"""
JADX MCP Server - Security Scan Tools

This module provides MCP tools for automated security scanning of decompiled
Android applications, checking for common vulnerability patterns including
hardcoded secrets, weak cryptography, insecure network configurations, and
dangerous API usage.

Author: jadx-ai-mcp contributors
License: See LICENSE file
"""

import re
import time
from typing import Optional
from src.server.logging_config import get_logger
from src.server.request_context import get_from_jadx_for_current_user as get_from_jadx

logger = get_logger("security_tools")

# ---------------------------------------------------------------------------
# Security rule definitions
# ---------------------------------------------------------------------------

SECURITY_RULES: dict[str, dict] = {
    "hardcoded_secrets": {
        "category": "secrets",
        "severity": "high",
        "patterns": [
            {"term": "password", "search_in": "code", "description": "Possible hardcoded password"},
            {"term": "secret", "search_in": "code", "description": "Possible hardcoded secret"},
            {"term": "api_key", "search_in": "code", "description": "Possible hardcoded API key"},
            {"term": "apikey", "search_in": "code", "description": "Possible hardcoded API key (no underscore)"},
            {"term": "Bearer ", "search_in": "code", "description": "Hardcoded Bearer token"},
            {"term": "-----BEGIN", "search_in": "code", "description": "Embedded private key/certificate"},
        ],
    },
    "insecure_crypto": {
        "category": "crypto",
        "severity": "high",
        "patterns": [
            {"term": "DES", "search_in": "class", "description": "Weak DES encryption"},
            {"term": "MD5", "search_in": "class", "description": "Weak MD5 hash"},
            {"term": "SHA1", "search_in": "class", "description": "Weak SHA-1 hash"},
            {"term": "ECB", "search_in": "code", "description": "Insecure ECB mode"},
            {"term": "AES/ECB", "search_in": "code", "description": "AES with insecure ECB mode"},
        ],
    },
    "insecure_network": {
        "category": "network",
        "severity": "medium",
        "patterns": [
            {"term": "http://", "search_in": "code", "description": "Cleartext HTTP communication"},
            {"term": "TrustManager", "search_in": "class", "description": "Custom TrustManager (potential SSL bypass)"},
            {"term": "AllowAllHostnameVerifier", "search_in": "class", "description": "Hostname verification bypass"},
            {"term": "ALLOW_ALL_HOSTNAME_VERIFIER", "search_in": "code", "description": "Hostname verification disabled"},
            {"term": "setHostnameVerifier", "search_in": "code", "description": "Custom hostname verification"},
        ],
    },
    "dangerous_apis": {
        "category": "permissions",
        "severity": "medium",
        "patterns": [
            {"term": "Runtime.exec", "search_in": "code", "description": "Command execution"},
            {"term": "ProcessBuilder", "search_in": "class", "description": "Process creation"},
            {"term": "DexClassLoader", "search_in": "class", "description": "Dynamic code loading"},
            {"term": "PathClassLoader", "search_in": "class", "description": "Dynamic code loading"},
            {"term": "WebView", "search_in": "class", "description": "WebView usage (check JS bridge)"},
            {"term": "addJavascriptInterface", "search_in": "code", "description": "WebView JS bridge (potential RCE)"},
            {"term": "setJavaScriptEnabled", "search_in": "code", "description": "WebView JavaScript enabled"},
        ],
    },
    "data_leakage": {
        "category": "secrets",
        "severity": "medium",
        "patterns": [
            {"term": "Log.d", "search_in": "code", "description": "Debug logging (potential data leak)"},
            {"term": "Log.v", "search_in": "code", "description": "Verbose logging (potential data leak)"},
            {"term": "SharedPreferences", "search_in": "class", "description": "Local storage (check for sensitive data)"},
            {"term": "MODE_WORLD_READABLE", "search_in": "code", "description": "World-readable file"},
            {"term": "MODE_WORLD_WRITEABLE", "search_in": "code", "description": "World-writeable file"},
        ],
    },
}

# Mapping from rule_id to remediation recommendations
RECOMMENDATIONS: dict[str, str] = {
    "hardcoded_secrets": (
        "Move secrets to environment variables, Android Keystore, or a secure "
        "secrets manager. Never embed credentials in source code or resources."
    ),
    "insecure_crypto": (
        "Replace DES with AES-256, MD5/SHA-1 with SHA-256+, and ECB mode with "
        "CBC or GCM. Use Android Keystore for key management."
    ),
    "insecure_network": (
        "Enforce HTTPS for all connections. Avoid custom TrustManagers that skip "
        "certificate validation. Use certificate pinning for sensitive endpoints."
    ),
    "dangerous_apis": (
        "Audit all dynamic code loading and command execution for user-controlled input. "
        "Restrict WebView JS bridges to trusted content. Validate all IPC inputs."
    ),
    "data_leakage": (
        "Remove debug/verbose logging in release builds. Use EncryptedSharedPreferences "
        "for sensitive data. Never use MODE_WORLD_READABLE/WRITEABLE."
    ),
}

# Valid scan_type values and their matching categories
SCAN_TYPES: dict[str, list[str] | None] = {
    "full": None,  # None means all categories
    "secrets": ["secrets"],
    "crypto": ["crypto"],
    "network": ["network"],
    "permissions": ["permissions"],
}


def filter_rules(scan_type: str) -> dict[str, dict]:
    """Return only rules matching the requested scan_type."""
    allowed_categories = SCAN_TYPES.get(scan_type)
    if allowed_categories is None:
        # "full" or unknown -> return all
        return SECURITY_RULES

    return {
        rule_id: rule
        for rule_id, rule in SECURITY_RULES.items()
        if rule["category"] in allowed_categories
    }


def _infer_match_context(term: str, snippet: str, class_name: str) -> tuple[str, str]:
    """
    Infer the context of a pattern match using heuristics.

    Returns:
        A tuple of (match_context, confidence) where match_context is one of:
        'string_literal', 'method_name', 'class_name', 'field_name', 'comment', 'unknown'
        and confidence is 'high' or 'low'.
    """
    if not snippet:
        # No snippet available — fall back to class name heuristics
        term_lower = term.lower()
        class_lower = class_name.lower()
        if term_lower in class_lower:
            return "class_name", "low"
        return "unknown", "low"

    # Check if the term appears inside a string literal (surrounded by quotes)
    # Pattern: term is inside "..." or '...' (within 60 chars on each side)
    string_literal_pattern = re.compile(
        r'(?:"[^"]{0,200}' + re.escape(term) + r'[^"]{0,200}"'
        r"|'[^']{0,200}" + re.escape(term) + r"[^']{0,200}')",
        re.IGNORECASE,
    )
    if string_literal_pattern.search(snippet):
        return "string_literal", "high"

    # Check if term appears in a comment (// or /* ... */)
    comment_pattern = re.compile(
        r'(?://[^\n]*' + re.escape(term) + r'|/\*[^*]*' + re.escape(term) + r')',
        re.IGNORECASE,
    )
    if comment_pattern.search(snippet):
        return "comment", "low"

    # Check if the term is part of a method call / method name
    # Heuristic: term is followed by '(' possibly with spaces, or preceded by '.'
    method_pattern = re.compile(
        r'(?:\.' + re.escape(term) + r'\s*\(|(?:void|int|String|boolean|byte|long)\s+' + re.escape(term) + r'\s*\()',
        re.IGNORECASE,
    )
    if method_pattern.search(snippet):
        return "method_name", "low"

    # Check if term appears in a field/variable assignment (= "value" pattern without quotes around term)
    field_assign_pattern = re.compile(
        r'(?:private|public|protected|static|final)\s+\S+\s+' + re.escape(term) + r'\s*[=;]',
        re.IGNORECASE,
    )
    if field_assign_pattern.search(snippet):
        return "field_name", "low"

    # Check class name for term presence
    if term.lower() in class_name.lower():
        return "class_name", "low"

    # Default: unknown, medium confidence
    return "unknown", "low"


def _extract_matches(search_result: dict) -> list[dict[str, str]]:
    """Extract class_name + snippet pairs from a search-classes-by-keyword response."""
    matches: list[dict[str, str]] = []
    classes = search_result.get("classes", search_result.get("results", []))
    for item in classes:
        if isinstance(item, dict):
            matches.append({
                "class_name": item.get("class_name", item.get("name", "")),
                "snippet": item.get("snippet", item.get("match", "")),
            })
        elif isinstance(item, str):
            matches.append({"class_name": item, "snippet": ""})
    return matches


# ---------------------------------------------------------------------------
# Main scan function
# ---------------------------------------------------------------------------

async def _run_security_scan(
    scan_type: str = "full",
    package: str = "",
    instance_id: Optional[str] = None,
) -> dict:
    """
    Run an automated security scan against the loaded APK/JAR using
    predefined vulnerability patterns.
    """
    start_time = time.monotonic()
    logger.info(f"run_security_scan: type={scan_type}, package={package!r}")

    # Validate scan_type
    if scan_type not in SCAN_TYPES:
        return {
            "error": "INVALID_SCAN_TYPE",
            "message": f"Invalid scan_type '{scan_type}'. Valid values: {list(SCAN_TYPES.keys())}",
        }

    # Check decompile status for code search availability
    decompile_status = await get_from_jadx("decompile-status", instance_id=instance_id)
    cached_percentage = 0.0
    if isinstance(decompile_status, dict):
        cached_percentage = decompile_status.get("cached_percentage", 0.0)

    code_search_available = cached_percentage >= 20.0

    # Get filtered rules
    rules = filter_rules(scan_type)

    findings: list[dict] = []
    skipped_rules: list[dict] = []

    for rule_id, rule in rules.items():
        rule_matches: list[dict[str, str]] = []
        rule_skipped_patterns: list[str] = []

        for pattern in rule["patterns"]:
            search_in = pattern["search_in"]

            # Skip code searches when cache is insufficient
            if search_in == "code" and not code_search_available:
                rule_skipped_patterns.append(pattern["term"])
                continue

            # Build search params
            params: dict = {
                "search_term": pattern["term"],
                "search_in": search_in,
                "count": 10,
            }
            if package:
                params["package"] = package

            try:
                result = await get_from_jadx(
                    "search-classes-by-keyword", params, instance_id=instance_id
                )
            except Exception:
                logger.warning(
                    f"run_security_scan: search failed for term={pattern['term']!r}",
                    exc_info=True,
                )
                continue

            if isinstance(result, dict) and "error" not in result:
                matches = _extract_matches(result)
                if matches:
                    # Annotate each match with context and confidence
                    annotated: list[dict[str, str]] = []
                    for m in matches:
                        ctx, conf = _infer_match_context(
                            pattern["term"], m.get("snippet", ""), m.get("class_name", "")
                        )
                        annotated.append({
                            **m,
                            "matched_term": pattern["term"],
                            "match_context": ctx,
                            "confidence": conf,
                        })
                    rule_matches.extend(annotated)

        # Record skipped patterns at rule level
        if rule_skipped_patterns:
            skipped_rules.append({
                "rule_id": rule_id,
                "reason": (
                    f"Code search skipped (cached_percentage={cached_percentage:.1f}% < 20%). "
                    f"Skipped patterns: {', '.join(rule_skipped_patterns)}"
                ),
            })

        if rule_matches:
            high_conf = [m for m in rule_matches if m.get("confidence") == "high"]
            low_conf = [m for m in rule_matches if m.get("confidence") != "high"]
            findings.append({
                "rule_id": rule_id,
                "category": rule["category"],
                "severity": rule["severity"],
                "description": "; ".join(p["description"] for p in rule["patterns"]),
                "matches": rule_matches[:20],  # cap displayed matches
                "match_count": len(rule_matches),
                "high_confidence_count": len(high_conf),
                "low_confidence_count": len(low_conf),
                "recommendation": RECOMMENDATIONS.get(rule_id, "Review the matched code for security issues."),
            })

    # Build summary
    high_count = sum(1 for f in findings if f["severity"] == "high")
    medium_count = sum(1 for f in findings if f["severity"] == "medium")
    low_count = sum(1 for f in findings if f["severity"] == "low")
    total_high_conf = sum(f.get("high_confidence_count", 0) for f in findings)
    total_low_conf = sum(f.get("low_confidence_count", 0) for f in findings)

    elapsed = round(time.monotonic() - start_time, 2)

    result = {
        "scan_type": scan_type,
        "scan_time_seconds": elapsed,
        "summary": {
            "total_findings": len(findings),
            "high_severity": high_count,
            "medium_severity": medium_count,
            "low_severity": low_count,
            "high_confidence_count": total_high_conf,
            "low_confidence_count": total_low_conf,
        },
        "findings": findings,
        "skipped_rules": skipped_rules,
        "scan_coverage": {
            "code_search_available": code_search_available,
            "cached_percentage": cached_percentage,
        },
    }

    logger.info(
        f"run_security_scan: completed in {elapsed}s — "
        f"findings={len(findings)}, skipped={len(skipped_rules)}"
    )
    return result


# ---------------------------------------------------------------------------
# MCP registration
# ---------------------------------------------------------------------------

def register_security_tools(mcp, with_busy_check):
    """Register security scan tools with the MCP server."""

    @mcp.tool()
    @with_busy_check
    async def run_security_scan(
        scan_type: str = "full",
        package: str = "",
        instance_id: Optional[str] = None,
    ) -> dict:
        """Automated security scan for hardcoded secrets, weak crypto, insecure network, dangerous APIs.

        Args:
            scan_type: full|secrets|crypto|network|permissions. package: Scope filter.
            instance_id: Target JADX instance name.
        Returns:
            dict: {summary: {total_findings, high_severity, medium_severity}, findings: [{rule_id, severity, matches}]}
        """
        return await _run_security_scan(
            scan_type=scan_type, package=package, instance_id=instance_id
        )

    logger.info("Security tools registered: run_security_scan")
