"""db.py — Charpente ORM (SQLAlchemy sur SQLite) + modèles de service-comptes.

Une base SQLite PROPRE au service (un simple fichier). On manipule des objets
Python, l'ORM écrit le SQL. La charpente (engine, Session, Base) est posée ici ;
le modèle métier `Joueur` est défini dessous.
"""

import os

from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import declarative_base, sessionmaker

# Fichier SQLite propre au service (surchargé en test via DB_PATH=:memory:).
CHEMIN_DB = os.environ.get("DB_PATH", "comptes.db")
if CHEMIN_DB == ":memory:":
    URL_DB = "sqlite://"
else:
    URL_DB = f"sqlite:///{CHEMIN_DB}"

engine = create_engine(URL_DB, connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)
Base = declarative_base()


class Joueur(Base):
    """Un compte. Les rôles sont stockés en CSV (« joueur,moderateur »)."""

    __tablename__ = "joueurs"

    id = Column(Integer, primary_key=True)
    pseudo = Column(String, unique=True, nullable=False, index=True)
    # JAMAIS le mot de passe en clair : on stocke le haché werkzeug.
    mot_de_passe_hache = Column(String, nullable=False)
    roles = Column(String, nullable=False, default="joueur")
    # Profil (étoffé) + profession (bonus).
    titre = Column(String, nullable=True)
    bio = Column(Text, nullable=True)
    profession = Column(String, nullable=True)

    # --- helpers de (dé)sérialisation ---

    def liste_roles(self):
        return [r for r in (self.roles or "").split(",") if r]

    def definir_roles(self, roles):
        # On déduplique en conservant l'ordre, et on retire les vides.
        propres = []
        for r in roles:
            if r and r not in propres:
                propres.append(r)
        self.roles = ",".join(propres)

    def profil(self):
        return {"titre": self.titre, "bio": self.bio, "profession": self.profession}

    def vers_public(self):
        """Fiche PUBLIQUE — ne contient jamais le mot de passe."""
        return {
            "pseudo": self.pseudo,
            "roles": self.liste_roles(),
            "profil": self.profil(),
        }


def init_db():
    """Crée les tables si besoin (idempotent)."""
    Base.metadata.create_all(engine)
