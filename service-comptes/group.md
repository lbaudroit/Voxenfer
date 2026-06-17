# group.md — G2 service-comptes

> Modèle à compléter avec **vos** noms. Le barème note les rôles **et** le
> journal heure par heure.

## Qui a fait quoi

| Membre | Rôle | Contributions |
|---|---|---|
| *Prénom A* | Dev principal | `app.py`, `db.py`, conteneurisation (Dockerfile) |
| *Prénom B* | Responsable contrat / doc | `auth.py` (JWT), `README.md`, section `2-contrats.md`, coordination avec G6 (rôles) |
| *Prénom C* | Responsable tests | jeux de `curl`, `test_app.py`, validation des codes d'erreur |

## Journal (heure par heure)

```
S1
09h00  squelette copié depuis service-template, /health répond              (A)
09h15  db.py : modèle Joueur (pseudo, mdp haché, roles CSV)                 (A)
09h30  /register + /login, mot de passe haché werkzeug                      (A)
09h45  auth.py : require_jwt + require_role + émission du jeton              (B)
10h00  validation contrat tous ensemble : payload {pseudo, roles}, HS256    (B)
10h20  /joueurs et /joueurs/<pseudo> (fiche publique sans mdp)              (A)
10h40  premiers curl OK ; bug : /login renvoyait 200 sur mauvais mdp        (C)
10h55  réglé : check_password_hash + 401 ; même message pseudo inconnu      (C)
11h10  amorçage admin au démarrage (sinon personne ne promeut personne)     (A)

S2
13h30  /joueurs/<pseudo>/roles (admin) : 200/400/404/409                    (A)
13h50  on confirme avec G6 : hiérarchie -> admin satisfait require_role(mod) (B)
14h10  étoffé : PATCH profil (intéressé ou admin), DELETE compte            (A)
14h30  bonus : profession + changement de mot de passe                      (A)
14h45  test_app.py : tous les cas du sujet passent (register/login/403/409) (C)
15h00  /metrics (compteurs JSON), handler 404/500 -> JSON                   (B)
15h15  docker build + run OK, joignable via la gateway /comptes/...         (A)
15h30  fige : README, contrat complété, group.md, archive Moodle           (B,C)
```

## Points de coordination inter-équipes

- **Tous** : valeur de `JWT_SECRET` et payload `{pseudo, roles}` (sinon les autres
  services ne décodent pas nos jetons).
- **G6 (modération)** : usage des rôles `moderateur`/`admin` et de la hiérarchie.
- **G1 (plateforme)** : route `/comptes/*` dans le `Caddyfile`, même `JWT_SECRET`
  dans le `docker-compose.yml`, port 5000.

## Ce qui a coincé

- Login qui acceptait un mauvais mot de passe (oubli du `check_password_hash`) → réglé.
- Question de la hiérarchie des rôles tranchée avec G6 (admin ≥ moderateur).
- Pas d'admin au premier démarrage → ajout de l'amorçage `amorcer_admin()`.
