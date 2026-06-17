# service-comptes (G2) — Voxenfer

**Identité des joueurs + émission des jetons JWT.**
Service *central* de l'écosystème : c'est lui qui crée les comptes et **émet les
JWT** que **tous** les autres services vérifient. Il ne gère ni pièces, ni
scores, ni boutique — uniquement *qui est qui* et *quels rôles* chacun a.

## Sommaire des routes

| Méthode | Route (interne, sans préfixe) | Auth | Effet |
|--------:|:------|:-----|:------|
| GET  | `/health` | — | sonde de vie |
| GET  | `/metrics` | — | compteurs JSON |
| POST | `/register` | — | crée un compte `{pseudo, mot_de_passe}` (haché) |
| POST | `/login` | — | renvoie `{ "token": "..." }` |
| GET  | `/joueurs` | — | liste des pseudos |
| GET  | `/joueurs/<pseudo>` | — | fiche `{pseudo, roles, profil}` |
| POST | `/joueurs/<pseudo>/roles` | admin | accorde un rôle `{role}` |
| DELETE | `/joueurs/<pseudo>/roles/<role>` | admin | retire un rôle |
| PATCH | `/joueurs/<pseudo>/profil` | intéressé/admin | `{titre?, bio?}` |
| DELETE | `/joueurs/<pseudo>` | intéressé/admin | supprime le compte |
| POST | `/joueurs/<pseudo>/profession` | intéressé/admin | `{profession}` *(bonus)* |
| POST | `/joueurs/<pseudo>/mot_de_passe` | intéressé | `{ancien, nouveau}` *(bonus)* |

> Via la gateway, tout est préfixé par `/comptes/...` (le préfixe est retiré
> avant d'arriver ici). Donc `POST /comptes/login` → `POST /login` en interne.

## Lancer le service

### Avec Docker (recommandé — comme dans le compose commun)

```bash
docker build -t service-comptes .
docker run -p 5000:5000 -e JWT_SECRET="le-secret-commun" service-comptes
```

Dans l'écosystème, G1 fixe le **même `JWT_SECRET`** pour tous les services dans
`docker-compose.yml`, et le service n'est joignable que **via la gateway**
(`http://localhost:8080/comptes/...`).

### En local (sans Docker)

```bash
pip install -r requirements.txt
JWT_SECRET="le-secret-commun" python app.py    # écoute sur :5000
```

### Variables d'environnement

| Variable | Défaut | Rôle |
|---|---|---|
| `JWT_SECRET` | `dev-secret-a-changer` | secret de signature, **commun à tous** |
| `JWT_DUREE_H` | `12` | durée de vie du jeton (heures) |
| `DB_PATH` | `comptes.db` | fichier SQLite (`:memory:` en test) |
| `ADMIN_PSEUDO` | `admin` | compte admin amorcé au démarrage |
| `ADMIN_PASSWORD` | `admin` | mot de passe de cet admin |

## L'admin initial

Un **admin** est créé automatiquement au démarrage (sinon personne ne peut
promouvoir personne). Par défaut : **pseudo `admin`, mot de passe `admin`**
(surchargeables par `ADMIN_PSEUDO` / `ADMIN_PASSWORD`). Cet admin est un
**compte de service**, pas un joueur du jeu. On obtient son jeton via `/login`.

## Exemples d'appel (curl)

Directement sur le service (`:5000`) ou via la gateway (`:8080/comptes`).

```bash
# 1. Inscription d'un joueur
curl -X POST localhost:5000/register \
  -H "Content-Type: application/json" \
  -d '{"pseudo":"maxime","mot_de_passe":"hunter2"}'
# -> 201 {"pseudo":"maxime","roles":["joueur"],"profil":{...}}

# 2. Connexion -> jeton
TOKEN=$(curl -s -X POST localhost:5000/login \
  -H "Content-Type: application/json" \
  -d '{"pseudo":"maxime","mot_de_passe":"hunter2"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')

# 3. Fiche publique (route ouverte — c'est ce que le mod lit à la connexion)
curl localhost:5000/joueurs/maxime
# -> {"pseudo":"maxime","roles":["joueur"],"profil":{"titre":null,"bio":null,"profession":null}}

# 4. Promotion par l'admin (écriture protégée)
ADMIN=$(curl -s -X POST localhost:5000/login \
  -H "Content-Type: application/json" \
  -d '{"pseudo":"admin","mot_de_passe":"admin"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')

curl -X POST localhost:5000/joueurs/maxime/roles \
  -H "Authorization: Bearer $ADMIN" \
  -H "Content-Type: application/json" \
  -d '{"role":"moderateur"}'
# -> 200, maxime devient moderateur

# 5. Le joueur édite son propre profil
curl -X PATCH localhost:5000/joueurs/maxime/profil \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"titre":"Explorateur","bio":"Salut !"}'
```

## Le JWT (notre part du contrat)

- **Émission** au `/login` : `jwt.encode({...}, auth.SECRET, algorithm="HS256")`.
- **Payload** conforme à `2-contrats.md` :
  ```json
  { "pseudo": "maxime", "roles": ["joueur"], "iat": ..., "exp": ... }
  ```
- **Vérification** dans `auth.py` (`require_jwt`, `require_role`) — fichier
  **partagé tel quel** par tous les services.
- **Hiérarchie** `joueur < moderateur < admin` : `require_role("moderateur")`
  accepte aussi un admin (rôle supérieur).

## Codes HTTP renvoyés

`200`/`201` OK · `400` champ manquant/invalide · `401` non authentifié (jeton
absent/invalide/expiré, ou mauvais mot de passe) · `403` rôle insuffisant ·
`404` joueur/route inconnu · `409` doublon (pseudo déjà pris, rôle déjà accordé).
Aucune route ne renvoie de `500` brut : un *handler* global rattrape tout en JSON.

## Robustesse / sécurité

- Mots de passe **hachés** (`werkzeug.security`), jamais stockés ni renvoyés en clair.
- Lectures **ouvertes**, écritures **protégées** par JWT.
- Message d'erreur de login **identique** que le pseudo existe ou non.
- Base SQLite **propre au service**, via l'ORM SQLAlchemy.

## Tests

```bash
pip install pytest
pytest -q        # base en mémoire, couvre les cas du sujet
```

## Fichiers

```
service-comptes/
├── app.py            # routes Flask
├── db.py             # ORM SQLAlchemy + modèle Joueur
├── auth.py           # charpente JWT (émission + vérification) — partagée
├── test_app.py       # tests pytest
├── requirements.txt
├── Dockerfile
└── README.md
```
