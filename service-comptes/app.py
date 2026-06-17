"""Service de comptes et d'authentification Voxenfer.

Auteur : Philippe ROUSSILLE <roussille@3il.fr>

Gère :
  - Inscription (register) : création de compte avec mot de passe haché
  - Connexion (login) : authentification et émission de JWT
  - Fiche joueur : profil public (pseudo, rôles, titre, bio, profession)
  - Gestion des rôles : accord de rôles (admin uniquement)
  - Profils : modification titre/bio
  - Suppression de compte
"""

import auth
import db
from auth import require_jwt, require_role
from flask import Flask, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
db.init()

_metriques = {"requetes": 0}


@app.before_request
def _compter():
    _metriques["requetes"] += 1


# --- Observabilité -------------------------------------------------------


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "comptes"})


@app.route("/metrics")
def metrics():
    return jsonify({"requetes_total": _metriques["requetes"]})


# --- Authentification (register, login) ----------------------------------


@app.route("/register", methods=["POST"])
def register():
    """Crée un compte joueur avec pseudo et mot de passe haché."""
    data = request.get_json() or {}
    pseudo = data.get("pseudo", "").strip()
    mot_de_passe = data.get("mot_de_passe", "")

    # Validation
    if not pseudo or len(pseudo) < 3 or len(pseudo) > 50:
        return jsonify({"erreur": "Pseudo invalide (3-50 caractères)"}), 400
    if not mot_de_passe or len(mot_de_passe) < 6:
        return jsonify({"erreur": "Mot de passe trop court (min. 6 caractères)"}), 400

    try:
        with db.Session() as s:
            # Vérifier l'unicité
            existant = s.query(db.Joueur).filter_by(pseudo=pseudo).first()
            if existant:
                return jsonify({"erreur": "Pseudo déjà existant"}), 409

            # Créer le compte
            joueur = db.Joueur(
                pseudo=pseudo, mot_de_passe_hash=generate_password_hash(mot_de_passe)
            )
            s.add(joueur)
            s.flush()  # pour récupérer l'ID

            # Créer le profil
            profil = db.Profil(joueur_id=joueur.id, pseudo=pseudo, titre="", bio="")
            s.add(profil)

            # Ajouter le rôle par défaut "joueur"
            role = db.Role(joueur_id=joueur.id, pseudo=pseudo, role="joueur")
            s.add(role)
            s.commit()

        return jsonify({"message": "Compte créé"}), 201

    except Exception as e:
        return jsonify({"erreur": str(e)}), 500


@app.route("/login", methods=["POST"])
def login():
    """Authentifie un joueur et renvoie un JWT."""
    data = request.get_json() or {}
    pseudo = data.get("pseudo", "").strip()
    mot_de_passe = data.get("mot_de_passe", "")

    if not pseudo or not mot_de_passe:
        return jsonify({"erreur": "Pseudo et mot de passe requis"}), 400

    try:
        with db.Session() as s:
            joueur = s.query(db.Joueur).filter_by(pseudo=pseudo).first()
            if not joueur or not check_password_hash(
                joueur.mot_de_passe_hash, mot_de_passe
            ):
                return jsonify({"erreur": "Identifiants invalides"}), 401

            # Récupérer les rôles
            roles_db = s.query(db.Role).filter_by(joueur_id=joueur.id).all()
            roles = [r.role for r in roles_db]

            # Émettre le JWT
            token = auth.creer_token(pseudo, roles)
            return jsonify({"token": token}), 200

    except Exception as e:
        return jsonify({"erreur": str(e)}), 500


# --- Joueurs (lectures publiques) ----------------------------------------


@app.route("/joueurs", methods=["GET"])
def lister_joueurs():
    """Liste tous les pseudos des joueurs."""
    try:
        with db.Session() as s:
            joueurs = s.query(db.Joueur).all()
            pseudos = [j.pseudo for j in joueurs]
            return jsonify({"joueurs": pseudos}), 200
    except Exception as e:
        return jsonify({"erreur": str(e)}), 500


@app.route("/joueurs/<pseudo>", methods=["GET"])
def get_joueur(pseudo):
    """Retourne la fiche publique d'un joueur."""
    try:
        with db.Session() as s:
            joueur = s.query(db.Joueur).filter_by(pseudo=pseudo).first()
            if not joueur:
                return jsonify({"erreur": "Joueur inconnu"}), 404

            # Récupérer les rôles
            roles_db = s.query(db.Role).filter_by(joueur_id=joueur.id).all()
            roles = [r.role for r in roles_db]

            # Récupérer le profil
            profil = s.query(db.Profil).filter_by(joueur_id=joueur.id).first()
            profil_data = {}
            if profil:
                profil_data = {
                    "titre": profil.titre,
                    "bio": profil.bio,
                    "profession": profil.profession,
                }

            return jsonify(
                {"pseudo": pseudo, "roles": roles, "profil": profil_data}
            ), 200

    except Exception as e:
        return jsonify({"erreur": str(e)}), 500


# --- Gestion des rôles (admin) -------------------------------------------


@app.route("/joueurs/<pseudo>/roles", methods=["POST"])
@require_role("admin")
def accorder_role(pseudo):
    """Accorde un rôle à un joueur (admin uniquement)."""
    data = request.get_json() or {}
    role = data.get("role", "").strip()

    if role not in ["joueur", "moderateur", "admin"]:
        return jsonify({"erreur": "Rôle invalide"}), 400

    try:
        with db.Session() as s:
            joueur = s.query(db.Joueur).filter_by(pseudo=pseudo).first()
            if not joueur:
                return jsonify({"erreur": "Joueur inconnu"}), 404

            # Vérifier si le rôle existe déjà
            existant = (
                s.query(db.Role).filter_by(joueur_id=joueur.id, role=role).first()
            )
            if existant:
                return jsonify({"message": "Rôle déjà accordé"}), 200

            # Ajouter le rôle
            nouveau_role = db.Role(joueur_id=joueur.id, pseudo=pseudo, role=role)
            s.add(nouveau_role)
            s.commit()

            return jsonify({"message": f"Rôle {role} accordé"}), 201

    except Exception as e:
        return jsonify({"erreur": str(e)}), 500


