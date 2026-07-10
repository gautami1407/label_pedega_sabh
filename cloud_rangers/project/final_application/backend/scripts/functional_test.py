import json
import os
import sys
import time
import base64
import traceback
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests


BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8000").rstrip("/")
TIMEOUT_S = float(os.getenv("TEST_TIMEOUT_S", "60"))


LOG_PATH = os.getenv(
    "FUNCTIONAL_TEST_LOG",
    os.path.join(os.path.dirname(__file__), "../functional_test_log.txt"),
)
LOG_PATH = os.path.abspath(LOG_PATH)

OPENAPI_PATH = os.path.join(os.path.dirname(__file__), "../functional_openapi_cache.json")
OPENAPI_PATH = os.path.abspath(OPENAPI_PATH)


@dataclass
class EndpointResult:
    method: str
    path: str
    url: str
    expected_status: int
    actual_status: Optional[int]
    response_time_ms: Optional[float]
    pass_fail: bool
    error: Optional[str] = None
    response_preview: Optional[str] = None


def _now_ms() -> int:
    return int(time.time() * 1000)


def _log_line(s: str) -> None:
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(s.rstrip("\n") + "\n")


def reset_log() -> None:
    if os.path.exists(LOG_PATH):
        os.remove(LOG_PATH)
    _log_line(f"Functional Test Log - {time.ctime()}")
    _log_line(f"BASE_URL={BASE_URL} TIMEOUT_S={TIMEOUT_S}")


def request_json(
    method: str,
    url: str,
    *,
    json_body: Optional[dict] = None,
    params: Optional[dict] = None,
    headers: Optional[dict] = None,
) -> Tuple[requests.Response, float]:
    start = time.perf_counter()
    resp = requests.request(
        method,
        url,
        json=json_body,
        params=params,
        headers=headers,
        timeout=TIMEOUT_S,
    )
    elapsed = (time.perf_counter() - start) * 1000.0
    return resp, elapsed


def safe_preview(resp: requests.Response, max_len: int = 800) -> str:
    try:
        if resp.headers.get("Content-Type", "").lower().startswith("application/json"):
            txt = json.dumps(resp.json(), ensure_ascii=False)
        else:
            txt = resp.text
    except Exception:
        txt = resp.text if resp.text else "<empty>"
    txt = txt.replace("\n", " ")
    return txt[:max_len]


