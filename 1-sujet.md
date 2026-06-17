---
titre: "Projet final Voxenfer"
sous-titre: L'écosystème de micro-services de Luanti
sous-sous-titre: 3iL Ing - I1 apprentissage
auteur: Philippe \textsc{Roussille}
annee: true
rendu-logo: 3il
---

[document:sommaire]

# Contexte - Ateliers Bousquet, projet Voxenfer

> *« Le serveur Luanti tourne. Les joueurs arrivent. Mais il faut tout autour : des comptes, une boutique, des classements, de la modération... Maxime, on monte l'écosystème. Chacun son service. »*
> Léon Mercier, 2024

Maxime, en stage aux Ateliers Bousquet, a lancé **Voxenfer** : un serveur du jeu libre **Luanti** (ex-Minetest). Le cœur du jeu tourne ; il manque tout l'**écosystème de services** autour (comptes, économie, boutique, classements, modération, événements). C'est votre mission : le construire, en micro-services, en réutilisant tout ce que vous avez vu aux **TP 08 à 12**.

Le découpage fonctionnel devait être préparé par **Gilbert Tournesol**, le consultant « cloud-native-agile-devops » des Ateliers... mais Gilbert a confondu « scaler horizontalement » et « partir en télétravail aux Maldives », et reste injoignable. Qu'à cela ne tienne : le découpage a été refait à l'arrache, et (heureux hasard pédagogique) il tombe **pile sur le nombre d'équipes**. À vous de jouer, et soyez plus fiables que Gilbert.

# Pourquoi tout ça ? (Léon et Maxime en discutent)

*Léon Mercier, qui a roulé sa bosse, passe voir où en est le stagiaire.*

**Léon.** Alors, ce serveur de jeu ? Tu as pris Minecraft, comme tout le monde ?

**Maxime.** Non, **Luanti** (l'ancien Minetest). Parce que c'est **libre** : je l'héberge, je le lis, je le modifie, je le conteneurise, **sans licence** ni compte Microsoft obligatoire. Minecraft est fermé : EULA, pas de code à étudier, auth liée à Mojang. Pour un projet pédagogique, le libre gagne haut la main.

**Léon.** Soit. Mais brancher des services sur un jeu, c'est pas l'enfer ?

**Maxime.** Justement, Luanti a un **modding de première classe, en Lua**, avec `request_http_api()` : un mod peut faire des **appels HTTP sortants**. Pile ce qu'il me fallait pour parler à des services REST. Côté Minecraft (mods Java, plugins Bukkit/Spigot), c'est plus lourd et le réseau est plus bridé.

**Léon.** Et tu mets quoi dans ce mod ? Les comptes, la boutique, les scores ?

**Maxime.** Surtout pas ! C'est l'erreur classique : tout fourrer dans le serveur de jeu, et se retrouver avec un **monolithe** greffé sur le jeu. Moi, **le jeu reste mince** : il ne fait que le jeu (le monde, les joueurs connectés). **Tout le métier est dehors**, dans des **micro-services** indépendants, chacun sa base, joignables en HTTP via la gateway.

**Léon.** Donc le jeu, dans ton histoire...

**Maxime.** ... devient un **client comme un autre** de l'écosystème : il appelle nos routes, exactement comme le ferait un site web ou un `curl`. On fait évoluer la boutique sans toucher au jeu, on scale les classements tout seuls. C'est ça, passer du monolithe aux micro-services : séparer le **moteur** (le jeu) des **fonctions métier** (les services).

**Léon.** Et ce fameux mod, il sert à quoi, alors ?

**Maxime.** À la **colle**, avec une contrainte qui explique tout : un mod ne fait que du **sortant**, il n'expose aucun serveur. Donc **jeu vers services**, facile : il appelle nos routes sur événement (connexion, mort, `/acheter`). Mais **services vers jeu**, impossible de « pousser » : alors le mod **interroge** des **files d'actions** et exécute ce qu'il y trouve (livrer un objet, expulser, téléporter). File + acquittement. Et les étudiants n'écrivent **aucun Lua** : juste des routes HTTP propres.

**Léon.** Dernière chose qui me chiffonne. Tu lis **directement la base du jeu** pour savoir qui est connecté ?

**Maxime.** Oui : Luanti sait stocker ses joueurs dans **PostgreSQL** (Minecraft, lui, c'est des fichiers `.mca` et du NBT, illisibles de l'extérieur). J'ai donc un `service-monde` qui **lit cette base en lecture seule** et l'expose en JSON : qui s'est connecté, sa dernière position, son inventaire.

**Léon.** Attends. Si **chaque** service tape dans la base de Luanti, tu te couples à un schéma que tu ne maîtrises pas... ça va péter à la première mise à jour du moteur.

**Maxime.** Exactement le piège que j'ai évité : **un seul** service la lit (`service-monde`), les autres consomment **son** API. C'est le pattern **adaptateur** (*anti-corruption layer*), pas une **base partagée**.

**Léon.** Et la position **en temps réel** d'un joueur qui bouge ?

**Maxime.** La base ne suffit pas, le moteur n'y écrit que de temps en temps. Pour le **live**, c'est le **mod** qui pousse l'info. Deux sources complémentaires : la **base** pour le persisté, le **mod** pour le temps réel.

**Léon.** ... Pas mal, gamin. Tâche d'être plus fiable que Gilbert.

# Ce qu'on attend (les principes, à relire avant tout)

Vous savez déjà tout faire. On réutilise, on n'invente rien. Un service Voxenfer digne de ce nom est :

- **Autonome** : une **responsabilité métier** et **sa propre base** (SQLite). Le service-boutique ne gère pas les comptes ; le service-comptes ne gère pas les scores.
- **Robuste** : il **traite les entrées attendues** sans broncher, et rejette les mauvaises avec un **code clair** (400, 401, 403, 404, 409), **jamais** un 500.
- **Résilient** : il **survit à la panne des autres**. Une dépendance injoignable donne un **503**, pas un plantage en cascade (TP 10).
- **Observable** : `/health` et `/metrics` sur chaque service (TP 09).
- **Poli** : *fail gracefully*, soyez un **bon voisin HTTP**.

> **L'interface partagée (jeton, routes, champs JSON, codes, routage, files d'actions) est dans `2-contrats.md`. Lisez-le AVANT de coder.**

