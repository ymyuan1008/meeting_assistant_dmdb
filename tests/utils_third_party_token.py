"""
第三方接口请求工具（tests环境）

用途：生成请求头 `token`，用于访问 `/api/v1/third-party/token` 接口。

格式：
    token: appId-{appId}#timestamp-{timestampMs}#sign-{md5}

签名计算规则：
    md5( f"{app_id}{app_secret}{timestamp_ms}" )

环境变量（可选）：
    - APP_ID
    - APP_SECRET

示例：
    builder = ThirdPartyTokenBuilder()
    headers = builder.headers()  # 默认读取环境变量并用当前毫秒时间戳
    # async client 请求：await ac.get("/api/v1/third-party/token", headers=headers)
"""

from __future__ import annotations

import os
import time
import hashlib
from typing import Optional, Dict


class ThirdPartyTokenBuilder:
    def __init__(self, app_id: Optional[str] = None, app_secret: Optional[str] = None) -> None:
        self.app_id = app_id or os.getenv("APP_ID", "")
        self.app_secret = app_secret or os.getenv("APP_SECRET", "")

    @staticmethod
    def now_ms() -> int:
        """当前时间戳（毫秒）。"""
        return int(time.time() * 1000)

    @staticmethod
    def sign(app_id: str, app_secret: str, timestamp_ms: int) -> str:
        """按服务端规则生成签名（md5）。"""
        raw = f"{app_id}{app_secret}{timestamp_ms}"
        return hashlib.md5(raw.encode()).hexdigest()

    def build(self, timestamp_ms: Optional[int] = None) -> str:
        """
        生成 `token` 字符串。

        参数：
            - timestamp_ms: 指定毫秒时间戳，不传则使用当前时间
        返回：
            - token 字符串，例如："appId-xxx#timestamp-1710000000000#sign-abcdef..."
        """
        if not self.app_id or not self.app_secret:
            raise ValueError("APP_ID/APP_SECRET 不能为空（可通过环境变量或构造参数传入）")

        ts = timestamp_ms if timestamp_ms is not None else self.now_ms()
        sig = self.sign(self.app_id, self.app_secret, ts)
        return f"appId-{self.app_id}#timestamp-{ts}#sign-{sig}"

    def headers(self, timestamp_ms: Optional[int] = None) -> Dict[str, str]:
        """生成可直接用于请求的 headers 字典。"""
        return {"token": self.build(timestamp_ms)}


def build_token_header(app_id: Optional[str] = None, app_secret: Optional[str] = None, timestamp_ms: Optional[int] = None) -> str:
    """
    便捷函数：直接生成 `token` 字符串。
    """
    return ThirdPartyTokenBuilder(app_id=app_id, app_secret=app_secret).build(timestamp_ms)


def build_headers(app_id: Optional[str] = None, app_secret: Optional[str] = None, timestamp_ms: Optional[int] = None) -> Dict[str, str]:
    """
    便捷函数：直接生成包含 `token` 的 headers。
    """
    return ThirdPartyTokenBuilder(app_id=app_id, app_secret=app_secret).headers(timestamp_ms)


# -----------------------------
# CLI：在其他服务器直接使用并打印信息
# -----------------------------
def _mask_secret(s: str) -> str:
    if len(s) <= 6:
        return "*" * len(s)
    return s[:3] + "*" * (len(s) - 6) + s[-3:]


def _join_url(base_url: str, path: str) -> str:
    base = base_url.rstrip('/')
    p = path if path.startswith('/') else f'/{path}'
    return base + p


