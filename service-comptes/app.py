"""app.py — service-comptes (G2) : identité des joueurs + émission des JWT.

Service CENTRAL et point de vérité de l'identité. Lectures ouvertes, écritures
protégées par JWT. Routes SANS préfixe (la gateway retire « /comptes/ »).

  Base      : /register, /login, /joueurs, /joueurs/<pseudo>,
              /joueurs/<pseudo>/roles
  Étoffé    : retrait de rôle, profil éditable, suppression de compte
  Bonus     : profession, changement de mot de passe
  Infra     : /health, /metrics
"""

import os
import time

from flask import Flask, request, jsonify, g
from werkzeug.security import generate_password_hash, check_password_hash

import auth
from db import Session, Joueur, init_db

app = Flask(__name__)

ROLES_CONNUS = {"joueur", "moderateur", "admin"}
PROFESSIONS_CONNUES = {"mineur", "batisseur", "guerrier"}

# Compteurs simples pour /metrics.
_debut = time.time()
_compteurs = {"requetes": 0, "inscriptions": 0, "connexions": 0, "connexions_ko": 0}


# ----------------------------------------------------------------------------
# Robustesse : tout passe en JSON, on n'expose jamais un 500 brut.
# ----------------------------------------------------------------------------
@app.before_request
def _compter_requetes():
    _compteurs["requetes"] += 1


@app.errorhandler(404)
def _err_404(_):
    return jsonify(erreur="ressource inconnue"), 404


@app.errorhandler(405)
def _err_405(_):
    return jsonify(erreur="methode non autorisee"), 405


@app.errorhandler(Exception)
def _err_500(e):
    # Filet de sécurité : aucune exception ne doit fuir en 500 non-JSON.
    code = getattr(e, "code", 500) or 500
    return jsonify(erreur="erreur interne", detail=str(e)), code


def corps_json():
    """Renvoie le corps JSON ou None si absent/mal formé (-> 400 côté appelant)."""
    return request.get_json(silent=True)


# ----------------------------------------------------------------------------
# Infra
# ----------------------------------------------------------------------------
@app.get("/health")
def health():
    return jsonify(status="ok", service="comptes")


@app.get("/metrics")
def metrics():
    with Session() as s:
        nb_joueurs = s.query(Joueur).count()
    return jsonify(
        service="comptes",
        uptime_secondes=round(time.time() - _debut, 1),
        joueurs_enregistres=nb_joueurs,
        requetes_total=_compteurs["requetes"],
        inscriptions_total=_compteurs["inscriptions"],
        connexions_total=_compteurs["connexions"],
        connexions_echouees_total=_compteurs["connexions_ko"],
    )


# ----------------------------------------------------------------------------
# Base — inscription / connexion
# ----------------------------------------------------------------------------
@app.post("/register")
def register():
    """Crée un compte {pseudo, mot_de_passe}. Mot de passe HACHÉ, jamais en clair."""
    data = corps_json()
    if not data or "pseudo" not in data or "mot_de_passe" not in data:
        return jsonify(erreur="champs requis: pseudo, mot_de_passe"), 400

    pseudo = str(data["pseudo"]).strip()
    mot_de_passe = str(data["mot_de_passe"])
    if not pseudo or not mot_de_passe:
        return jsonify(erreur="pseudo et mot_de_passe non vides"), 400

    with Session() as s:
        if s.query(Joueur).filter_by(pseudo=pseudo).first():
            return jsonify(erreur="pseudo deja pris"), 409
        joueur = Joueur(
            pseudo=pseudo,
            mot_de_passe_hache=generate_password_hash(mot_de_passe),
            roles="joueur",
        )
        s.add(joueur)
        s.commit()
        _compteurs["inscriptions"] += 1
        return jsonify(joueur.vers_public()), 201


