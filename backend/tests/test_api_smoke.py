"""API 冒烟集成测试：健康检查、注册登录、账号数据导出/用量/注销、鉴权。

需要可用的 PostgreSQL；数据库不可用时自动跳过，不影响本地纯单元测试。
"""
import os
import random
import unittest

try:
    from fastapi.testclient import TestClient
    from main import app
except Exception as exc:  # pragma: no cover - 依赖缺失时跳过
    TestClient = None
    app = None


@unittest.skipUnless(TestClient and app, "FastAPI 或 main 不可用")
class ApiSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.client = TestClient(app)
            cls.client.__enter__()
        except Exception as exc:
            raise unittest.SkipTest(f"数据库不可用，跳过 API 集成测试: {exc}")

    @classmethod
    def tearDownClass(cls):
        try:
            cls.client.__exit__(None, None, None)
        except Exception:
            pass

    def test_health(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "healthy")

    def test_account_export_requires_auth(self):
        resp = self.client.get("/api/account/export")
        self.assertEqual(resp.status_code, 401)

    def test_register_login_export_delete_flow(self):
        phone = "159" + "".join(str(random.randint(0, 9)) for _ in range(8))
        code_resp = self.client.post("/api/auth/send-code", json={"phone": phone})
        self.assertEqual(code_resp.status_code, 200)
        debug_code = code_resp.json()["debug_code"]

        reg = self.client.post(
            "/api/auth/register",
            json={"phone": phone, "code": debug_code, "password": "test123456"},
        )
        self.assertEqual(reg.status_code, 200)
        token = reg.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        me = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["phone"], phone)

        export = self.client.get("/api/account/export", headers=headers)
        self.assertEqual(export.status_code, 200)
        self.assertEqual(export.json()["user"]["phone"], phone)

        usage = self.client.get("/api/account/usage/summary", headers=headers)
        self.assertEqual(usage.status_code, 200)
        self.assertIn("summary", usage.json())

        delete = self.client.delete("/api/account/delete", headers=headers)
        self.assertEqual(delete.status_code, 200)
        self.assertTrue(delete.json()["deleted_user"])
    def test_login_lockout_after_failures(self):
        phone = "159" + "".join(str(random.randint(0, 9)) for _ in range(8))
        code_resp = self.client.post("/api/auth/send-code", json={"phone": phone})
        debug_code = code_resp.json()["debug_code"]
        reg = self.client.post(
            "/api/auth/register",
            json={"phone": phone, "code": debug_code, "password": "test123456"},
        )
        self.assertEqual(reg.status_code, 200)
        token = reg.json()["token"]

        for _ in range(5):
            bad = self.client.post(
                "/api/auth/login",
                json={"phone": phone, "password": "wrong-pass"},
            )
            self.assertEqual(bad.status_code, 400)

        locked = self.client.post(
            "/api/auth/login",
            json={"phone": phone, "password": "test123456"},
        )
        self.assertEqual(locked.status_code, 429)

        self.client.delete(
            "/api/account/delete",
            headers={"Authorization": f"Bearer {token}"},
        )