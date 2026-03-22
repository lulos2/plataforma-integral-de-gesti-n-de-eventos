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


class Rol(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String, nullable=False, unique=True, index=True)  # admin | operador | auditor | etc
    permissions = relationship("Permission", secondary=role_permissions, lazy="selectin")


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

    rol_id = Column(Integer, ForeignKey("roles.id"), nullable=False, index=True)
    rol = relationship("Rol")

    # Allows a strict "super-admin only" policy for privilege management.
    is_superuser = Column(Boolean, nullable=False, server_default="false", index=True)

    activo = Column(Boolean, nullable=False, server_default="true", index=True)
    fecha_creacion = Column(DateTime(timezone=True), server_default=func.now(), index=True)
