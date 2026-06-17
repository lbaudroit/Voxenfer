"""Authentification JWT partagée par les services Voxenfer -- À COMPLÉTER.

Auteur : Philippe ROUSSILLE <roussille@3il.fr>

Vous avez fait du JWT au TP 09 : à vous d'écrire la VÉRIFICATION du jeton, en
respectant le contrat commun (2-contrats.md) pour que les services se comprennent :
  - jeton transmis dans l'en-tête  Authorization: Bearer <jeton>  (algo HS256) ;
  - signé avec le SECRET commun ci-dessous (le même pour tous les services) ;
  - payload : {"pseudo": "...", "roles": [...]} ;
  - jeton absent ou invalide -> 401 ; rôle requis absent de la liste -> 403 ;
  - après vérification, posez le contenu du jeton dans request.joueur, pour que
    la route sache QUI appelle (request.joueur["pseudo"], request.joueur["roles"]).

Le service-comptes, lui, ÉMET le jeton à son /login : c'est à lui d'écrire cette
partie (jwt.encode avec le MÊME SECRET et le MÊME payload).
"""
import os
from functools import wraps

import jwt          # PyJWT : jwt.encode / jwt.decode (HS256)
from flask import request, jsonify

# Secret partagé : DOIT être le même pour tous les services (sinon les jetons
# émis par service-comptes sont rejetés ailleurs). Fixé dans docker-compose.yml.
SECRET = os.environ.get("JWT_SECRET", "voxenfer-secret-partage-du-serveur-2026")


def require_jwt(f):
    """Décorateur : refuse la requête (401) si le jeton est absent ou invalide ;
    sinon pose le payload dans request.joueur et exécute la route.

    À ÉCRIRE (cf. en-tête du fichier, 2-contrats.md et TP 09).
    """
    @wraps(f)
    def verifie(*args, **kwargs):
        # TODO : lire l'en-tête Authorization, décoder le JWT (HS256, SECRET),
        #        renvoyer 401 si absent/invalide, sinon request.joueur = payload.
        raise NotImplementedError("require_jwt à écrire (TP 09 / 2-contrats.md)")
    return verifie


def require_role(role):
    """Décorateur paramétré : comme require_jwt, mais exige en plus que `role`
    figure dans la liste des rôles du jeton (sinon 403).

    À ÉCRIRE (cf. en-tête du fichier, 2-contrats.md et TP 09).
    """
    def decorateur(f):
        @wraps(f)
        def verifie(*args, **kwargs):
            # TODO : vérifier le jeton (comme require_jwt), puis vérifier que
            #        `role` est dans request.joueur["roles"] (sinon 403).
            raise NotImplementedError("require_role à écrire (TP 09 / 2-contrats.md)")
        return verifie
    return decorateur
