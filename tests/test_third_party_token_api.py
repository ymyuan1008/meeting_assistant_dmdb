import hashlib
import time
import importlib
import pytest
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport


def build_header_token(app_id: str, app_secret: str, timestamp_ms: int) -> str:
    sign_str = f"{app_id}{app_secret}{timestamp_ms}"
    sign = hashlib.md5(sign_str.encode()).hexdigest()
    return f"appId-{app_id}#timestamp-{timestamp_ms}#sign-{sign}"


@pytest.mark.asyncio
async def test_generate_token_success(monkeypatch):
    # 配置环境变量，在模块导入前设置（模块在导入时读取这些值）
    monkeypatch.setenv("APP_ID", "aihear")
    monkeypatch.setenv("APP_SECRET", "z88zJsQ!rc4DOkMTKnfokU3fHOxFeZzoYvwGvHyG@r1")
    monkeypatch.setenv("JWT_SECRET", "test-third-party-jwt-secret")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("THIRD_PARTY_ACCESS_TOKEN_EXPIRE_MINUTES", "1")
    monkeypatch.setenv("THIRD_PARTY_TIMESTAMP_VALID_WINDOW", "300")

    # 重新导入路由模块以应用环境变量
    tp_module = importlib.import_module("router.third_party_token")
    importlib.reload(tp_module)

    app = FastAPI()
    app.include_router(tp_module.router)

    timestamp_ms = int(time.time() * 1000)
    header_token = build_header_token("aihear", "z88zJsQ!rc4DOkMTKnfokU3fHOxFeZzoYvwGvHyG@r1", timestamp_ms)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/third-party/token", headers={"token": header_token})

    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 200
    assert data["message"] == "成功"
    assert "access_token" in data["data"]
    assert data["data"]["token_type"] == "Bearer"
    assert data["data"]["scope"] == "api"


@pytest.mark.asyncio
async def test_invalid_signature(monkeypatch):
    monkeypatch.setenv("APP_ID", "aihear")
    monkeypatch.setenv("APP_SECRET", "correct-secret")
    monkeypatch.setenv("JWT_SECRET", "test-third-party-jwt-secret")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")

    tp_module = importlib.import_module("router.third_party_token")
    importlib.reload(tp_module)

    app = FastAPI()
    app.include_router(tp_module.router)

    timestamp_ms = int(time.time() * 1000)
    # 使用错误的secret生成签名，触发签名校验失败
    wrong_header_token = build_header_token("aihear", "wrong-secret", timestamp_ms)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/third-party/token", headers={"token": wrong_header_token})

    assert resp.status_code == 401
    data = resp.json()
    assert data["code"] == 401
    assert data["message"] == "无效的签名"
    assert data["data"] is None


@pytest.mark.asyncio
async def test_expired_request(monkeypatch):
    monkeypatch.setenv("APP_ID", "aihear")
    monkeypatch.setenv("APP_SECRET", "secret")
    monkeypatch.setenv("JWT_SECRET", "test-third-party-jwt-secret")
    monkeypatch.setenv("THIRD_PARTY_TIMESTAMP_VALID_WINDOW", "1")  # 1秒窗口，方便触发过期

    tp_module = importlib.import_module("router.third_party_token")
    importlib.reload(tp_module)

    app = FastAPI()
    app.include_router(tp_module.router)

    # 构造一个较早的时间戳（2秒前）
    timestamp_ms = int((time.time() - 2) * 1000)
    header_token = build_header_token("aihear", "secret", timestamp_ms)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/第三方/token")
        # 注意：路径应为英文，修正错误请求以验证正确路径
        assert resp.status_code == 404

    # 使用正确路径但时间过期
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/third-party/token", headers={"token": header_token})

    assert resp.status_code == 401
    data = resp.json()
    assert data["message"] == "请求已过期"
    assert data["data"] is None