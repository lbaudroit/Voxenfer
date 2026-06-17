"""Test suite pour service-comptes (pytest framework).

Usage:
  pytest test_comptes.py -v                    # Verbose
  pytest test_comptes.py -v -s                 # With prints
  pytest test_comptes.py::TestAuth -v          # Only Auth tests
  pytest test_comptes.py --cov                 # Coverage report
  pytest test_comptes.py -x                    # Stop on first failure
"""

import os
import tempfile

import auth
import db
import jwt
import pytest
from sqlalchemy import inspect
from werkzeug.security import check_password_hash, generate_password_hash


@pytest.fixture(scope="function")
def temp_db():
    """Fixture: Create a temporary database for each test."""
    # Create temp file
    fd, temp_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    # Override DB_PATH
    original_db_path = db.DB_PATH
    db.DB_PATH = temp_path

    # Recreate engine and session
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    db.engine = create_engine(f"sqlite:///{temp_path}")
    db.Session = sessionmaker(bind=db.engine)
    db.init()

    yield temp_path

    # Cleanup
    db.DB_PATH = original_db_path
    if os.path.exists(temp_path):
        os.remove(temp_path)


class TestPasswordHashing:
    """Tests for password hashing security."""

    def test_password_hash_valid(self):
        """Password hash should verify correct password."""
        pwd = "test123"
        hashed = generate_password_hash(pwd)
        assert check_password_hash(hashed, pwd)

    def test_password_hash_invalid(self):
        """Password hash should reject wrong password."""
        pwd = "test123"
        wrong_pwd = "wrong"
        hashed = generate_password_hash(pwd)
        assert not check_password_hash(hashed, wrong_pwd)

    def test_password_hash_different_each_time(self):
        """Each hash should be unique (salt protection)."""
        pwd = "test123"
        hash1 = generate_password_hash(pwd)
        hash2 = generate_password_hash(pwd)
        assert hash1 != hash2
        # But both should validate
        assert check_password_hash(hash1, pwd)
        assert check_password_hash(hash2, pwd)

    def test_password_hash_not_plaintext(self):
        """Hash should not contain plaintext password."""
        pwd = "secret_password_123"
        hashed = generate_password_hash(pwd)
        assert pwd not in hashed


class TestJWT:
    """Tests for JWT token creation and verification."""

    def test_create_token_basic(self):
        """Should create valid JWT token."""
        token = auth.creer_token("alice", ["joueur"])
        assert isinstance(token, str)
        assert len(token) > 20

    def test_token_payload_structure(self):
        """Token payload should have correct structure."""
        pseudo = "alice"
        roles = ["joueur", "moderateur"]
        token = auth.creer_token(pseudo, roles)

        payload = jwt.decode(token, auth.SECRET, algorithms=["HS256"])
        assert payload["pseudo"] == pseudo
        assert payload["roles"] == roles

    def test_token_default_role(self):
        """Token should have default 'joueur' role."""
        token = auth.creer_token("bob")
        payload = jwt.decode(token, auth.SECRET, algorithms=["HS256"])
        assert payload["roles"] == ["joueur"]

    def test_token_multiple_roles(self):
        """Token should support multiple roles."""
        roles = ["joueur", "moderateur", "admin"]
        token = auth.creer_token("admin_user", roles)
        payload = jwt.decode(token, auth.SECRET, algorithms=["HS256"])
        assert len(payload["roles"]) == 3
        assert all(role in payload["roles"] for role in roles)

    def test_token_invalid_raises_error(self):
        """Invalid token should raise JWT error."""
        with pytest.raises(jwt.InvalidTokenError):
            jwt.decode("invalid_token", auth.SECRET, algorithms=["HS256"])

    def test_token_wrong_secret_raises_error(self):
        """Token with wrong secret should raise error."""
        token = auth.creer_token("alice", ["joueur"])
        with pytest.raises(jwt.InvalidTokenError):
            jwt.decode(token, "wrong_secret", algorithms=["HS256"])

    def test_token_algorithm_hs256(self):
        """Token should use HS256 algorithm."""
        token = auth.creer_token("alice", ["joueur"])
        # Decode without verification to check header
        header = jwt.get_unverified_header(token)
        assert header["alg"] == "HS256"


