"""auth.py — Charpente JWT partagée par TOUS les services Voxenfer.

C'est service-comptes (G2) qui ÉMET les jetons (au /login) ; tous les autres
services se contentent de les VÉRIFIER avec ce même fichier. Le secret est
partagé via la variable d'environnement JWT_SECRET (fixée dans docker-compose).

Payload du contrat (2-contrats.md) :
    { "pseudo": "maxime", "roles": ["joueur"] }

Hiérarchie : joueur < moderateur < admin.
`require_role(role)` accepte tout rôle SUPÉRIEUR OU ÉGAL dans la hiérarchie
(un admin satisfait donc require_role("moderateur")). C'est notre lecture de
« appartenance à la liste » + hiérarchie, notée dans le contrat.
"""

import os
import functools
import datetime

import jwt
from flask import request, jsonify, g

# Secret partagé, IDENTIQUE pour tous les services (cf. docker-compose.yml).
SECRET = os.environ.get("JWT_SECRET", "dev-secret-a-changer")
ALGORITHME = "HS256"

# Hiérarchie des rôles : plus le nombre est grand, plus le rôle est puissant.
HIERARCHIE = {"joueur": 0, "moderateur": 1, "admin": 2}

# Durée de vie du jeton (heures). Au-delà, il faut se reconnecter.
DUREE_JETON_H = int(os.environ.get("JWT_DUREE_H", "12"))


def emettre_jeton(pseudo, roles):
    """Émet un JWT signé. Utilisé UNIQUEMENT par service-comptes au /login."""
    maintenant = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "pseudo": pseudo,
        "roles": list(roles),
        "iat": maintenant,
        "exp": maintenant + datetime.timedelta(hours=DUREE_JETON_H),
    }
    return jwt.encode(payload, SECRET, algorithm=ALGORITHME)


def _extraire_jeton():
    """Récupère le jeton depuis l'en-tête « Authorization: Bearer <jeton> »."""
    entete = request.headers.get("Authorization", "")
    if not entete.startswith("Bearer "):
        return None
    jeton = entete[len("Bearer "):].strip()
    return jeton or None


def _charger_identite():
    """Décode le jeton et range l'identité dans flask.g.

    Renvoie None si tout va bien, sinon un tuple (reponse_json, code_http)
    que l'appelant doit retourner directement.
    """
    jeton = _extraire_jeton()
    if not jeton:
        return jsonify(erreur="jeton manquant"), 401
    try:
        payload = jwt.decode(jeton, SECRET, algorithms=[ALGORITHME])
    except jwt.ExpiredSignatureError:
        return jsonify(erreur="jeton expire"), 401
    except jwt.PyJWTError:
        return jsonify(erreur="jeton invalide"), 401
    g.identite = payload
    g.pseudo = payload.get("pseudo")
    g.roles = payload.get("roles", []) or []
    return None


def require_jwt(f):
    """Décorateur : exige un JWT valide. Place l'identité dans g.pseudo / g.roles."""

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        echec = _charger_identite()
        if echec is not None:
            return echec
        return f(*args, **kwargs)

    return wrapper


def a_le_role(roles, role_min):
    """True si l'un des `roles` est >= `role_min` dans la hiérarchie."""
    niveau_requis = HIERARCHIE.get(role_min, 99)
    niveau_max = max((HIERARCHIE.get(r, -1) for r in roles), default=-1)
    return niveau_max >= niveau_requis


def require_role(role_min):
    """Décorateur : exige un JWT valide ET un rôle >= role_min (hiérarchie).

    401 si pas/plus de jeton valide, 403 si le rôle est insuffisant.
    """

    def decorateur(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            echec = _charger_identite()
            if echec is not None:
                return echec
            if not a_le_role(g.roles, role_min):
                return jsonify(erreur="role insuffisant"), 403
            return f(*args, **kwargs)

        return wrapper

    return decorateur
