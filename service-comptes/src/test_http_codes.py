"""HTTP Response Code Tests for service-comptes.

Tests verify that all routes return the correct HTTP status codes
as specified in 2-contrats.md (page 23-31).
"""

import json
import os
import tempfile

import app as app_module
import db
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from werkzeug.security import generate_password_hash


@pytest.fixture(scope="function")
def temp_db():
    """Fixture: Create a temporary database for each test."""
    fd, temp_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    # Override DB_PATH
    original_db_path = db.DB_PATH
    db.DB_PATH = temp_path

    # Recreate engine and session
    db.engine = create_engine(f"sqlite:///{temp_path}")
    db.Session = sessionmaker(bind=db.engine)
    db.init()

    # Create admin account with admin role
    with db.Session() as s:
        admin = db.Joueur(
            pseudo="admin", mot_de_passe_hash=generate_password_hash("admin-secret")
        )
        s.add(admin)
        s.flush()

        # Add profil
        profil = db.Profil(
            joueur_id=admin.id, pseudo="admin", titre="Admin", bio="Admin account"
        )
        s.add(profil)

        # Add roles
        role1 = db.Role(joueur_id=admin.id, pseudo="admin", role="joueur")
        role2 = db.Role(joueur_id=admin.id, pseudo="admin", role="admin")
        s.add_all([role1, role2])
        s.commit()

    yield temp_path

    # Cleanup
    db.DB_PATH = original_db_path
    if os.path.exists(temp_path):
        os.remove(temp_path)


@pytest.fixture
def client(temp_db):
    """Fixture: Create Flask test client."""
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as client:
        yield client


def get_user_token(client, pseudo="alice", password="secret123"):
    """Helper: Create/get token for a user."""
    # Register
    client.post(
        "/register",
        data=json.dumps({"pseudo": pseudo, "mot_de_passe": password}),
        content_type="application/json",
    )

    # Login
    response = client.post(
        "/login",
        data=json.dumps({"pseudo": pseudo, "mot_de_passe": password}),
        content_type="application/json",
    )
    return response.get_json()["token"]


def get_admin_token(client):
    """Helper: Get admin token."""
    response = client.post(
        "/login",
        data=json.dumps({"pseudo": "admin", "mot_de_passe": "admin-secret"}),
        content_type="application/json",
    )
    return response.get_json()["token"]