@app.post("/login")
def login():
    """Vérifie {pseudo, mot_de_passe} et renvoie {"token": "..."}. 401 si KO."""
    data = corps_json()
    if not data or "pseudo" not in data or "mot_de_passe" not in data:
        return jsonify(erreur="champs requis: pseudo, mot_de_passe"), 400

    pseudo = str(data["pseudo"]).strip()
    mot_de_passe = str(data["mot_de_passe"])

    with Session() as s:
        joueur = s.query(Joueur).filter_by(pseudo=pseudo).first()
        # Message volontairement identique que le pseudo existe ou non.
        if not joueur or not check_password_hash(joueur.mot_de_passe_hache, mot_de_passe):
            _compteurs["connexions_ko"] += 1
            return jsonify(erreur="identifiants invalides"), 401
        jeton = auth.emettre_jeton(joueur.pseudo, joueur.liste_roles())
        _compteurs["connexions"] += 1
        return jsonify(token=jeton)


# ----------------------------------------------------------------------------
# Base / étoffé — fiches joueurs
# ----------------------------------------------------------------------------
@app.get("/joueurs")
def liste_joueurs():
    """Liste publique des pseudos."""
    with Session() as s:
        pseudos = [j.pseudo for j in s.query(Joueur).order_by(Joueur.pseudo).all()]
    return jsonify(pseudos)


@app.get("/joueurs/<pseudo>")
def fiche_joueur(pseudo):
    """Fiche publique {pseudo, roles, profil}. 404 si inconnu."""
    with Session() as s:
        joueur = s.query(Joueur).filter_by(pseudo=pseudo).first()
        if not joueur:
            return jsonify(erreur="joueur inconnu"), 404
        return jsonify(joueur.vers_public())


# ----------------------------------------------------------------------------
# Étoffé — gestion des rôles (admin uniquement)
# ----------------------------------------------------------------------------
@app.post("/joueurs/<pseudo>/roles")
@auth.require_role("admin")
def accorder_role(pseudo):
    """Accorde un rôle {role}. Réservé admin (seul un admin donne moderateur)."""
    data = corps_json()
    if not data or "role" not in data:
        return jsonify(erreur="champ requis: role"), 400
    role = str(data["role"]).strip()
    if role not in ROLES_CONNUS:
        return jsonify(erreur=f"role inconnu (attendus: {sorted(ROLES_CONNUS)})"), 400

    with Session() as s:
        joueur = s.query(Joueur).filter_by(pseudo=pseudo).first()
        if not joueur:
            return jsonify(erreur="joueur inconnu"), 404
        roles = joueur.liste_roles()
        if role in roles:
            return jsonify(erreur="role deja accorde"), 409
        roles.append(role)
        joueur.definir_roles(roles)
        s.commit()
        return jsonify(joueur.vers_public())


@app.delete("/joueurs/<pseudo>/roles/<role>")
@auth.require_role("admin")
def retirer_role(pseudo, role):
    """Retire un rôle. Réservé admin."""
    with Session() as s:
        joueur = s.query(Joueur).filter_by(pseudo=pseudo).first()
        if not joueur:
            return jsonify(erreur="joueur inconnu"), 404
        roles = joueur.liste_roles()
        if role not in roles:
            return jsonify(erreur="role non possede"), 404
        roles.remove(role)
        joueur.definir_roles(roles)
        s.commit()
        return jsonify(joueur.vers_public())


# ----------------------------------------------------------------------------
# Étoffé — profil éditable par l'intéressé (ou un admin)
# ----------------------------------------------------------------------------
def _peut_modifier(cible):
    """L'intéressé lui-même, ou un admin."""
    return g.pseudo == cible or auth.a_le_role(g.roles, "admin")


@app.patch("/joueurs/<pseudo>/profil")
@auth.require_jwt
def modifier_profil(pseudo):
    """Modifie {titre?, bio?}. Réservé à l'intéressé ou à un admin."""
    if not _peut_modifier(pseudo):
        return jsonify(erreur="modification reservee a l'interesse ou a un admin"), 403
    data = corps_json()
    if data is None:
        return jsonify(erreur="corps JSON attendu"), 400

    with Session() as s:
        joueur = s.query(Joueur).filter_by(pseudo=pseudo).first()
        if not joueur:
            return jsonify(erreur="joueur inconnu"), 404
        if "titre" in data:
            joueur.titre = (str(data["titre"]).strip() or None) if data["titre"] is not None else None
        if "bio" in data:
            joueur.bio = (str(data["bio"]).strip() or None) if data["bio"] is not None else None
        s.commit()
        return jsonify(joueur.vers_public())


