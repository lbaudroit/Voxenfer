# Contrat complété — service-comptes (G2)

> À fusionner dans `2-contrats.md` (section *service-comptes*). On **étoffe sans
> casser** les signatures de base. Routes **internes** (sans préfixe ; la gateway
> ajoute/retire `/comptes/`).

## Tableau des routes

| Méthode | Route | Auth | Rôle | Corps attendu / réponse |
|--------:|:------|:-----|:-----|:------------------------|
| POST | `/register` | — | — | **req** `{pseudo, mot_de_passe}` · **201** `{pseudo, roles, profil}` · 400 champ manquant · 409 pseudo pris |
| POST | `/login` | — | — | **req** `{pseudo, mot_de_passe}` · **200** `{token}` · 401 identifiants invalides |
| GET | `/joueurs` | — | — | **200** `["maxime", "leon", ...]` (liste de pseudos) |
| GET | `/joueurs/<pseudo>` | — | — | **200** `{pseudo, roles, profil}` · 404 inconnu |
| POST | `/joueurs/<pseudo>/roles` | jwt | admin | **req** `{role}` · **200** fiche · 400 rôle inconnu · 404 joueur inconnu · 409 déjà accordé |
| DELETE | `/joueurs/<pseudo>/roles/<role>` | jwt | admin | **200** fiche · 404 joueur/rôle absent |
| PATCH | `/joueurs/<pseudo>/profil` | jwt | intéressé **ou** admin | **req** `{titre?, bio?}` · **200** fiche · 403 si ni intéressé ni admin |
| DELETE | `/joueurs/<pseudo>` | jwt | intéressé **ou** admin | **200** `{supprime}` · 403/404 |
| POST | `/joueurs/<pseudo>/profession` | jwt | intéressé **ou** admin | **req** `{profession}` ∈ {mineur, batisseur, guerrier} · **200** fiche *(bonus)* |
| POST | `/joueurs/<pseudo>/mot_de_passe` | jwt | intéressé | **req** `{ancien, nouveau}` · **200** · 401 ancien faux *(bonus)* |
| GET | `/health` | — | — | **200** `{status:"ok", service:"comptes"}` |
| GET | `/metrics` | — | — | **200** compteurs JSON |

## Champs JSON exacts

**Objet `joueur` (fiche publique)** — renvoyé par `/register`, `/joueurs/<pseudo>`
et les routes d'écriture qui répondent une fiche. **Ne contient jamais le mot de passe.**

```json
{
  "pseudo": "maxime",
  "roles": ["joueur"],
  "profil": { "titre": null, "bio": null, "profession": null }
}
```

**Login** :

```json
{ "token": "eyJhbGciOiJIUzI1Ni␣..." }
```

**Erreur** (toutes les routes, avec le bon code HTTP) :

```json
{ "erreur": "message court" }
```

## Décisions d'équipe (à valider tous ensemble)

1. **Payload JWT** (conforme au contrat) : `{"pseudo": "...", "roles": [...], "iat": ..., "exp": ...}`.
   Algorithme **HS256**, secret `JWT_SECRET` commun, durée **12 h** (`JWT_DUREE_H`).
2. **Hiérarchie** : `require_role(r)` accepte tout rôle **≥ r** (`joueur < moderateur < admin`).
   Un **admin satisfait donc `require_role("moderateur")`**. (Lecture de « appartenance à
   la liste » + hiérarchie ; à confirmer avec G6 qui utilise les rôles.)
3. **Nouveaux comptes** : rôle `joueur` par défaut.
4. **Rôles connus** : `joueur`, `moderateur`, `admin` (tout autre rôle → 400).
5. **Admin initial** amorcé au démarrage : `admin` / `admin` (compte de service,
   surchargeable par `ADMIN_PSEUDO`/`ADMIN_PASSWORD`).
6. **Login** : un mauvais mot de passe **et** un pseudo inconnu renvoient le même
   `401` (pas de fuite d'information).