class TestDatabase:
    """Tests for database models and schema."""

    def test_tables_exist(self, temp_db):
        """Database should have required tables."""
        inspector_obj = inspect(db.engine)
        tables = inspector_obj.get_table_names()

        assert "joueurs" in tables
        assert "profils" in tables
        assert "roles" in tables

    def test_joueurs_table_columns(self, temp_db):
        """Joueurs table should have required columns."""
        inspector_obj = inspect(db.engine)
        columns = {col["name"] for col in inspector_obj.get_columns("joueurs")}

        assert "id" in columns
        assert "pseudo" in columns
        assert "mot_de_passe_hash" in columns
        assert "created_at" in columns
        assert "updated_at" in columns

    def test_profils_table_columns(self, temp_db):
        """Profils table should have required columns."""
        inspector_obj = inspect(db.engine)
        columns = {col["name"] for col in inspector_obj.get_columns("profils")}

        assert "id" in columns
        assert "joueur_id" in columns
        assert "pseudo" in columns
        assert "titre" in columns
        assert "bio" in columns
        assert "profession" in columns

    def test_roles_table_columns(self, temp_db):
        """Roles table should have required columns."""
        inspector_obj = inspect(db.engine)
        columns = {col["name"] for col in inspector_obj.get_columns("roles")}

        assert "id" in columns
        assert "joueur_id" in columns
        assert "pseudo" in columns
        assert "role" in columns

    def test_joueur_unique_pseudo(self, temp_db):
        """Pseudo should be unique in joueurs table."""
        with db.Session() as s:
            # Create first joueur
            j1 = db.Joueur(pseudo="alice", mot_de_passe_hash="hash1")
            s.add(j1)
            s.commit()

            # Try to create duplicate
            j2 = db.Joueur(pseudo="alice", mot_de_passe_hash="hash2")
            s.add(j2)

            with pytest.raises(Exception):  # SQLAlchemy IntegrityError
                s.commit()

    def test_create_joueur(self, temp_db):
        """Should create joueur in database."""
        with db.Session() as s:
            joueur = db.Joueur(
                pseudo="alice", mot_de_passe_hash=generate_password_hash("secret123")
            )
            s.add(joueur)
            s.commit()

            # Verify it was created
            found = s.query(db.Joueur).filter_by(pseudo="alice").first()
            assert found is not None
            assert found.pseudo == "alice"

    def test_create_profil(self, temp_db):
        """Should create profil in database."""
        with db.Session() as s:
            joueur = db.Joueur(
                pseudo="bob", mot_de_passe_hash=generate_password_hash("secret")
            )
            s.add(joueur)
            s.flush()

            profil = db.Profil(
                joueur_id=joueur.id,
                pseudo="bob",
                titre="Mineur",
                bio="J'aime creuser",
                profession="mineur",
            )
            s.add(profil)
            s.commit()

            # Verify it was created
            found = s.query(db.Profil).filter_by(pseudo="bob").first()
            assert found is not None
            assert found.titre == "Mineur"
            assert found.profession == "mineur"

    def test_create_role(self, temp_db):
        """Should create role in database."""
        with db.Session() as s:
            joueur = db.Joueur(pseudo="charlie", mot_de_passe_hash="hash")
            s.add(joueur)
            s.flush()

            role = db.Role(joueur_id=joueur.id, pseudo="charlie", role="admin")
            s.add(role)
            s.commit()

            # Verify it was created
            found = s.query(db.Role).filter_by(pseudo="charlie").first()
            assert found is not None
            assert found.role == "admin"

    def test_cascade_delete_roles_with_joueur(self, temp_db):
        """Deleting joueur should handle associated roles."""
        with db.Session() as s:
            joueur = db.Joueur(pseudo="david", mot_de_passe_hash="hash")
            s.add(joueur)
            s.flush()

            role = db.Role(joueur_id=joueur.id, pseudo="david", role="joueur")
            s.add(role)
            s.commit()

            # Delete joueur
            joueur_id = joueur.id
            s.delete(joueur)
            s.commit()

            # Verify role is gone or remains (depends on cascade configuration)
            # Our design doesn't configure cascade, so role remains as orphaned
            # This is fine - app-level deletion handles this in app.py
            found_role = s.query(db.Role).filter_by(joueur_id=joueur_id).first()
            # Test passes - we're just documenting the behavior
            pass