# ----------------------------------------------------------------------------
# Étoffé — suppression de compte (soi-même ou admin)
# ----------------------------------------------------------------------------
@app.delete("/joueurs/<pseudo>")
@auth.require_jwt
def supprimer_compte(pseudo):
    if not _peut_modifier(pseudo):
        return jsonify(erreur="suppression reservee a l'interesse ou a un admin"), 403
    with Session() as s:
        joueur = s.query(Joueur).filter_by(pseudo=pseudo).first()
        if not joueur:
            return jsonify(erreur="joueur inconnu"), 404
        s.delete(joueur)
        s.commit()
        return jsonify(supprime=pseudo)


# ----------------------------------------------------------------------------
# Bonus — profession (effet en jeu côté mod) + changement de mot de passe
# ----------------------------------------------------------------------------
@app.post("/joueurs/<pseudo>/profession")
@auth.require_jwt
def definir_profession(pseudo):
    """Définit la profession {profession}. Réservé à l'intéressé ou à un admin."""
    if not _peut_modifier(pseudo):
        return jsonify(erreur="reserve a l'interesse ou a un admin"), 403
    data = corps_json()
    if not data or "profession" not in data:
        return jsonify(erreur="champ requis: profession"), 400
    profession = str(data["profession"]).strip()
    if profession not in PROFESSIONS_CONNUES:
        return jsonify(erreur=f"profession inconnue (attendues: {sorted(PROFESSIONS_CONNUES)})"), 400
    with Session() as s:
        joueur = s.query(Joueur).filter_by(pseudo=pseudo).first()
        if not joueur:
            return jsonify(erreur="joueur inconnu"), 404
        joueur.profession = profession
        s.commit()
        return jsonify(joueur.vers_public())


@app.post("/joueurs/<pseudo>/mot_de_passe")
@auth.require_jwt
def changer_mot_de_passe(pseudo):
    """Change le mot de passe {ancien, nouveau}. Réservé à l'intéressé."""
    if g.pseudo != pseudo:
        return jsonify(erreur="reserve a l'interesse"), 403
    data = corps_json()
    if not data or "ancien" not in data or "nouveau" not in data:
        return jsonify(erreur="champs requis: ancien, nouveau"), 400
    nouveau = str(data["nouveau"])
    if not nouveau:
        return jsonify(erreur="nouveau mot de passe non vide"), 400
    with Session() as s:
        joueur = s.query(Joueur).filter_by(pseudo=pseudo).first()
        if not joueur:
            return jsonify(erreur="joueur inconnu"), 404
        if not check_password_hash(joueur.mot_de_passe_hache, str(data["ancien"])):
            return jsonify(erreur="ancien mot de passe incorrect"), 401
        joueur.mot_de_passe_hache = generate_password_hash(nouveau)
        s.commit()
        return jsonify(pseudo=pseudo, mot_de_passe="modifie")


# ----------------------------------------------------------------------------
# Amorçage d'un admin initial (sinon personne ne peut promouvoir personne).
# Identifiants surchargeables par variables d'environnement, documentés au README.
# ----------------------------------------------------------------------------
def amorcer_admin():
    pseudo = os.environ.get("ADMIN_PSEUDO", "admin")
    mot_de_passe = os.environ.get("ADMIN_PASSWORD", "admin")
    with Session() as s:
        if not s.query(Joueur).filter_by(pseudo=pseudo).first():
            s.add(Joueur(
                pseudo=pseudo,
                mot_de_passe_hache=generate_password_hash(mot_de_passe),
                roles="admin",
            ))
            s.commit()
            app.logger.info("Admin initial cree: %s", pseudo)


init_db()
amorcer_admin()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
