"""Base de données du service, via un ORM : SQLAlchemy.

Auteur : Philippe ROUSSILLE <roussille@3il.fr>

Un ORM (Object-Relational Mapper) fait le pont entre des OBJETS Python et des
LIGNES de table : vous manipulez des objets, l'ORM écrit le SQL à votre place.
Principe micro-services : ce service possède SA base, un simple fichier SQLite
(inclus dans Python, aucun serveur à installer). Le chemin passe par une variable
d'environnement pour pouvoir le mettre dans un volume Docker (voir
docker-compose.yml). Vous avez découvert ce pattern au TP 12.
"""

import os
from datetime import datetime

from sqlalchemy import DateTime, String, create_engine, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

DB_PATH = os.environ.get("DB_PATH", "data.db")

# Le moteur : il sait parler à CETTE base (ici un fichier SQLite).
engine = create_engine(f"sqlite:///{DB_PATH}")

# Session : la "poignée" par laquelle on lit/écrit. On en ouvre une par requête.
Session = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    """Classe de base commune à tous vos modèles."""


# --- Modèles : Comptes, Profils, Rôles ------------------------------------


class Joueur(Base):
    """Compte d'un joueur : identifiant et mot de passe haché."""

    __tablename__ = "joueurs"

    id: Mapped[int] = mapped_column(primary_key=True)
    pseudo: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    mot_de_passe_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )


class Profil(Base):
    """Profil public du joueur : titre, bio, profession."""

    __tablename__ = "profils"

    id: Mapped[int] = mapped_column(primary_key=True)
    joueur_id: Mapped[int] = mapped_column(nullable=False, index=True)
    pseudo: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    titre: Mapped[str] = mapped_column(String(100), nullable=True, default="")
    bio: Mapped[str] = mapped_column(String(500), nullable=True, default="")
    profession: Mapped[str | None] = mapped_column(
        String(50), nullable=True, default=None
    )  # mineur, batisseur, guerrier


class Role(Base):
    """Rôles d'un joueur : joueur, moderateur, admin."""

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    joueur_id: Mapped[int] = mapped_column(nullable=False, index=True)
    pseudo: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    role: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # joueur, moderateur, admin


def init():
    """Crée les tables si elles n'existent pas. À APPELER au démarrage."""
    Base.metadata.create_all(engine)
