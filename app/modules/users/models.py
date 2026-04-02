from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer, String, Boolean, DateTime, Text, Table
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database.base import Base


role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


class Rol(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String, nullable=False, unique=True, index=True)  # admin | operador | auditor | etc
    permissions = relationship("Permission", secondary=role_permissions, lazy="selectin")
    users = relationship("Usuario", secondary=user_roles, back_populates="roles", lazy="selectin")


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String, nullable=False, unique=True, index=True)
    description = Column(String, nullable=True)


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, nullable=False, unique=True, index=True)
    email = Column(String, nullable=True, unique=True, index=True)
    nombre = Column(String, nullable=True)
    apellido = Column(String, nullable=True)
    # Nullable for backwards compatibility if the table already existed.
    password_hash = Column(Text, nullable=True)

    roles = relationship("Rol", secondary=user_roles, back_populates="users", lazy="selectin")

    activo = Column(Boolean, nullable=False, server_default="true", index=True)
    fecha_creacion = Column(DateTime(timezone=True), server_default=func.now(), index=True)