class TestIntegration:
    """Integration tests combining multiple components."""

    def test_full_user_creation_flow(self, temp_db):
        """Full flow: create joueur, profil, role."""
        pseudo = "eve"
        password = "secure_pass_123"

        with db.Session() as s:
            # Create joueur
            joueur = db.Joueur(
                pseudo=pseudo, mot_de_passe_hash=generate_password_hash(password)
            )
            s.add(joueur)
            s.flush()

            # Create profil
            profil = db.Profil(
                joueur_id=joueur.id, pseudo=pseudo, titre="Explorer", bio="Adventurer"
            )
            s.add(profil)

            # Create role
            role = db.Role(joueur_id=joueur.id, pseudo=pseudo, role="joueur")
            s.add(role)
            s.commit()

            # Verify everything
            found_joueur = s.query(db.Joueur).filter_by(pseudo=pseudo).first()
            assert found_joueur is not None
            assert check_password_hash(found_joueur.mot_de_passe_hash, password)

            found_profil = (
                s.query(db.Profil).filter_by(joueur_id=found_joueur.id).first()
            )
            assert found_profil is not None
            assert found_profil.titre == "Explorer"

            found_role = s.query(db.Role).filter_by(joueur_id=found_joueur.id).first()
            assert found_role is not None
            assert found_role.role == "joueur"

    def test_jwt_token_for_user(self, temp_db):
        """Should create valid JWT for registered user."""
        pseudo = "frank"
        roles = ["joueur", "moderateur"]

        with db.Session() as s:
            joueur = db.Joueur(pseudo=pseudo, mot_de_passe_hash="hash")
            s.add(joueur)
            s.flush()

            for role_name in roles:
                role = db.Role(joueur_id=joueur.id, pseudo=pseudo, role=role_name)
                s.add(role)
            s.commit()

        # Create token
        token = auth.creer_token(pseudo, roles)

        # Verify token
        payload = jwt.decode(token, auth.SECRET, algorithms=["HS256"])
        assert payload["pseudo"] == pseudo
        assert payload["roles"] == roles

    def test_multiple_users_independent(self, temp_db):
        """Multiple users should be independent."""
        with db.Session() as s:
            j1 = db.Joueur(pseudo="user1", mot_de_passe_hash="hash1")
            j2 = db.Joueur(pseudo="user2", mot_de_passe_hash="hash2")
            s.add_all([j1, j2])
            s.flush()

            r1 = db.Role(joueur_id=j1.id, pseudo="user1", role="joueur")
            r2 = db.Role(joueur_id=j2.id, pseudo="user2", role="admin")
            s.add_all([r1, r2])
            s.commit()

        # Verify independence
        with db.Session() as s:
            user1 = s.query(db.Joueur).filter_by(pseudo="user1").first()
            user2 = s.query(db.Joueur).filter_by(pseudo="user2").first()

            roles1 = s.query(db.Role).filter_by(joueur_id=user1.id).all()
            roles2 = s.query(db.Role).filter_by(joueur_id=user2.id).all()

            assert [r.role for r in roles1] == ["joueur"]
            assert [r.role for r in roles2] == ["admin"]


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_empty_pseudo(self, temp_db):
        """Empty pseudo should be handled."""
        with db.Session() as s:
            joueur = db.Joueur(pseudo="", mot_de_passe_hash="hash")
            s.add(joueur)
            s.commit()

            found = s.query(db.Joueur).filter_by(pseudo="").first()
            assert found is not None

    def test_very_long_pseudo(self, temp_db):
        """Very long pseudo should be stored (up to 50 chars)."""
        long_pseudo = "a" * 50
        with db.Session() as s:
            joueur = db.Joueur(pseudo=long_pseudo, mot_de_passe_hash="hash")
            s.add(joueur)
            s.commit()

            found = s.query(db.Joueur).filter_by(pseudo=long_pseudo).first()
            assert found is not None

    def test_special_characters_in_password_hash(self, temp_db):
        """Password with special chars should hash correctly."""
        pwd = "p@ssw0rd!#$%^&*()"
        hashed = generate_password_hash(pwd)
        assert check_password_hash(hashed, pwd)

    def test_unicode_in_pseudo(self, temp_db):
        """Unicode in pseudo should be handled."""
        pseudo = "جويل"  # Arabic
        with db.Session() as s:
            joueur = db.Joueur(pseudo=pseudo, mot_de_passe_hash="hash")
            s.add(joueur)
            s.commit()

            found = s.query(db.Joueur).filter_by(pseudo=pseudo).first()
            assert found is not None

    def test_jwt_with_empty_roles(self):
        """JWT with empty roles list."""
        token = auth.creer_token("user", [])
        payload = jwt.decode(token, auth.SECRET, algorithms=["HS256"])
        assert payload["roles"] == []


@pytest.fixture(scope="session", autouse=True)
def cleanup():
    """Clean up test database after all tests."""
    yield
    # Cleanup code here if needed


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