## Vous êtes dans une architecture DÉCENTRALISÉE (le piège n°1)

Dans un monolithe, tout le monde partage les mêmes variables, les mêmes objets : chacun fait sa cuisine. En **micro-services**, chaque équipe code **dans son coin**, avec son propre Flask, sa propre base, sa propre vérité. Conséquence essentielle :

> **L'information échangée entre services doit être claire, complète, et convenue À L'AVANCE.** (Revoyez le cours de conception sur le **couplage** : ici, échange minimal et contrat explicite.)

Vous ne pouvez **pas deviner** comment l'autre appellera votre service. Les **noms de champs, leurs types, la structure JSON** doivent être **connus et partagés**. Concrètement :

- Si `service-boutique` envoie `{"objet_id": 12}` à `service-economie`, l'éco doit attendre exactement `objet_id`, pas `id_objet`.
- Si le JWT contient `"roles": ["admin"]`, chaque service comprend que `"admin"` suffit, et n'attend pas `"is_admin": true`.
- Si une route renvoie une **liste**, l'appelant ne doit pas attendre un dictionnaire.

**La documentation est primordiale.** Avant de coder : relisez ensemble `2-contrats.md`, mettez-vous d'accord **dans l'équipe ET entre équipes**, et notez tout ajustement. C'est le prix de la liberté en micro-services : indépendants, oui, mais l'interopérabilité repose sur une **bonne entente**.

## Comment les services se reconnaissent : JWT vs appels chaînés

Quand un service a besoin de savoir **qui appelle** et **ce qu'il a le droit de faire**, deux stratégies existent.

**1. Appels internes (chained requests).** Chaque service en interroge un autre par HTTP (ex. demander à `service-comptes` si « patron » est admin).

- *Avantages* : données toujours à jour, pas de duplication de logique.
- *Inconvénients* : **couplage fort**, risque de **cascade d'indisponibilité**, plus dur à tester (il faut lancer plusieurs services).

**2. Jeton JWT porté dans la requête.** Au `/login`, `service-comptes` émet un **JWT signé** (identité + rôles). Le client le renvoie dans chaque requête (`Authorization: Bearer <jeton>`), et chaque service le **vérifie localement**, sans appel externe.