def main() -> None:
    import argparse
    import json
    import datetime
    import urllib.request
    import urllib.error

    parser = argparse.ArgumentParser(description="第三方接口请求工具：生成并打印 token 请求头")
    parser.add_argument("--app-id", dest="app_id", type=str, default=os.getenv("APP_ID", ""), help="应用ID（默认读取环境变量 APP_ID）")
    parser.add_argument("--app-secret", dest="app_secret", type=str, default=os.getenv("APP_SECRET", ""), help="应用Secret（默认读取环境变量 APP_SECRET）")
    parser.add_argument("--timestamp-ms", dest="timestamp_ms", type=int, default=None, help="指定毫秒时间戳（默认使用当前时间）")
    parser.add_argument("--offset-sec", dest="offset_sec", type=int, default=0, help="在当前时间基础上偏移秒数（可为负数，用于构造过期请求）")
    parser.add_argument("--base-url", dest="base_url", type=str, default="http://localhost:8000", help="服务 Base URL，例如 http://127.0.0.1:8000")
    parser.add_argument("--path", dest="path", type=str, default="/api/v1/third-party/token", help="接口路径，默认 /api/v1/third-party/token")
    parser.add_argument("--request", dest="do_request", action="store_true", help="实际发送请求并打印响应")
    parser.add_argument("--print-iwr", dest="print_iwr", action="store_true", help="同时打印 PowerShell Invoke-WebRequest 命令")
    args = parser.parse_args()

    print("==== 第三方 Token 请求工具 ====")

    if not args.app_id or not args.app_secret:
        print("[ERROR] APP_ID/APP_SECRET 未提供（可通过参数或环境变量传入）")
        raise SystemExit(1)

    # 计算时间戳
    base_ts = ThirdPartyTokenBuilder.now_ms()
    ts = args.timestamp_ms if args.timestamp_ms is not None else base_ts + args.offset_sec * 1000

    # 打印输入信息
    print(f"app_id        : {args.app_id}")
    print(f"app_secret    : {_mask_secret(args.app_secret)}")
    iso_time = datetime.datetime.fromtimestamp(ts / 1000.0).isoformat()
    print(f"timestamp_ms  : {ts} ({iso_time})")

    # 计算签名及 token
    sig = ThirdPartyTokenBuilder.sign(args.app_id, args.app_secret, ts)
    token_str = f"appId-{args.app_id}#timestamp-{ts}#sign-{sig}"
    headers = {"token": token_str}

    # 打印签名与头
    print(f"sign_raw      : {args.app_id}{args.app_secret}{ts}")
    print(f"sign_md5      : {sig}")
    print(f"header_token  : {token_str}")
    print(f"headers_json  : {json.dumps(headers, ensure_ascii=False)}")

    # 打印 curl 与 PowerShell 命令
    url = _join_url(args.base_url, args.path)
    curl_cmd = f"curl -v -H \"token: {token_str}\" \"{url}\""
    print("\n示例 curl：")
    print(curl_cmd)

    if args.print_iwr:
        iwr_cmd = f"iwr -Method GET -Uri \"{url}\" -Headers @{{ token = '{token_str}' }}"
        print("\n示例 PowerShell Invoke-WebRequest：")
        print(iwr_cmd)

    # 选择性发起请求并打印响应
    if args.do_request:
        print("\n[REQUEST] 发送 GET 请求...")
        req = urllib.request.Request(url=url, method="GET")
        req.add_header("token", token_str)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                status = resp.getcode()
                body = resp.read()
                # 尝试 JSON 输出
                try:
                    body_json = json.loads(body.decode("utf-8", errors="ignore"))
                    body_out = json.dumps(body_json, ensure_ascii=False, indent=2)
                except Exception:
                    body_out = body[:1000].decode("utf-8", errors="ignore")
                print(f"[RESPONSE] status={status}\n{body_out}")
        except urllib.error.HTTPError as e:
            print(f"[HTTPError] status={e.code}, reason={e.reason}")
            try:
                err_body = e.read().decode("utf-8", errors="ignore")
                print(err_body)
            except Exception:
                pass
            raise SystemExit(1)
        except urllib.error.URLError as e:
            print(f"[URLError] {e.reason}")
            raise SystemExit(1)


if __name__ == "__main__":
    main()