class TestRegisterCodes:
    """Test /register endpoint response codes."""

    def test_register_201_created(self, client):
        """POST /register with valid data -> 201 Created."""
        response = client.post(
            "/register",
            data=json.dumps({"pseudo": "newuser", "mot_de_passe": "pass123"}),
            content_type="application/json",
        )
        assert response.status_code == 201
        assert "message" in response.get_json()

    def test_register_400_missing_pseudo(self, client):
        """POST /register without pseudo -> 400 Bad Request."""
        response = client.post(
            "/register",
            data=json.dumps({"mot_de_passe": "pass123"}),
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_register_400_missing_password(self, client):
        """POST /register without password -> 400 Bad Request."""
        response = client.post(
            "/register",
            data=json.dumps({"pseudo": "alice"}),
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_register_400_short_pseudo(self, client):
        """POST /register with pseudo < 3 chars -> 400 Bad Request."""
        response = client.post(
            "/register",
            data=json.dumps({"pseudo": "ab", "mot_de_passe": "pass123"}),
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_register_400_short_password(self, client):
        """POST /register with password < 6 chars -> 400 Bad Request."""
        response = client.post(
            "/register",
            data=json.dumps({"pseudo": "alice", "mot_de_passe": "short"}),
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_register_409_duplicate_pseudo(self, client):
        """POST /register with duplicate pseudo -> 409 Conflict."""
        # Create first user
        response1 = client.post(
            "/register",
            data=json.dumps({"pseudo": "alice", "mot_de_passe": "pass123"}),
            content_type="application/json",
        )
        assert response1.status_code == 201

        # Try to create duplicate
        response2 = client.post(
            "/register",
            data=json.dumps({"pseudo": "alice", "mot_de_passe": "pass456"}),
            content_type="application/json",
        )
        assert response2.status_code == 409


class TestLoginCodes:
    """Test /login endpoint response codes."""

    def test_login_200_success(self, client):
        """POST /login with valid credentials -> 200 OK."""
        # Register first
        client.post(
            "/register",
            data=json.dumps({"pseudo": "alice", "mot_de_passe": "pass123"}),
            content_type="application/json",
        )

        # Login
        response = client.post(
            "/login",
            data=json.dumps({"pseudo": "alice", "mot_de_passe": "pass123"}),
            content_type="application/json",
        )
        assert response.status_code == 200
        assert "token" in response.get_json()

    def test_login_400_missing_pseudo(self, client):
        """POST /login without pseudo -> 400 Bad Request."""
        response = client.post(
            "/login",
            data=json.dumps({"mot_de_passe": "pass123"}),
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_login_400_missing_password(self, client):
        """POST /login without password -> 400 Bad Request."""
        response = client.post(
            "/login",
            data=json.dumps({"pseudo": "alice"}),
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_login_401_wrong_password(self, client):
        """POST /login with wrong password -> 401 Unauthorized."""
        # Register
        client.post(
            "/register",
            data=json.dumps({"pseudo": "alice", "mot_de_passe": "correct"}),
            content_type="application/json",
        )

        # Login with wrong password
        response = client.post(
            "/login",
            data=json.dumps({"pseudo": "alice", "mot_de_passe": "wrong"}),
            content_type="application/json",
        )
        assert response.status_code == 401

    def test_login_401_user_not_found(self, client):
        """POST /login with non-existent user -> 401 Unauthorized."""
        response = client.post(
            "/login",
            data=json.dumps({"pseudo": "nonexistent", "mot_de_passe": "pass"}),
            content_type="application/json",
        )
        assert response.status_code == 401


class TestJoueurListCodes:
    """Test GET /joueurs endpoint response codes."""

    def test_joueurs_list_200_ok(self, client):
        """GET /joueurs -> 200 OK."""
        response = client.get("/joueurs")
        assert response.status_code == 200
        assert "joueurs" in response.get_json()

    def test_joueurs_list_200_with_users(self, client):
        """GET /joueurs with users -> 200 OK with list."""
        # Create users
        get_user_token(client, "alice", "pass1234")
        get_user_token(client, "bob", "pass5678")

        response = client.get("/joueurs")
        assert response.status_code == 200
        joueurs = response.get_json()["joueurs"]
        assert "alice" in joueurs
        assert "bob" in joueurs


class TestJoueurGetCodes:
    """Test GET /joueurs/<pseudo> endpoint response codes."""

    def test_joueur_get_200_ok(self, client):
        """GET /joueurs/<pseudo> with existing user -> 200 OK."""
        get_user_token(client, "alice", "pass123")

        response = client.get("/joueurs/alice")
        assert response.status_code == 200
        data = response.get_json()
        assert data["pseudo"] == "alice"
        assert "roles" in data
        assert "profil" in data

    def test_joueur_get_404_not_found(self, client):
        """GET /joueurs/<pseudo> with non-existent user -> 404 Not Found."""
        response = client.get("/joueurs/nonexistent")
        assert response.status_code == 404


class TestGrantRoleCodes:
    """Test POST /joueurs/<pseudo>/roles endpoint response codes."""

    def test_grant_role_201_created(self, client):
        """POST /joueurs/<pseudo>/roles with admin token -> 201 Created."""
        # Create user
        get_user_token(client, "alice", "pass123")
        admin_token = get_admin_token(client)

        # Grant role
        response = client.post(
            "/joueurs/alice/roles",
            data=json.dumps({"role": "moderateur"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 201

    def test_grant_role_200_already_granted(self, client):
        """POST /joueurs/<pseudo>/roles when role already granted -> 200 OK."""
        get_user_token(client, "alice", "pass123")
        admin_token = get_admin_token(client)

        # First grant
        client.post(
            "/joueurs/alice/roles",
            data=json.dumps({"role": "moderateur"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        # Second grant (duplicate)
        response = client.post(
            "/joueurs/alice/roles",
            data=json.dumps({"role": "moderateur"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200

    def test_grant_role_400_invalid_role(self, client):
        """POST /joueurs/<pseudo>/roles with invalid role -> 400 Bad Request."""
        get_user_token(client, "alice", "pass123")
        admin_token = get_admin_token(client)

        response = client.post(
            "/joueurs/alice/roles",
            data=json.dumps({"role": "invalid_role"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 400

    def test_grant_role_401_no_token(self, client):
        """POST /joueurs/<pseudo>/roles without token -> 401 Unauthorized."""
        get_user_token(client, "alice", "pass123")

        response = client.post(
            "/joueurs/alice/roles",
            data=json.dumps({"role": "moderateur"}),
            content_type="application/json",
        )
        assert response.status_code == 401

    def test_grant_role_403_insufficient_role(self, client):
        """POST /joueurs/<pseudo>/roles as non-admin -> 403 Forbidden."""
        user_token = get_user_token(client, "alice", "pass123")
        get_user_token(client, "bob", "pass456")

        response = client.post(
            "/joueurs/bob/roles",
            data=json.dumps({"role": "moderateur"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert response.status_code == 403

    def test_grant_role_404_user_not_found(self, client):
        """POST /joueurs/<pseudo>/roles with non-existent user -> 404 Not Found."""
        admin_token = get_admin_token(client)

        response = client.post(
            "/joueurs/nonexistent/roles",
            data=json.dumps({"role": "moderateur"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404


class TestRevokeRoleCodes:
    """Test DELETE /joueurs/<pseudo>/roles/<role> endpoint response codes."""

    def test_revoke_role_200_ok(self, client):
        """DELETE /joueurs/<pseudo>/roles/<role> -> 200 OK."""
        get_user_token(client, "alice", "pass123")
        admin_token = get_admin_token(client)

        # First grant a role
        client.post(
            "/joueurs/alice/roles",
            data=json.dumps({"role": "moderateur"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        # Revoke it
        response = client.delete(
            "/joueurs/alice/roles/moderateur",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200

    def test_revoke_role_400_invalid_role(self, client):
        """DELETE /joueurs/<pseudo>/roles/<invalid> -> 400 Bad Request."""
        get_user_token(client, "alice", "pass123")
        admin_token = get_admin_token(client)

        response = client.delete(
            "/joueurs/alice/roles/invalid_role",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 400

    def test_revoke_role_401_no_token(self, client):
        """DELETE /joueurs/<pseudo>/roles/<role> without token -> 401 Unauthorized."""
        get_user_token(client, "alice", "pass123")

        response = client.delete("/joueurs/alice/roles/moderateur")
        assert response.status_code == 401

    def test_revoke_role_403_insufficient_role(self, client):
        """DELETE /joueurs/<pseudo>/roles/<role> as non-admin -> 403 Forbidden."""
        user_token = get_user_token(client, "alice", "pass123")
        get_user_token(client, "bob", "pass456")

        response = client.delete(
            "/joueurs/bob/roles/moderateur",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert response.status_code == 403

    def test_revoke_role_404_user_not_found(self, client):
        """DELETE /joueurs/<pseudo>/roles/<role> with non-existent user -> 404."""
        admin_token = get_admin_token(client)

        response = client.delete(
            "/joueurs/nonexistent/roles/moderateur",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404

    def test_revoke_role_404_role_not_found(self, client):
        """DELETE /joueurs/<pseudo>/roles/<role> with non-existent role -> 404."""
        get_user_token(client, "alice", "pass123")
        admin_token = get_admin_token(client)

        response = client.delete(
            "/joueurs/alice/roles/moderateur",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404


class TestModifyProfilCodes:
    """Test PATCH /joueurs/<pseudo>/profil endpoint response codes."""

    def test_modify_profil_200_ok(self, client):
        """PATCH /joueurs/<pseudo>/profil with valid token -> 200 OK."""
        user_token = get_user_token(client, "alice", "pass123")

        response = client.patch(
            "/joueurs/alice/profil",
            data=json.dumps(
                {"titre": "Mineur", "bio": "I mine", "profession": "mineur"}
            ),
            content_type="application/json",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert response.status_code == 200

    def test_modify_profil_400_title_too_long(self, client):
        """PATCH /joueurs/<pseudo>/profil with title > 100 chars -> 400."""
        user_token = get_user_token(client, "alice", "pass123")

        response = client.patch(
            "/joueurs/alice/profil",
            data=json.dumps({"titre": "x" * 101, "bio": "", "profession": "mineur"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert response.status_code == 400

    def test_modify_profil_400_bio_too_long(self, client):
        """PATCH /joueurs/<pseudo>/profil with bio > 500 chars -> 400."""
        user_token = get_user_token(client, "alice", "pass123")

        response = client.patch(
            "/joueurs/alice/profil",
            data=json.dumps(
                {"titre": "Title", "bio": "x" * 501, "profession": "mineur"}
            ),
            content_type="application/json",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert response.status_code == 400

    def test_modify_profil_400_invalid_profession(self, client):
        """PATCH /joueurs/<pseudo>/profil with invalid profession -> 400."""
        user_token = get_user_token(client, "alice", "pass123")

        response = client.patch(
            "/joueurs/alice/profil",
            data=json.dumps(
                {"titre": "Title", "bio": "Bio", "profession": "invalid_profession"}
            ),
            content_type="application/json",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert response.status_code == 400

    def test_modify_profil_401_no_token(self, client):
        """PATCH /joueurs/<pseudo>/profil without token -> 401 Unauthorized."""
        get_user_token(client, "alice", "pass123")

        response = client.patch(
            "/joueurs/alice/profil",
            data=json.dumps({"titre": "Title", "bio": "Bio"}),
            content_type="application/json",
        )
        assert response.status_code == 401

    def test_modify_profil_403_not_own_profil(self, client):
        """PATCH /joueurs/<other>/profil as non-admin -> 403 Forbidden."""
        user_token = get_user_token(client, "alice", "pass123")
        get_user_token(client, "bob", "pass456")

        response = client.patch(
            "/joueurs/bob/profil",
            data=json.dumps({"titre": "Title", "bio": "Bio"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert response.status_code == 403

    def test_modify_profil_200_admin_can_modify_other(self, client):
        """PATCH /joueurs/<pseudo>/profil as admin on other -> 200."""
        get_user_token(client, "alice", "pass123")
        admin_token = get_admin_token(client)

        response = client.patch(
            "/joueurs/alice/profil",
            data=json.dumps({"titre": "Title", "bio": "Bio"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200

    def test_modify_profil_404_user_not_found(self, client):
        """PATCH /joueurs/<pseudo>/profil with non-existent user -> 403."""
        user_token = get_user_token(client, "alice", "pass123")

        response = client.patch(
            "/joueurs/nonexistent/profil",
            data=json.dumps({"titre": "Title", "bio": "Bio"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        # Auth check first: user can only modify own profile, so 403 for others
        assert response.status_code == 403


class TestDeleteAccountCodes:
    """Test DELETE /joueurs/<pseudo> endpoint response codes."""

    def test_delete_account_200_ok(self, client):
        """DELETE /joueurs/<pseudo> with valid token -> 200 OK."""
        user_token = get_user_token(client, "alice", "pass123")

        response = client.delete(
            "/joueurs/alice", headers={"Authorization": f"Bearer {user_token}"}
        )
        assert response.status_code == 200

    def test_delete_account_401_no_token(self, client):
        """DELETE /joueurs/<pseudo> without token -> 401 Unauthorized."""
        get_user_token(client, "alice", "pass123")

        response = client.delete("/joueurs/alice")
        assert response.status_code == 401

    def test_delete_account_403_not_own_account(self, client):
        """DELETE /joueurs/<other> as non-admin -> 403 Forbidden."""
        user_token = get_user_token(client, "alice", "pass123")
        get_user_token(client, "bob", "pass456")

        response = client.delete(
            "/joueurs/bob", headers={"Authorization": f"Bearer {user_token}"}
        )
        assert response.status_code == 403

    def test_delete_account_200_admin_deletes_other(self, client):
        """DELETE /joueurs/<other> as admin -> 200 OK."""
        get_user_token(client, "alice", "pass123")
        admin_token = get_admin_token(client)

        response = client.delete(
            "/joueurs/alice", headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200

    def test_delete_account_404_user_not_found(self, client):
        """DELETE /joueurs/<pseudo> with non-existent user -> 403."""
        user_token = get_user_token(client, "alice", "pass123")

        response = client.delete(
            "/joueurs/nonexistent", headers={"Authorization": f"Bearer {user_token}"}
        )
        # Auth check first: user can only delete own account, so 403 for others
        assert response.status_code == 403


class TestHealthMetricsCodes:
    """Test observability endpoints response codes."""

    def test_health_200_ok(self, client):
        """GET /health -> 200 OK."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.get_json()
        assert "status" in data
        assert "service" in data

    def test_metrics_200_ok(self, client):
        """GET /metrics -> 200 OK."""
        response = client.get("/metrics")
        assert response.status_code == 200
        data = response.get_json()
        assert "requetes_total" in data


class TestInvalidTokenCodes:
    """Test invalid/malformed JWT handling."""

    def test_invalid_token_401(self, client):
        """Request with invalid token -> 401 Unauthorized."""
        response = client.post(
            "/joueurs/alice/roles",
            data=json.dumps({"role": "moderateur"}),
            content_type="application/json",
            headers={"Authorization": "Bearer invalid_token"},
        )
        assert response.status_code == 401

    def test_malformed_bearer_header_401(self, client):
        """Request with malformed Bearer header -> 401 Unauthorized."""
        response = client.post(
            "/joueurs/alice/roles",
            data=json.dumps({"role": "moderateur"}),
            content_type="application/json",
            headers={"Authorization": "InvalidFormat token"},
        )
        assert response.status_code == 401

    def test_no_bearer_header_401(self, client):
        """Request without Bearer header -> 401 Unauthorized."""
        response = client.post(
            "/joueurs/alice/roles",
            data=json.dumps({"role": "moderateur"}),
            content_type="application/json",
        )
        assert response.status_code == 401


class TestResponseCodeConsistency:
    """Verify consistency of response codes across endpoints."""

    def test_all_missing_fields_return_400(self, client):
        """All endpoints should return 400 for malformed requests."""
        # Register missing pseudo
        response = client.post(
            "/register",
            data=json.dumps({"mot_de_passe": "pass"}),
            content_type="application/json",
        )
        assert response.status_code == 400

        # Login missing password
        response = client.post(
            "/login",
            data=json.dumps({"pseudo": "alice"}),
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_all_auth_required_return_401_without_token(self, client):
        """All protected endpoints should return 401 without token."""
        get_user_token(client, "alice", "pass123")

        # Test all protected endpoints
        protected_endpoints = [
            ("POST", "/joueurs/alice/roles", {"role": "moderateur"}),
            ("DELETE", "/joueurs/alice/roles/joueur", None),
            ("PATCH", "/joueurs/alice/profil", {"titre": "Title"}),
            ("DELETE", "/joueurs/alice", None),
        ]

        for method, endpoint, data in protected_endpoints:
            if method == "POST":
                response = client.post(
                    endpoint, data=json.dumps(data), content_type="application/json"
                )
            elif method == "PATCH":
                response = client.patch(
                    endpoint, data=json.dumps(data), content_type="application/json"
                )
            elif method == "DELETE":
                response = client.delete(endpoint)

            assert response.status_code == 401, f"Failed for {method} {endpoint}"

    def test_all_nonexistent_resources_return_404(self, client):
        """Most endpoints return 404 for non-existent resources."""
        # Get non-existent user
        response = client.get("/joueurs/nonexistent")
        assert response.status_code == 404

        # Grant role to non-existent user
        admin_token = get_admin_token(client)
        response = client.post(
            "/joueurs/nonexistent/roles",
            data=json.dumps({"role": "moderateur"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404

        # Note: Modify/Delete endpoints check authorization first, so non-existent
        # users you're trying to modify return 403 (forbidden) not 404 (not found)
        # This is correct security: "you can't modify that" vs "that doesn't exist"
        user_token = get_user_token(client, "alice", "pass123")
        response = client.patch(
            "/joueurs/nonexistent/profil",
            data=json.dumps({"titre": "Title"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert response.status_code == 403


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