- *Avantages* : **résilient** (aucune dépendance à l'exécution), simple avec Flask + PyJWT, **découplage fort**.
- *Inconvénients* : un rôle changé n'est vu qu'à l'expiration du jeton ; il faut gérer proprement la signature et la durée de vie.

**Le choix de Voxenfer : JWT.** Chaque service reste **indépendant et testable seul**. Le **seul** appel inter-service **obligatoire** du projet est `boutique -> economie` (acheter débite des pièces) ; tout le reste passe par le jeton. (Un service `monde` fournit en plus de la **lecture** de l'état du jeu, mais personne n'est tenu de l'appeler.)

# Quatre nouveautés par rapport aux TP

Vous repartez des TP 08 à 12, avec **quatre évolutions** (toutes outillées par le `starter/`, rien à réinventer) :

- **Stockage : une vraie base via un ORM** (SQLAlchemy sur SQLite) au lieu des fichiers JSON. Toujours une base **propre au service** (un fichier SQLite, inclus dans Python, aucun serveur à installer), mais vous manipulez des **objets** Python et l'ORM écrit le SQL à votre place (TP 12). Le `db.py` du `service-template` pose la charpente (moteur, `Session`, `Base`) ; à vous d'y définir vos modèles.
- **JWT par joueur, et une hiérarchie de rôles** : vous connaissez les rôles et `require_role` (TP 09). Ici le jeton identifie un **joueur** : son champ s'appelle `pseudo` (au lieu de `sub`). Trois rôles : `joueur` < `moderateur` < `admin` (**l'admin n'est pas un joueur** : c'est un compte de service). Vous **complétez** la vérification du jeton dans `auth.py` (charpente fournie), en respectant le contrat.
- **Gateway** : une **porte d'entrée unique** (Caddy) devant tous les services, nouveauté du projet. Gérée par **G1** ; un `Caddyfile` à compléter est fourni (un modèle de route en commentaire).
- **Le pont avec le jeu** : votre écosystème est **branché sur le serveur Luanti**, dans les deux sens. En **lecture**, `service-monde` lit la base du serveur (qui a joué, où, avec quoi). En **temps réel**, un **mod** (fourni, côté enseignant) relie les événements du jeu à vos services **et exécute en jeu vos décisions** (livrer un objet, expulser, téléporter...). Vous ne faites que du **HTTP** : aucune ligne de Lua.

# Organisation

- **7 équipes de 3.** **2 séances (~3h).** C'est court : visez **peu mais bien**. Un service **qui marche** vaut mieux qu'un projet ambitieux qui ne démarre pas.
- **G1 = plateforme** : gateway Caddy + `docker-compose` + contrats + **service-monde** (le lecteur de la base Luanti, à coder).
- **G2 à G7 = un micro-service métier chacun.**
- **Le mod Luanti est côté enseignant** (tout le Lua) : vous n'écrivez **que du Flask**.
- **Première demi-heure, tous ensemble (animée par G1)** : valider `2-contrats.md` (secret JWT, payload, hiérarchie de rôles, noms de routes, ports, table des `type` d'actions). **Ne codez pas avant d'être d'accord.**
- **Restez dans votre périmètre.** *Faites-en peu, mais que ça marche.*

## Répartition : les 7 thèmes

Sept équipes, sept thèmes, **un thème par équipe**. Chaque thème pèse à peu près autant de travail ; ils diffèrent surtout par leur **saveur** (ce qu'on y touche) et leur place dans l'écosystème.

| Thème (équipe) | En deux mots | Sa saveur |
|---|---|---|
| **G1 - Plateforme** | gateway + compose + `service-monde` | transverse : Docker, intégration, un peu de SQL ; fait tenir l'ensemble |
| **G2 - Comptes** | identité, émet les JWT | central : tout le monde dépend de votre jeton |
| **G3 - Économie** | les pièces | contenu et net : CRUD + le `409` solde insuffisant |
| **G4 - Boutique** | objets + achat | la vitrine : le seul appel inter-service + livraison en jeu |
| **G5 - Classements** | scores | le plus accessible : un `ORDER BY` et c'est joué |
| **G6 - Modération** | bans, signalements | les rôles + une file d'actions (kick en jeu) |
| **G7 - Événements** | tournois, téléport | une file d'actions + le piège du routage racine |

**Comment répartir (à faire en 15 min, début de séance) :**

- **G1 d'abord** : confiez-le à l'équipe la plus à l'aise avec **Docker et l'intégration** ; c'est elle qui assemble le `docker-compose`, anime la validation des contrats, et code `service-monde`. Rôle « chef d'orchestre ».
- **Les six autres** : au **choix** (ou tirage au sort). Repères : **G4** est la plus riche (appel inter-service + effet en jeu), **G3** et **G5** les plus contenues, **G2** la plus structurante. Équilibrez selon les niveaux.
- **Une fois choisi, on n'en change plus** : chacun reste dans son périmètre.

## Rôles conseillés dans chaque équipe

Pour éviter le chaos, désignez (quitte à ce que les rôles se chevauchent un peu) :

| Rôle | Mission |
|---|---|
| **Dev principal** | le cœur du service (`app.py`, `db.py`) et sa conteneurisation |
| **Responsable contrat/doc** | tient le `README.md`, vérifie l'accord avec `2-contrats.md`, parle aux autres équipes |
| **Responsable tests** | prépare les `curl` / un jeu de données + quelques tests `pytest` |

> G1 a en plus un **coordinateur d'intégration** : il s'assure que tous les `service-*/` tournent ensemble dans le `docker-compose.yml` et passent par la gateway.

## Déroulé conseillé (2 séances, ~3h)

Court, donc tenez un cap. Repères (à adapter) :

| Quand | Tous ensemble / G1 | Chaque équipe service |
|---|---|---|
| **S1 - 0:00 à 0:20** | G1 anime : valider `2-contrats.md` (secret JWT, routes, table des `type`) | écouter, noter vos routes |
| **S1 - 0:20 à 0:40** | G1 boote le compose à vide (gateway + Postgres) | copier `service-template/` en `service-<nom>/`, `/health` répond |
| **S1 - 0:40 à la fin** | G1 branche chaque service au fur et à mesure | coder la **base** (la/les route(s) clés), tester au `curl` |
| **fin S1** | *objectif : tous les `/health` verts via la gateway, base fonctionnelle* | |
| **S2 - début** | | **étoffé** : JWT/rôles, 409, files d'actions |
| **S2 - milieu** | G1 fait passer le **scénario complet** (achat -> débit, ban...) | brancher les effets en jeu (files), bonus si le temps |
| **S2 - 0:30 avant la fin** | | **figer** : `README.md`, `group.md`, archive Moodle |

Règle d'or : une **route de base qui marche** vaut mieux que trois routes étoffées à moitié.

# Le starter

Un dossier `starter/` vous est fourni (voir son `README.md`) :

- `service-template/` : à **copier** pour créer votre service (Flask + ORM SQLAlchemy/SQLite + `auth.py` + `/health` + `/metrics` + `Dockerfile`).
- `Caddyfile` + `docker-compose.yml` : **squelettes** pour G1 à compléter (gateway, Postgres « Luanti » et serveur de jeu déjà là ; un modèle de service en commentaire, le reste à écrire).
- `luanti-db/` : un **Postgres** au vrai schéma Luanti (tables vides) qui tient lieu de la base du serveur de jeu.
- `mod-voxenfer/` : le **mod Luanti fourni** (illustratif, **non noté**), voir ci-dessous.

## Arborescence conseillée

**Chaque équipe G2-G7 produit UN seul dossier `service-<nom>/`** (copié depuis `service-template/`), de cette forme :

```
service-comptes/
├── app.py            <- vos routes
├── db.py             <- vos tables (ORM SQLAlchemy)
├── auth.py           <- charpente JWT à compléter (vérification du jeton)
├── requirements.txt
└── Dockerfile
```

Et **G1 assemble** l'écosystème (chaque `service-*/` y est posé à plat) :

```
voxenfer/
├── docker-compose.yml      <- G1 (un bloc par service, MEME JWT_SECRET)
├── Caddyfile               <- G1 (une route par service, dont /monde)
├── luanti-db/init.sql      <- fourni (Postgres au schema Luanti)
├── service-comptes/        <- G2
├── service-economie/       <- G3
├── service-boutique/       <- G4
├── service-classements/    <- G5
├── service-moderation/     <- G6
├── service-evenements/     <- G7
└── service-monde/          <- G1 (lecteur de la base Luanti)
```

# Le pont jeu <-> vos services (mod fourni, non noté)

Le starter contient un **mod Luanti** (`mod-voxenfer/`, **fourni, non noté** : vous n'y touchez pas, c'est du Lua, donc l'affaire de l'enseignant). Il fait la liaison **temps réel**, dans les **deux sens**, par HTTP via la gateway, comme un vrai serveur. Il **consomme votre API** : côté note, seul compte que **vos routes** (`2-contrats.md`) répondent juste, avec les bons codes.

**Sens 1 - le jeu appelle vos services** (sur événement) :

| Événement en jeu | Service appelé | Appel (via gateway) |
|---|---|---|
| Un joueur **se connecte** | comptes / moderation / evenements | `GET /comptes/joueurs/<pseudo>`, `GET /moderation/bannis/<pseudo>`, `GET /evenements/` |
| Un joueur **meurt** | classements | `POST /classements/scores` (le tueur marque) |
| `/acheter <id>` | boutique | `POST /boutique/acheter` (-> débite l'économie) |
| `/solde` | economie | `GET /economie/solde/<pseudo>` |
| `/signaler <joueur> <raison>` | moderation | `POST /moderation/signalements` |

**Sens 2 - vos services agissent dans le jeu** : un service ne peut pas « pousser » vers le jeu ; il **range ses décisions** et le mod vient les chercher (puis exécute) :

| Décision d'un service | Effet en jeu (par le mod) |
|---|---|
| boutique : achat validé | l'objet **apparaît dans l'inventaire** du joueur |
| evenements : tournoi lancé | les inscrits sont **téléportés** à l'arène |
| moderation : joueur banni / sanction | il est **expulsé** ; ou son inventaire est modifié |
| comptes : rôle / profession | **privilèges**, bonus physique, titre affichés |
| economie : solde | affiché en **HUD** |
| classements : top | affiché en **HUD** / couronne au n°1 |

> **Mécanique** (files d'actions, interrogation, acquittement) : tout est dans `2-contrats.md`. Faire tourner Luanti est **facultatif** : votre service se valide au `curl` et dans le `docker compose`.

# La gateway en détail (Caddy)

Tous les appels passent par **une seule porte**, la **gateway**, tenue par G1. On utilise **Caddy** comme *reverse proxy* : un serveur qui ne traite rien lui-même, mais **relaie** chaque requête vers le bon service interne. Comprendre son fonctionnement vous évite bien des « pourquoi mon service n'est pas joignable ? ».

Elle écoute sur `http://localhost:8080` (le seul port exposé sur la machine). Elle regarde le **préfixe** de l'URL, **le retire**, et transmet le reste au service correspondant, désigné par son **nom de conteneur** :

```caddy
:80 {
    handle_path /comptes/* {
        reverse_proxy service-comptes:5000
    }
    handle_path /boutique/* {
        reverse_proxy service-boutique:5000
    }
    # ... un bloc par service ...
}
```

Trois choses à retenir :

- **`handle_path` retire le préfixe.** `POST /comptes/login` arrive sur `service-comptes` en `POST /login`. **À l'intérieur, vos routes n'ont donc PAS le préfixe** (`/login`, pas `/comptes/login`). C'est le piège n°1.
- **`reverse_proxy service-comptes:5000`** vise le service par son **nom dans le `docker-compose.yml`** (DNS interne de Docker), **jamais** `localhost` : dans un conteneur, `localhost` c'est lui-même.
- **Les services ne sont pas exposés** sur la machine : seule la gateway l'est (port 8080). Pour parler à un service, on passe **toujours** par elle (entre services aussi : `http://service-economie:5000`).

**Pourquoi une gateway ?** Un point d'entrée unique pour tout l'écosystème : on y centralise le routage (et, en vrai, l'authentification, les logs, le TLS, la limitation de débit). Le client (un navigateur, un `curl`, le mod du jeu) ne connaît **qu'une** adresse, pas la liste des services internes.

**Un cas particulier** (cf. `2-contrats.md`) : quand une ressource porte le nom du service (les **événements**), la collection est à la **racine** du service, et `handle_path /evenements/*` ne capte pas le chemin nu `/evenements`. On ajoute donc `redir /evenements /evenements/` dans le `Caddyfile`.

# Sous le capot : Luanti, le mod, et la base PostgreSQL

Pour situer le terrain (utile surtout à G1, mais éclairant pour tous).

## Luanti, le moteur

Luanti est un **moteur de jeu voxel libre**, scriptable en **Lua** via des **mods**. Le serveur tourne **headless** (sans interface) et stocke son état dans des **backends configurables** : `auth` (les comptes du jeu), `player` (position, vie, inventaire), `map` (le monde). Par défaut c'est du SQLite local ; on l'a configuré en **PostgreSQL** pour `auth` et `player`, ce qui rend l'état du jeu **lisible en SQL** par un service.

## Le mod (`mod-voxenfer`)

C'est du **Lua** chargé par le serveur. Il s'accroche aux **événements** du jeu (`register_on_joinplayer`, `register_on_dieplayer`, `register_chatcommand`...) et peut faire des **appels HTTP sortants** via `minetest.request_http_api()` (à autoriser dans `minetest.conf`). Sa **contrainte** : uniquement du sortant, aucun serveur entrant. D'où :

- **jeu -> services** : sur événement, il appelle vos routes ;
- **services -> jeu** : il **interroge** vos files d'actions sur `globalstep` (toutes les ~N secondes), exécute en jeu (`kick_player`, `player:set_pos`, `inv:add_item`...), puis **acquitte**.

Vous n'écrivez **aucun Lua** : le mod est fourni et géré par l'enseignant.

## La base PostgreSQL de Luanti

Le **schéma est imposé par le moteur** (vous ne le concevez pas). Les tables qui nous intéressent :

| Table | Contient |
|---|---|
| `auth` | les comptes du jeu : `name`, mot de passe (haché SRP), `last_login` |
| `user_privileges` | les privilèges par compte |
| `player` | l'état sauvegardé : `name`, `posx/posy/posz`, `hp`, `breath`... |
| `player_metadata`, `player_inventories`, `player_inventory_items` | métadonnées et inventaire |

Important : le moteur **possède** ce schéma et y écrit **à son rythme** (périodiquement, à la déconnexion). On le **lit**, on ne l'**écrit jamais**.

## Le service d'observation (`service-monde`)

C'est l'**adaptateur** : un service qui **lit cette base en lecture seule** (SQL explicite, pas d'ORM : on s'adapte à un schéma existant) et l'**expose en HTTP/JSON** (`/joueurs`, `/positions/<pseudo>`...). **Un seul** service touche la base Luanti ; les autres consomment son API. C'est le pattern **anti-corruption layer** (sinon : tout le monde couplé à un schéma qu'on ne maîtrise pas, l'anti-pattern de la **base partagée**).

Limite à connaître : `service-monde` donne le **dernier état sauvegardé**, pas le temps réel. Pour la position **live** d'un joueur qui bouge, c'est le **mod** qui pousse l'info en direct. **Base = persisté ; mod = live.**

# Schéma d'architecture

```
   navigateur / curl                    joueur (client Luanti)
          |                                    |
          | HTTP                               | jeu (UDP 30000)
          v                                    v
   +-----------------+                  +------------------+
   | GATEWAY (Caddy) | <---- HTTP ----- | serveur Luanti   |
   |  localhost:8080 |   le mod :       | + mod-voxenfer   |
   +--------+--------+   events + files +--------+---------+
            |                                    |
            | /<service>/...                     | ecrit
            | (prefixe retire)                   | auth / player
            v                                    v
   +----------------------------------+   +----------------+
   | SERVICES (Flask, 1 base chacun)  |   |   luanti-db    |
   |                                  |   |  (PostgreSQL)  |
   | comptes   economie   boutique    |   +-------+--------+
   | classements  moderation          |           ^
   | evenements   service-monde       |           | lecture seule
   +----------------------------------+           |
                 service-monde  ------- lit -------+
```

- Une seule porte exposée sur la machine : la **gateway** (`:8080`). Les services et la base sont **internes** (joignables seulement par leur nom).
- **Tous** les services vérifient le **JWT** (émis par `comptes`).
- Seul appel inter-service **obligatoire** : `boutique -> economie` (`/debiter`).
- `service-monde` **lit** `luanti-db` en lecture seule (adaptateur) ; le **moteur Luanti y écrit**. Base = **persisté**, mod = **live**.

# Découpage fonctionnel

> Les **routes précises, les champs JSON et les codes** sont dans `2-contrats.md` : ci-dessous on décrit **le métier**, pas la signature exacte. Faites la **base** d'abord (elle suffit à valider le service), puis l'**étoffé**, puis le **bonus** si le temps le permet. Chaque service expose aussi `/health` et `/metrics` (du starter).

## G1 - Plateforme (gateway + orchestration + service-monde)

**Objectif.** Assembler tout l'écosystème, l'exposer par **une seule porte**, et fournir la **lecture de la base du jeu**. C'est l'équipe « infrastructure » : peu de métier propre, mais c'est vous qui faites **tenir l'ensemble**, et le projet entier se juge à votre `docker compose up`. Vous ne gérez ni comptes, ni messages, ni scores : vous **routez** et vous **exposez l'état du monde**.

**En jeu.** À la connexion, le mod salue le joueur et applique ses privilèges ; il lit aussi l'état du monde via votre `service-monde` (le mod parle à la gateway).

**Tâches.**
- *Base* : compléter le **`Caddyfile`** (un `handle_path` par service, dont `/monde`, qui retire le préfixe avant de transmettre) et le **`docker-compose.yml`** (un bloc par service + le Postgres, **même `JWT_SECRET` pour tous**, un volume par base) -- les deux sont fournis en squelette, avec un modèle de service en commentaire. Faire `docker compose up --build`, et vérifier que chaque `/<service>/health` répond via `http://localhost:8080`.
- *Étoffé* : **coder `service-monde`**, lecteur **lecture seule** de la base PostgreSQL de Luanti. Il expose qui s'est connecté, quand, où (position), avec quoi (inventaire). **Pas d'ORM ici** : on ne possède pas ce schéma (c'est celui du moteur), on **s'y adapte** en SQL explicite (psycopg2). Animer la mise au point des contrats en début de séance.
- *Bonus* : **carte web des positions** (une page servie par la gateway qui place les joueurs sur un plan, en lisant `service-monde`) ; une page d'accueil qui agrège les `/health` ; remplacer Caddy par **Traefik**.

**Tests à prévoir.** Tout le compose démarre (`docker compose ps` : tout `Up`) ; `curl :8080/comptes/health` et `:8080/monde/joueurs` répondent ; un service éteint n'empêche pas la gateway de répondre pour les autres (502 sur le seul absent).

**Conseils.**
- Faites booter le compose **au plus tôt**, même incomplet (gateway + Postgres), puis branchez les services au fur et à mesure qu'ils arrivent.
- Un service joint un autre par son **nom** (`http://service-economie:5000`), jamais par `localhost`.
- Pour `service-monde`, commencez par `GET /joueurs` (une requête `SELECT`, une liste JSON) avant les positions et l'inventaire.
- Vous êtes l'équipe **d'intégration** : c'est à vous d'aller voir les autres si un service ne se branche pas.

## G2 - service-comptes (identité, émet les jetons)

**Objectif.** Gérer les **comptes** des joueurs et l'**authentification**. Service **central** et **point de vérité** de l'identité : c'est vous qui **émettez les JWT** que **tous** les autres services vérifient. Vous ne gérez ni les pièces, ni les scores, ni les canaux : seulement **qui est qui** et **quels rôles** il a.

**En jeu.** À la connexion, le mod lit `GET /joueurs/<pseudo>` pour accueillir le joueur et **appliquer ses privilèges** selon son rôle.

**Tâches.**
- *Base* : **inscription** (`/register`, mot de passe **haché** avec `werkzeug.security`, **jamais en clair**), **connexion** (`/login`, qui renvoie un **JWT** signé contenant le `pseudo` et les `roles`), et **fiche publique** d'un joueur (`/joueurs/<pseudo>`).
- *Étoffé* : **lister** les joueurs ; **gérer les rôles** (accorder/retirer, sachant que **seul un admin** peut donner `moderateur`) ; **profil** modifiable par l'intéressé (titre, bio) ; **suppression** de compte (soi-même ou admin).
- *Bonus* : **professions** (`mineur` / `batisseur` / `guerrier`) : un attribut dont le mod tire des effets en jeu (privilèges, bonus physique, titre HUD) ; changement de mot de passe.

**Tests à prévoir.** `register` puis `login` -> on obtient un jeton ; **login avec un mauvais mot de passe -> 401** ; un non-admin qui tente d'accorder un rôle -> **403** ; un `register` en double -> **409** ; vérifier qu'aucun mot de passe n'est stocké ni renvoyé en clair.

**Conseils.**
- Le JWT, c'est **votre part** (TP 09) : complétez la **vérification** dans `auth.py` (`require_jwt` / `require_role`, partagée par tous les services) **et** écrivez l'**émission** du jeton à votre `/login` (`jwt.encode({...}, auth.SECRET, algorithm="HS256")`).
- Le jeton encode au minimum : le `pseudo`, les `roles` (respectez le payload du contrat, sinon les autres services ne vous comprendront pas).
- Un **admin initial** doit exister au démarrage (sinon personne ne peut promouvoir personne) : amorcez-le et **documentez** comment l'obtenir.

## G3 - service-economie (les pièces)

**Objectif.** La **monnaie** du serveur : un solde de pièces par joueur, qu'on peut créditer, débiter, transférer. Vous ne savez pas ce qu'on **achète** (c'est la boutique) : vous savez seulement **débiter** et **créditer**.

**En jeu.** La commande `/solde` affiche les pièces (le mod les met en **HUD**) ; et **tout achat passe par vous** : la boutique appelle votre `/debiter`.

**Tâches.**
- *Base* : consulter le **solde** d'un joueur ; **créditer** (réservé **admin**) ; **débiter** (jeton requis), avec un **`409` si le solde est insuffisant** (on ne passe jamais en négatif).
- *Étoffé* : **transférer** des pièces d'un joueur à un autre (l'émetteur est le `pseudo` du jeton, pas un champ libre) ; **historique** des mouvements d'un joueur.
- *Bonus* : une petite **taxe** sur les transferts ; un classement des plus riches.

**Tests à prévoir.** Créditer puis lire le solde ; **débiter plus que le solde -> 409** ; débiter un montant négatif ou non entier -> **400** ; `crediter` sans rôle admin -> **403** ; un transfert vide bien le compte source et remplit la cible.

**Conseils.**
- Le **409 sur solde insuffisant** est le cœur du service : écrivez-le et testez-le tôt.
- Validez les entrées (montant entier > 0) et répondez **400** sinon, plutôt que de laisser planter.
- Pensez « transaction atomique » pour le transfert : on débite **et** on crédite, ou rien.

## G4 - service-boutique (les objets, livrés en jeu) - service vitrine

**Objectif.** Un **catalogue** d'objets et l'**achat** (payé via l'économie, livré en jeu). C'est le service **vitrine** du projet : le **seul appel inter-service obligatoire** est ici (`acheter` -> `economie/debiter`), et l'effet en jeu (un objet qui apparaît dans l'inventaire) est le plus spectaculaire.

**En jeu.** `/acheter <id>` **débite l'économie** puis **l'objet acheté apparaît dans l'inventaire** du joueur (le mod vide votre file de livraisons). Un objet du catalogue = un **item Luanti réel** (ex. `default:pick_steel 1`).

**Tâches.**
- *Base* : exposer le **catalogue** (liste, ajout réservé **admin**) ; **acheter** un objet, ce qui **appelle `economie /debiter`** et **gère le 503** si l'éco est injoignable (on ne perd pas l'objet, on signale « réessayez »).
- *Étoffé* : la **file de livraisons** (que le mod vient lire puis acquitter) ; l'**inventaire** des objets achetés par un joueur.
- *Bonus* : **remises** ; **stock limité** (`409` si rupture) ; livraison par **drop au sol** dans le monde (`type:"spawn_item"`) plutôt que dans l'inventaire.

**Tests à prévoir.** Acheter avec un solde suffisant -> **201** + débit côté éco ; acheter sans pièces -> **409** (relayé depuis l'éco) ; acheter en ayant **coupé** `service-economie` -> **503** (et pas un 500) ; après achat, la file de livraisons contient bien l'objet pour le bon joueur.

**Conseils.**
- Encadrez l'appel `requests` à l'éco par un `try/except` -> **503** ; c'est noté (robustesse, TP 10).
- La file de livraisons = une simple table avec un statut `en_attente` / `livre` (pur ORM, TP 12). Le mod la lit, livre, puis appelle votre route d'acquittement.
- Stockez l'**itemstring Luanti** (`default:...`) directement : le mod le passe tel quel à `inv:add_item`.

## G5 - service-classements (les scores)

**Objectif.** Les **scores** et le **classement** des joueurs. Vous ne savez pas *pourquoi* un joueur marque (c'est le jeu qui le dit) : vous **enregistrez** et vous **classez**.

**En jeu.** À chaque **mort d'un joueur**, le mod envoie `POST /scores` (le tueur marque des points). Votre `/classement` est le tableau d'honneur du serveur, affiché en **HUD** (et une couronne au n°1).

**Tâches.**
- *Base* : **ajouter des points** à un joueur (jeton requis) ; consulter le **score** d'un joueur ; le **classement** (trié par points décroissants).
- *Étoffé* : le **top N** (`/classement/top/<n>`).
- *Bonus* : classements **par période** (jour / semaine) ; **pagination** ; **succès** ou badges.

**Tests à prévoir.** Ajouter des points deux fois -> le total **cumule** ; le classement est bien **trié** (le plus haut en tête) ; demander le score d'un inconnu renvoie un résultat propre (0 ou 404, à décider et à documenter) ; `POST /scores` sans jeton -> **401**.

**Conseils.**
- Le classement, c'est un `ORDER BY points DESC` : ne sur-architecturez pas.
- Décidez tôt si `POST /scores` **ajoute** des points ou **fixe** un total, et écrivez-le dans le contrat (le mod, lui, **ajoute**).

## G6 - service-moderation (signalements, bans, inventaires)

**Objectif.** **Signalements**, **bannissements** et **pouvoirs de modération en jeu**. Vous tenez la **porte d'entrée** du serveur : c'est votre liste de bannis que le mod consulte pour expulser. Vous ne gérez pas les comptes (juste qui est sanctionné).

**En jeu.** La commande `/signaler` crée un signalement ; un joueur **banni est expulsé** (le mod relit en boucle votre liste de bannis et kicke les connectés) ; un modérateur peut **confisquer** ou **donner** un objet (via une file d'actions).

**Tâches.**
- *Base* : **créer un signalement** (tout joueur) et les **lister** (modérateur) ; **bannir** un joueur (modérateur) ; **savoir si un joueur est banni** (`/bannis/<pseudo>`, route ouverte que le mod interroge à la connexion).
- *Étoffé* : la **liste** des bannis (pour la réconciliation du mod) ; **motif** et **durée** ; **lever** un ban ; une **file d'actions** que le mod exécute en jeu (`confisquer` / `donner_objet` / `spawn_item`).
- *Bonus* : **historique** de modération (qui a banni qui, quand, pourquoi).

**Tests à prévoir.** Bannir un joueur puis `/bannis/<pseudo>` -> `banni: true` ; lever le ban -> `banni: false` ; un **joueur** (non modérateur) qui tente de bannir -> **403** ; créer un signalement sans jeton -> **401** ; la liste des bannis est bien un tableau exploitable par le mod.

**Conseils.**
- `GET /bannis` (la liste) est ce que le mod lit **en boucle** : renvoyez une liste simple, stable.
- Distinguez bien **401** (« je ne sais pas qui vous êtes ») et **403** (« je sais, mais vous n'êtes pas modérateur »).
- La file d'actions suit le même patron que la boutique (statut `en_attente` / `fait`).

## G7 - service-evenements (tournois, téléport)

**Objectif.** Les **événements** du serveur (tournois, annonces) et les **inscriptions**. Vous rythmez la vie du serveur ; au lancement d'un tournoi, vous **déclenchez la téléportation** des inscrits vers l'arène.

**En jeu.** À la connexion, le mod lit la liste des événements et **annonce le prochain** ; au **lancement** d'un tournoi, les inscrits sont **téléportés à l'arène** (via une file de téléports que le mod exécute).

**Tâches.**
- *Base* : **lister** les événements ; en **créer** (admin) ; **s'inscrire** (jeton requis) ; lister les **inscrits**.
> **Cas particulier de routage** : ici la ressource porte le **nom du service**, donc vos routes sont à la **racine** (`/`, `/<id>/inscription`...), pas `/evenements`. Via la gateway, ça devient `/evenements/...` (voir `2-contrats.md`).
- *Étoffé* : une **arène** (coordonnées) et un nombre de **places** (`409` si complet) ; un **lancement** qui remplit la **file de téléportations** (que le mod vide, puis acquitte).
- *Bonus* : **dates** de début/fin ; **statut** automatique (à venir / en cours / terminé) ; **rappels**.

**Tests à prévoir.** Créer un événement (admin) ; s'inscrire deux fois -> la 2e est refusée (déjà inscrit) ; s'inscrire à un événement **complet** -> **409** ; après `lancer`, la file de téléportations contient bien chaque inscrit avec les coordonnées de l'arène ; créer un événement sans être admin -> **403**.

**Conseils.**
- Attention au **routage racine** (voir l'encadré ci-dessus et `2-contrats.md`) : c'est le piège classique de ce service.
- Les coordonnées d'arène sont des nombres (`x`, `y`, `z`) : le mod les passe à `player:set_pos`.

# Rendu attendu (par équipe)

Dépôt (Git **et** archive sur Moodle), contenant :

- Votre service complet : `app.py`, `db.py`, `auth.py`, `requirements.txt`, `Dockerfile` (G1 : `Caddyfile` + `docker-compose.yml` + `service-monde`).
- Un **`README.md`** : objectif du service, comment le lancer, **exemples d'appel** (`curl` avec un jeton).
- Votre **`2-contrats.md` complété** : au moins la section de **votre** service (routes étoffées, champs JSON exacts). Le contrat partagé est un livrable, pas un acquis.
- Un **`group.md`** : qui a fait quoi + **journal heure par heure** (ce qui a avancé, ce qui a coincé). Exemple :
  ```
  9h00  squelette + /register (Alice)
  9h40  500 sur /acheter, on parle au groupe éco (Bob)
  10h05 réglé : il manquait le 503 quand l'éco est coupée
  ```
- **Bonus** : tests `pytest`, documentation des routes.

**Archive Moodle** : `groupe-2-comptes.tar.gz`, etc., avant **12h00 le 17/06**.

# Barème indicatif (/20 par équipe)

| Critère | Points |
|---|---|
| Routes minimales fonctionnelles | /7 |
| JWT et contrôle d'accès (rôles, écritures protégées) | /3 |
| Robustesse (codes d'erreur clairs, 503 si dépendance KO) | /2 |
| `/health` + `/metrics` | /1 |
| Dockerisation (build + run) | /2 |
| Intègre dans le `docker compose` commun (joignable via la gateway) | /2 |
| Documentation : README clair + exemples d'appel + section `2-contrats.md` complétée | /2 |
| `group.md` (rôles + journal) | /1 |
| Bonus / initiative (files d'actions, professions, carte, transferts, Traefik...) | +2 |

> Des points sont retirés pour un service mal séparé (touche au périmètre d'un autre), des routes instables, ou un service qui ne démarre pas dans le compose.

# Glossaire

- **Gateway** : la porte d'entrée unique (Caddy) ; route les requêtes vers les services internes.
- **Reverse proxy** : un serveur qui **relaie** les requêtes vers d'autres serveurs, au lieu de les traiter lui-même.
- **JWT** : un jeton **signé** (identité + rôles) que chaque service vérifie localement, sans appel externe.
- **Rôle** : `joueur` < `moderateur` < `admin` ; porté par le JWT.
- **ORM** : *Object-Relational Mapper* (SQLAlchemy) ; on manipule des objets Python, il écrit le SQL.
- **Stateless** : chaque requête se suffit à elle-même ; le serveur ne garde pas de session.
- **Idempotent** : rejouer l'opération donne le même résultat (`PUT`, `DELETE` ; pas `POST`).
- **Healthcheck** : la route `/health` qu'un superviseur interroge pour savoir si le service est vivant.
- **File d'actions** : une liste d'actions à exécuter en jeu, que le mod vient lire puis **acquitter**.
- **Acquittement** : marquer une action « faite » pour qu'elle ne soit pas rejouée.
- **Réconciliation** : relire un état (ex. la liste des bannis) et agir, plutôt que gérer une file (idempotent).
- **Adaptateur (anti-corruption layer)** : un service unique qui isole un système externe (la base Luanti) derrière une API propre.
- **Headless** : un serveur sans interface graphique.

**Codes HTTP** : **200** OK · **201** créé · **400** requête mal formée · **401** non authentifié · **403** authentifié mais droit insuffisant · **404** introuvable · **409** conflit (doublon, solde insuffisant) · **503** une dépendance est injoignable.

# Et voilà !

Vous avez construit, brique par brique, tout ce qu'il faut (TP 08 à 12). Le projet, c'est **votre** brique dans un écosystème commun, branché sur un vrai jeu. Coordonnez-vous, respectez les contrats, faites tourner Voxenfer... et soyez plus fiables que Gilbert. Bon projet !
