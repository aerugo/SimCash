"""Tests for admin / user management."""
from __future__ import annotations

import os
import pytest
from unittest.mock import MagicMock, patch


class FakeDocSnapshot:
    def __init__(self, data=None):
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        return self._data


class FakeCollection:
    def __init__(self):
        self._docs: dict[str, dict] = {}

    def document(self, doc_id: str):
        return FakeDocRef(self, doc_id)

    def stream(self):
        return [FakeDocSnapshot(d) for d in self._docs.values()]


class FakeDocRef:
    def __init__(self, coll: FakeCollection, doc_id: str):
        self._coll = coll
        self._id = doc_id

    def get(self):
        data = self._coll._docs.get(self._id)
        return FakeDocSnapshot(data)

    def set(self, data: dict, merge: bool = False):
        if merge and self._id in self._coll._docs:
            self._coll._docs[self._id].update(data)
        else:
            self._coll._docs[self._id] = dict(data)

    def delete(self):
        self._coll._docs.pop(self._id, None)


class FakeFirestoreClient:
    def __init__(self):
        self._collections: dict[str, FakeCollection] = {}

    def collection(self, name: str):
        if name not in self._collections:
            self._collections[name] = FakeCollection()
        return self._collections[name]


@pytest.fixture(autouse=True)
def mock_firestore():
    fake_db = FakeFirestoreClient()
    import app.admin as admin_mod
    old_db = admin_mod._db
    old_get = admin_mod._get_db
    admin_mod._db = fake_db
    admin_mod._get_db = lambda: fake_db
    yield fake_db
    admin_mod._db = old_db
    admin_mod._get_db = old_get


@pytest.fixture
def user_mgr():
    from app.admin import UserManager
    return UserManager()


class TestIsAllowed:
    def test_sensestack_domain_allowed(self, user_mgr):
        with patch("app.admin.config.is_auth_disabled", return_value=False):
            assert user_mgr.is_allowed("anyone@sensestack.xyz") is True

    def test_unknown_email_not_allowed(self, user_mgr):
        with patch("app.admin.config.is_auth_disabled", return_value=False):
            assert user_mgr.is_allowed("stranger@gmail.com") is False

    def test_invited_email_allowed(self, user_mgr):
        with patch("app.admin.config.is_auth_disabled", return_value=False):
            user_mgr.invite_user("invited@test.com", "admin@sensestack.xyz")
            assert user_mgr.is_allowed("invited@test.com") is True

    def test_auth_disabled_always_allowed(self, user_mgr):
        with patch("app.admin.config.is_auth_disabled", return_value=True):
            assert user_mgr.is_allowed("anyone@anywhere.com") is True


class TestIsAdmin:
    def test_non_admin(self, user_mgr):
        with patch("app.admin.config.is_auth_disabled", return_value=False):
            assert user_mgr.is_admin("user@test.com") is False

    def test_seeded_admin(self, user_mgr):
        with patch("app.admin.config.is_auth_disabled", return_value=False):
            user_mgr.seed_admin("admin@sensestack.xyz")
            assert user_mgr.is_admin("admin@sensestack.xyz") is True

    def test_auth_disabled_always_admin(self, user_mgr):
        with patch("app.admin.config.is_auth_disabled", return_value=True):
            assert user_mgr.is_admin("anyone@anywhere.com") is True


class TestInviteListRevoke:
    def test_invite_list_revoke_cycle(self, user_mgr):
        with patch("app.admin.config.is_auth_disabled", return_value=False):
            assert user_mgr.list_users() == []
            user_mgr.invite_user("test@example.com", "admin@sensestack.xyz")
            users = user_mgr.list_users()
            assert len(users) == 1
            assert users[0]["email"] == "test@example.com"
            assert users[0]["status"] == "invited"
            assert users[0]["invited_by"] == "admin@sensestack.xyz"
            assert user_mgr.is_allowed("test@example.com") is True
            user_mgr.revoke_user("test@example.com")
            assert user_mgr.list_users() == []
            assert user_mgr.is_allowed("test@example.com") is False


class TestRecordLogin:
    def test_record_login_updates_status(self, user_mgr):
        user_mgr.invite_user("test@example.com", "admin@sensestack.xyz")
        user_mgr.record_login("test@example.com", "google")
        users = user_mgr.list_users()
        assert len(users) == 1
        assert users[0]["status"] == "active"
        assert users[0]["sign_in_method"] == "google"
        assert "last_login" in users[0]


class TestAdminEndpoints:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    def test_admin_me(self, client):
        res = client.get("/api/admin/me")
        assert res.status_code == 200
        data = res.json()
        assert "email" in data
        assert "is_admin" in data

    def test_admin_users_in_dev_mode(self, client):
        res = client.get("/api/admin/users")
        assert res.status_code == 200
        assert "users" in res.json()

    def test_admin_invite_and_list(self, client):
        res = client.post("/api/admin/invite", json={"email": "newuser@test.com"})
        assert res.status_code == 200
        assert res.json()["status"] == "invited"

    def test_admin_revoke(self, client):
        client.post("/api/admin/invite", json={"email": "torevoke@test.com"})
        res = client.delete("/api/admin/users/torevoke@test.com")
        assert res.status_code == 200
        assert res.json()["status"] == "revoked"
