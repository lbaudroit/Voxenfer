"""Tests pytest de service-comptes.

Lancer :  pytest -q
Base en mémoire, secret et admin de test fixés AVANT l'import du service.
"""

import os

import pytest  # noqa: E402

import app as app_module  # noqa: E402
from db import Base, engine, Session, Joueur  # noqa: E402


os.environ["DB_PATH"] = ":memory:"
os.environ["JWT_SECRET"] = "secret-de-test"
os.environ["ADMIN_PSEUDO"] = "admin"
os.environ["ADMIN_PASSWORD"] = "motdepasseadmin"


@pytest.fixture
def client():
    # Repartir d'une base propre + admin amorcé à chaque test.
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    app_module.amorcer_admin()
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


def _token_admin(client):
    r = client.post("/login", json={"pseudo": "admin", "mot_de_passe": "motdepasseadmin"})
    assert r.status_code == 200
    return r.get_json()["token"]


def _entete(token):
    return {"Authorization": f"Bearer {token}"}


# --- Cas demandés par le sujet ---------------------------------------------

def test_register_puis_login_donne_un_jeton(client):
    assert client.post("/register", json={"pseudo": "maxime", "mot_de_passe": "abc"}).status_code == 201
    r = client.post("/login", json={"pseudo": "maxime", "mot_de_passe": "abc"})
    assert r.status_code == 200
    assert r.get_json()["token"]


def test_login_mauvais_mot_de_passe_401(client):
    client.post("/register", json={"pseudo": "maxime", "mot_de_passe": "abc"})
    r = client.post("/login", json={"pseudo": "maxime", "mot_de_passe": "MAUVAIS"})
    assert r.status_code == 401


def test_register_en_double_409(client):
    client.post("/register", json={"pseudo": "maxime", "mot_de_passe": "abc"})
    r = client.post("/register", json={"pseudo": "maxime", "mot_de_passe": "autre"})
    assert r.status_code == 409


def test_non_admin_accorde_role_403(client):
    client.post("/register", json={"pseudo": "leon", "mot_de_passe": "x"})
    client.post("/register", json={"pseudo": "cible", "mot_de_passe": "x"})
    tok = client.post("/login", json={"pseudo": "leon", "mot_de_passe": "x"}).get_json()["token"]
    r = client.post("/joueurs/cible/roles", json={"role": "moderateur"}, headers=_entete(tok))
    assert r.status_code == 403


def test_aucun_mot_de_passe_en_clair(client):
    client.post("/register", json={"pseudo": "maxime", "mot_de_passe": "secret123"})
    # Ni stocké en clair...
    with Session() as s:
        j = s.query(Joueur).filter_by(pseudo="maxime").first()
        assert j.mot_de_passe_hache != "secret123"
        assert "secret123" not in j.mot_de_passe_hache
    # ...ni renvoyé par la fiche publique.
    fiche = client.get("/joueurs/maxime").get_json()
    assert "secret123" not in str(fiche)
    assert "mot_de_passe" not in fiche


# --- Cas complémentaires ----------------------------------------------------

def test_register_champ_manquant_400(client):
    assert client.post("/register", json={"pseudo": "x"}).status_code == 400


def test_admin_accorde_role_200(client):
    client.post("/register", json={"pseudo": "cible", "mot_de_passe": "x"})
    tok = _token_admin(client)
    r = client.post("/joueurs/cible/roles", json={"role": "moderateur"}, headers=_entete(tok))
    assert r.status_code == 200
    assert "moderateur" in r.get_json()["roles"]


def test_accorder_role_inconnu_400(client):
    client.post("/register", json={"pseudo": "cible", "mot_de_passe": "x"})
    tok = _token_admin(client)
    r = client.post("/joueurs/cible/roles", json={"role": "sorcier"}, headers=_entete(tok))
    assert r.status_code == 400


def test_accorder_role_joueur_inconnu_404(client):
    tok = _token_admin(client)
    r = client.post("/joueurs/fantome/roles", json={"role": "moderateur"}, headers=_entete(tok))
    assert r.status_code == 404


def test_ecriture_sans_jeton_401(client):
    r = client.post("/joueurs/x/roles", json={"role": "moderateur"})
    assert r.status_code == 401


def test_fiche_inconnue_404(client):
    assert client.get("/joueurs/fantome").status_code == 404


def test_profil_editable_par_interesse(client):
    client.post("/register", json={"pseudo": "maxime", "mot_de_passe": "x"})
    tok = client.post("/login", json={"pseudo": "maxime", "mot_de_passe": "x"}).get_json()["token"]
    r = client.patch("/joueurs/maxime/profil", json={"titre": "Bâtisseur", "bio": "Salut"}, headers=_entete(tok))
    assert r.status_code == 200
    assert r.get_json()["profil"]["titre"] == "Bâtisseur"


def test_profil_autrui_interdit_403(client):
    client.post("/register", json={"pseudo": "maxime", "mot_de_passe": "x"})
    client.post("/register", json={"pseudo": "leon", "mot_de_passe": "x"})
    tok = client.post("/login", json={"pseudo": "leon", "mot_de_passe": "x"}).get_json()["token"]
    r = client.patch("/joueurs/maxime/profil", json={"bio": "piraté"}, headers=_entete(tok))
    assert r.status_code == 403


def test_health_et_metrics(client):
    assert client.get("/health").get_json()["status"] == "ok"
    assert client.get("/metrics").status_code == 200


def test_changement_mot_de_passe(client):
    client.post("/register", json={"pseudo": "maxime", "mot_de_passe": "vieux"})
    tok = client.post("/login", json={"pseudo": "maxime", "mot_de_passe": "vieux"}).get_json()["token"]
    r = client.post("/joueurs/maxime/mot_de_passe", json={"ancien": "vieux", "nouveau": "neuf"}, headers=_entete(tok))
    assert r.status_code == 200
    assert client.post("/login", json={"pseudo": "maxime", "mot_de_passe": "neuf"}).status_code == 200
    assert client.post("/login", json={"pseudo": "maxime", "mot_de_passe": "vieux"}).status_code == 401
