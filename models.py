from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

class Curso(Base):
    __tablename__ = "cursos"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    tipo = Column(String, nullable=False)

    usuarios = relationship("Usuario", back_populates="curso")


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    estudante_id = Column(String, unique=True, nullable=True)
    nome = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    senha = Column(String, nullable=False)
    perfil = Column(String, nullable=False)
    bloqueado_financeiro = Column(Boolean, default=False)
    
    curso_id = Column(Integer, ForeignKey("cursos.id"), nullable=True)
    curso = relationship("Curso", back_populates="usuarios")

    notas = relationship("Nota", back_populates="estudante")


class Nota(Base):
    __tablename__ = "notas"

    id = Column(Integer, primary_key=True, index=True)
    estudante_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    semestre = Column(Integer, nullable=False)
    disciplina = Column(String, nullable=False)
    teste = Column(Float, default=0.0)
    trabalho = Column(Float, default=0.0)
    exame = Column(Float, default=0.0)
    media = Column(Float, default=0.0)

    estudante = relationship("Usuario", back_populates="notas")