@app.route("/joueurs/<pseudo>/roles/<role>", methods=["DELETE"])
@require_role("admin")
def retirer_role(pseudo, role):
    """Retire un rôle à un joueur (admin uniquement)."""
    if role not in ["joueur", "moderateur", "admin"]:
        return jsonify({"erreur": "Rôle invalide"}), 400

    try:
        with db.Session() as s:
            joueur = s.query(db.Joueur).filter_by(pseudo=pseudo).first()
            if not joueur:
                return jsonify({"erreur": "Joueur inconnu"}), 404

            role_obj = (
                s.query(db.Role).filter_by(joueur_id=joueur.id, role=role).first()
            )
            if not role_obj:
                return jsonify({"erreur": "Rôle non trouvé"}), 404

            s.delete(role_obj)
            s.commit()

            return jsonify({"message": f"Rôle {role} retiré"}), 200

    except Exception as e:
        return jsonify({"erreur": str(e)}), 500


# --- Profils (modification) ----------------------------------------------


@app.route("/joueurs/<pseudo>/profil", methods=["PATCH"])
@require_jwt
def modifier_profil(pseudo):
    """Modifie le profil d'un joueur (titre, bio, profession).
    L'utilisateur peut modifier son propre profil, l'admin peut modifier n'importe quel profil.
    """
    # Vérifier l'autorisation
    if request.joueur["pseudo"] != pseudo and "admin" not in request.joueur["roles"]:
        return jsonify({"erreur": "Non autorisé"}), 403

    data = request.get_json() or {}
    titre = data.get("titre", "").strip()
    bio = data.get("bio", "").strip()
    profession = data.get("profession", "").strip() if data.get("profession") else None

    # Validation
    if len(titre) > 100 or len(bio) > 500:
        return jsonify({"erreur": "Champs trop longs"}), 400

    if profession and profession not in ["mineur", "batisseur", "guerrier"]:
        return jsonify({"erreur": "Profession invalide"}), 400

    try:
        with db.Session() as s:
            joueur = s.query(db.Joueur).filter_by(pseudo=pseudo).first()
            if not joueur:
                return jsonify({"erreur": "Joueur inconnu"}), 404

            profil = s.query(db.Profil).filter_by(joueur_id=joueur.id).first()
            if not profil:
                return jsonify({"erreur": "Profil non trouvé"}), 404

            profil.titre = titre
            profil.bio = bio
            profil.profession = profession
            s.commit()

            return jsonify({"message": "Profil modifié"}), 200

    except Exception as e:
        return jsonify({"erreur": str(e)}), 500


# --- Suppression de compte -----------------------------------------------


@app.route("/joueurs/<pseudo>", methods=["DELETE"])
@require_jwt
def supprimer_compte(pseudo):
    """Supprime un compte joueur.
    L'utilisateur peut supprimer son propre compte, l'admin peut supprimer n'importe quel compte.
    """
    # Vérifier l'autorisation
    if request.joueur["pseudo"] != pseudo and "admin" not in request.joueur["roles"]:
        return jsonify({"erreur": "Non autorisé"}), 403

    try:
        with db.Session() as s:
            joueur = s.query(db.Joueur).filter_by(pseudo=pseudo).first()
            if not joueur:
                return jsonify({"erreur": "Joueur inconnu"}), 404

            # Supprimer les rôles
            s.query(db.Role).filter_by(joueur_id=joueur.id).delete()

            # Supprimer le profil
            s.query(db.Profil).filter_by(joueur_id=joueur.id).delete()

            # Supprimer le joueur
            s.delete(joueur)
            s.commit()

            return jsonify({"message": "Compte supprimé"}), 200

    except Exception as e:
        return jsonify({"erreur": str(e)}), 500


# --- Bootstrap admin initial (startup) -----------------------------------


def bootstrap_admin():
    """Crée un compte admin initial s'il n'existe pas.
    Identifiants par défaut : pseudo="admin", mot_de_passe="admin-secret"
    """
    try:
        with db.Session() as s:
            existant = s.query(db.Joueur).filter_by(pseudo="admin").first()
            if existant:
                return

            # Créer le compte admin
            admin = db.Joueur(
                pseudo="admin", mot_de_passe_hash=generate_password_hash("admin-secret")
            )
            s.add(admin)
            s.flush()

            # Créer le profil
            profil = db.Profil(
                joueur_id=admin.id,
                pseudo="admin",
                titre="Administrateur",
                bio="Compte de service pour la gestion",
            )
            s.add(profil)

            # Ajouter les rôles admin et joueur
            role_joueur = db.Role(joueur_id=admin.id, pseudo="admin", role="joueur")
            role_admin = db.Role(joueur_id=admin.id, pseudo="admin", role="admin")
            s.add(role_joueur)
            s.add(role_admin)
            s.commit()

            print("Admin initial créé : pseudo='admin', mot_de_passe='admin-secret'")
            print("⚠️ À changer en production !")

    except Exception as e:
        print(f"Erreur lors du bootstrap admin : {e}")


if __name__ == "__main__":
    # Bootstrap l'admin initial
    bootstrap_admin()
    # Lance le serveur
    app.run(host="0.0.0.0", port=5000)