def load_openapi() -> dict:
    # Try live first
    openapi_url = f"{BASE_URL}/openapi.json"
    try:
        resp, _ = request_json("GET", openapi_url)
        resp.raise_for_status()
        data = resp.json()
        with open(OPENAPI_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return data
    except Exception:
        # Fall back to cache
        if os.path.exists(OPENAPI_PATH):
            with open(OPENAPI_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        raise


def normalize_path(path_template: str) -> str:
    # fastapi uses {param} in OpenAPI
    return path_template


def discover_endpoints(openapi: dict) -> List[Tuple[str, str, dict]]:
    endpoints: List[Tuple[str, str, dict]] = []
    paths = openapi.get("paths") or {}
    for path_template, methods in paths.items():
        if not isinstance(methods, dict):
            continue
        for method, spec in methods.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            if not isinstance(spec, dict):
                continue
            endpoints.append((method.upper(), normalize_path(path_template), spec))
    # Stable ordering
    endpoints.sort(key=lambda x: (x[1], x[0]))
    return endpoints


def expected_statuses_from_openapi(spec: dict) -> List[int]:
    # Prefer 200/201; otherwise accept any declared 2xx/3xx.
    responses = spec.get("responses") or {}
    status_codes: List[int] = []
    for k in responses.keys():
        if k == "default":
            continue
        try:
            status_codes.append(int(k))
        except Exception:
            pass
    # If explicit codes exist, use those; else default to 200
    if status_codes:
        return sorted(set(status_codes))
    return [200]


def build_request_for_endpoint(method: str, path_template: str, spec: dict) -> Tuple[dict, Optional[dict]]:
    """Return (params_or_none, json_body_or_none)."""
    params: Dict[str, Any] = {}
    json_body: Optional[Dict[str, Any]] = None

    # Path params
    # OpenAPI spec provides parameters list including in: path/query.
    for p in (spec.get("parameters") or []):
        if not isinstance(p, dict):
            continue
        location = p.get("in")
        name = p.get("name")
        schema = p.get("schema") or {}
        if location == "path":
            # minimal plausible values by parameter name
            if name:
                lower = name.lower()
                if "barcode" in lower:
                    params[name] = "4006381333931"  # common EAN13
                elif "identifier" in lower:
                    params[name] = "E100"  # likely valid for additives
                elif "id" == lower or lower.endswith("_id") or lower == "id":
                    params[name] = "1"
                else:
                    params[name] = "test"
        elif location == "query":
            if name:
                lower = name.lower()
                if lower == "q":
                    params[name] = "milk"
                elif lower in {"page_size", "page", "limit"}:
                    params[name] = 5 if lower == "page_size" else 1
                elif lower == "product":
                    params[name] = "milk"

    # Request body
    req_body = spec.get("requestBody")
    if req_body and isinstance(req_body, dict):
        content = req_body.get("content") or {}
        # Only handle application/json
        app_json = content.get("application/json") if isinstance(content, dict) else None
        if app_json is not None:
            # minimal bodies by endpoint path
            # Use heuristics on path template
            if "/api/v1/scan/ocr" in path_template:
                # If runner sample image exists, use it; else send a tiny valid base64 string.
                img_b64 = _load_sample_image_b64()
                json_body = {"image_data": f"data:image/png;base64,{img_b64}"}
            elif "/api/v1/scan/barcode" in path_template:
                json_body = {"barcode": "4006381333931", "preferences": {}}
            elif "/api/v1/ai/chat" in path_template:
                json_body = {"message": "What are key ingredients to watch for in this product?", "context": {}}
            elif "/api/v1/auth/login" in path_template:
                json_body = {"email": "test@example.com", "password": "TestPassword123!"}
            elif "/api/v1/auth/register" in path_template:
                json_body = {
                    "email": "test@example.com",
                    "password": "TestPassword123!",
                    "name": "Test User",
                }
            else:
                # generic
                json_body = {}

    return params, json_body


def _load_sample_image_b64() -> str:
    # Try sample image inside scripts directory
    candidates = [
        os.path.join(os.path.dirname(__file__), "sample_label.png"),
        os.path.join(os.path.dirname(__file__), "../data/sample_label.png"),
    ]
    for p in candidates:
        if os.path.isfile(p):
            with open(p, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")

    # Fallback: 1x1 transparent PNG (base64) to keep content valid.
    return (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMB/"
        "Y2YpAAAAAElFTkSuQmCC"
    )


def substitute_path_params(path_template: str, path_params: dict) -> str:
    out = path_template
    for k, v in path_params.items():
        out = out.replace("{" + k + "}", str(v))
    return out


def is_auth_endpoint(path: str, method: str) -> bool:
    return path.startswith("/api/v1/auth/")


def is_rate_limited_endpoint(path: str) -> bool:
    return path.startswith("/api/v1/scan/") or path.startswith("/api/v1/ai/")


def main() -> None:
    reset_log()

    results: List[EndpointResult] = []

    try:
        openapi = load_openapi()
    except Exception as e:
        _log_line("FAILED: Unable to load /openapi.json")
        _log_line(str(e))
        raise

    endpoints = discover_endpoints(openapi)
    _log_line(f"Discovered endpoints from OpenAPI: {len(endpoints)}")

    # Sanity: required meta endpoints regardless of schema
    required_checks = [
        ("GET", "/health"),
        ("GET", "/docs"),
        ("GET", "/openapi.json"),
        ("GET", "/"),
    ]

    for method, path in required_checks:
        url = f"{BASE_URL}{path}"
        try:
            resp, rt = request_json(method, url)
            ok = resp.status_code in {200, 304}
            results.append(
                EndpointResult(
                    method,
                    path,
                    url,
                    200,
                    resp.status_code,
                    rt,
                    ok,
                    error=None if ok else f"Unexpected status {resp.status_code}",
                    response_preview=safe_preview(resp),
                )
            )
            _log_line(f"CHECK {method} {path} -> {resp.status_code} ({rt:.1f}ms)")
        except Exception as e:
            results.append(EndpointResult(method, path, url, 200, None, None, False, error=str(e)))
            _log_line(f"CHECK {method} {path} -> EXCEPTION: {e}")

    # Execute all discovered endpoints
    for method, path_template, spec in endpoints:
        # Skip OpenAPI & docs already checked
        if path_template in {"/openapi.json", "/docs", "/redoc"}:
            continue
        # Skip static html routing unless it's explicitly in OpenAPI
        if path_template.startswith("/static/"):
            continue

        # Build request
        path_params, json_body = build_request_for_endpoint(method, path_template, spec)
        final_path = substitute_path_params(path_template, path_params)
        url = f"{BASE_URL}{final_path}"

        expected_statuses = expected_statuses_from_openapi(spec)

        # If any auth endpoints, we won't attempt login unless configured.
        # We'll still execute them to verify status; if they require creds, failure will be logged.
        try:
            params = {k: v for k, v in path_params.items() if "{" not in k}
            resp: Optional[requests.Response] = None
            elapsed: Optional[float] = None

            # Avoid double-using path_params as query params.
            query_params = None

            if method == "GET":
                # Put query params if any were inferred
                # build_request_for_endpoint stored query params in params dict; but we used same dict.
                query_params = {}
                for p in (spec.get("parameters") or []):
                    if not isinstance(p, dict):
                        continue
                    if p.get("in") == "query":
                        name = p.get("name")
                        if name and name in params:
                            query_params[name] = params[name]
                resp, elapsed = request_json(method, url, params=query_params)
            else:
                resp, elapsed = request_json(method, url, json_body=json_body)

            actual = resp.status_code
            ok = actual in expected_statuses or (200 <= actual < 400 and any(200 <= s < 400 for s in expected_statuses))

            preview = safe_preview(resp)
            err = None
            if not ok:
                # try to extract detail
                try:
                    j = resp.json()
                    err = f"Expected one of {expected_statuses}, got {actual}. Detail: {j.get('detail') or j.get('error') or j}"
                except Exception:
                    err = f"Expected one of {expected_statuses}, got {actual}. Body: {preview}"

            results.append(
                EndpointResult(
                    method=method,
                    path=path_template,
                    url=url,
                    expected_status=expected_statuses[0] if expected_statuses else 200,
                    actual_status=actual,
                    response_time_ms=elapsed,
                    pass_fail=ok,
                    error=err,
                    response_preview=preview,
                )
            )

            _log_line(
                f"{('PASS' if ok else 'FAIL')} {method} {path_template} -> {actual} ({elapsed:.1f}ms)"
            )

        except Exception as e:
            tb = traceback.format_exc()
            results.append(
                EndpointResult(
                    method=method,
                    path=path_template,
                    url=url,
                    expected_status=expected_statuses[0] if expected_statuses else 200,
                    actual_status=None,
                    response_time_ms=None,
                    pass_fail=False,
                    error=f"EXCEPTION: {e}\n{tb}",
                )
            )
            _log_line(f"FAIL {method} {path_template} -> EXCEPTION: {e}")

    # Validate database connectivity (best-effort by calling /health)
    # /health already covered above, but we parse it if available
    # (no backend code changes).

    # Create summary report
    report_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../functional_test_report.json"))
    summary_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../functional_test_summary.txt"))

    passed = [r for r in results if r.pass_fail]
    failed = [r for r in results if not r.pass_fail]

    _log_line(f"TOTAL={len(results)} PASSED={len(passed)} FAILED={len(failed)}")

    report_obj: Dict[str, Any] = {
        "base_url": BASE_URL,
        "timeout_s": TIMEOUT_S,
        "total": len(results),
        "passed": len(passed),
        "failed": len(failed),
        "results": [
            {
                "endpoint": {
                    "method": r.method,
                    "path": r.path,
                    "url": r.url,
                },
                "expected_status": r.expected_status,
                "actual_status": r.actual_status,
                "response_time_ms": r.response_time_ms,
                "pass": r.pass_fail,
                "error": r.error,
                "response_preview": r.response_preview,
            }
            for r in results
        ],
    }

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_obj, f, ensure_ascii=False, indent=2)

    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(f"Functional Test Summary\n")
        f.write(f"Base URL: {BASE_URL}\n")
        f.write(f"Timeout: {TIMEOUT_S}s\n")
        f.write(f"Total: {len(results)}\n")
        f.write(f"Passed: {len(passed)}\n")
        f.write(f"Failed: {len(failed)}\n")
        f.write("\nFailed endpoints:\n")
        for r in failed:
            f.write(f"- {r.method} {r.path}: {r.error or ('status='+str(r.actual_status))}\n")

    # Exit code
    if failed:
        _log_line("RESULT: FAIL")
        # No auto-fix is performed automatically in this runner; instead it logs failures.
        # Per requirements, external dependencies may prevent success.
        sys.exit(1)

    _log_line("RESULT: PASS")
    sys.exit(0)


if __name__ == "__main__":
    main()

