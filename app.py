import os
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
from jose import JWTError, jwt
from sqlalchemy.orm import Session

import models
from database import engine, get_db

# Cria as tabelas na base de dados PostgreSQL automaticamente se não existirem
models.Base.metadata.create_all(bind=engine)

# CONFIGURAÇÕES DE SEGURANÇA
SECRET_KEY = "sua_chave_secreta_super_segura_aqui"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120

app = FastAPI(title="SIGA-Íris API")

# CONFIGURAÇÃO DE CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# ---------------------------------------------------------
# POVOAMENTO INICIAL DO BANCO DE DADOS (SEED)
# ---------------------------------------------------------
@app.on_event("startup")
def startup_db_seed():
    db = next(get_db())
    
    # 1. Inserir Cursos Iniciais
    if db.query(models.Curso).count() == 0:
        cursos_iniciais = [
            models.Curso(id=1, nome="Engenharia Informática", tipo="Licenciatura"),
            models.Curso(id=2, nome="Administração de Empresas", tipo="Licenciatura"),
            models.Curso(id=3, nome="Medicina Geral", tipo="Mestrado Integral")
        ]
        db.add_all(cursos_iniciais)
        db.commit()

    # 2. Inserir Utilizadores Iniciais
    if db.query(models.Usuario).count() == 0:
        admin = models.Usuario(
            nome="Administrador do Sistema",
            email="admin@univ.br",
            senha="123",
            perfil="admin"
        )
        docente = models.Usuario(
            nome="Prof. Doutor Carlos",
            email="docente@univ.br",
            senha="123",
            perfil="docente",
            curso_id=1
        )
        estudante = models.Usuario(
            estudante_id="EST01",
            nome="João Silva",
            email="estudante@univ.br",
            senha="123",
            perfil="estudante",
            curso_id=1,
            bloqueado_financeiro=False
        )
        db.add_all([admin, docente, estudante])
        db.commit()
        db.refresh(estudante)

        # Inserir Notas Iniciais para o estudante de teste
        notas_iniciais = [
            models.Nota(estudante_id=estudante.id, semestre=1, disciplina="Programação I", teste=14.0, trabalho=16.0, exame=15.0, media=15.0),
            models.Nota(estudante_id=estudante.id, semestre=1, disciplina="Matemática Discreta", teste=12.0, trabalho=10.0, exame=11.0, media=11.0),
            models.Nota(estudante_id=estudante.id, semestre=2, disciplina="Algoritmos e Estruturas de Dados", teste=0.0, trabalho=0.0, exame=0.0, media=0.0),
            models.Nota(estudante_id=estudante.id, semestre=2, disciplina="Base de Dados", teste=0.0, trabalho=0.0, exame=0.0, media=0.0)
        ]
        db.add_all(notas_iniciais)
        db.commit()

# ---------------------------------------------------------
# MODELOS PYDANTIC
# ---------------------------------------------------------
class PublicarNotaSchema(BaseModel):
    estudante_id: str
    semestre: int
    disciplina: str
    teste: float
    trabalho: float
    exame: float

class NovoUsuarioSchema(BaseModel):
    nome: str
    email: str
    senha: str
    perfil: str
    curso_id: Optional[int] = None

# ---------------------------------------------------------
# FUNÇÕES AUXILIARES DE TOKEN E AUTENTICAÇÃO
# ---------------------------------------------------------
def criar_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def obter_usuario_atual(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Token inválido.")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token expirado ou inválido.")

    usuario = db.query(models.Usuario).filter(models.Usuario.email == email).first()
    if usuario is None:
        raise HTTPException(status_code=401, detail="Utilizador não encontrado.")
    return usuario

# ---------------------------------------------------------
# ROTAS DA API
# ---------------------------------------------------------
@app.get("/")
def root():
    return {"status": "API SIGA-Íris com PostgreSQL activa e funcional!"}

@app.post("/api/auth/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter(models.Usuario.email == form_data.username).first()
    if not usuario or usuario.senha != form_data.password:
        raise HTTPException(status_code=400, detail="Credenciais de acesso incorretas.")
    
    token = criar_token({"sub": usuario.email, "perfil": usuario.perfil})
    return {
        "access_token": token,
        "token_type": "bearer",
        "perfil": usuario.perfil,
        "nome": usuario.nome
    }

@app.get("/api/cursos")
def listar_cursos(db: Session = Depends(get_db)):
    return db.query(models.Curso).all()

@app.get("/api/docente/disciplinas")
def obter_disciplinas_docente(user: models.Usuario = Depends(obter_usuario_atual)):
    if user.perfil != "docente":
        raise HTTPException(status_code=403, detail="Acesso exclusivo para docentes.")
    
    # Disciplinas padrão associadas ao docente
    disciplinas = {
        "1": ["Programação I", "Matemática Discreta"],
        "2": ["Algoritmos e Estruturas de Dados", "Base de Dados"]
    }
    return {"disciplinas": disciplinas}

@app.post("/api/docente/publicar-nota")
def publicar_nota(payload: PublicarNotaSchema, user: models.Usuario = Depends(obter_usuario_atual), db: Session = Depends(get_db)):
    if user.perfil != "docente":
        raise HTTPException(status_code=403, detail="Acesso exclusivo para docentes.")
    
    estudante = db.query(models.Usuario).filter(
        models.Usuario.estudante_id == payload.estudante_id,
        models.Usuario.perfil == "estudante"
    ).first()

    if not estudante:
        raise HTTPException(status_code=404, detail="Estudante não encontrado com esse ID.")

    media = round((payload.teste + payload.trabalho + payload.exame) / 3, 1)

    # Procura se a nota da disciplina já existe na base de dados
    nota_existente = db.query(models.Nota).filter(
        models.Nota.estudante_id == estudante.id,
        models.Nota.semestre == payload.semestre,
        models.Nota.disciplina == payload.disciplina
    ).first()

    if nota_existente:
        nota_existente.teste = payload.teste
        nota_existente.trabalho = payload.trabalho
        nota_existente.exame = payload.exame
        nota_existente.media = media
    else:
        nova_nota = models.Nota(
            estudante_id=estudante.id,
            semestre=payload.semestre,
            disciplina=payload.disciplina,
            teste=payload.teste,
            trabalho=payload.trabalho,
            exame=payload.exame,
            media=media
        )
        db.add(nova_nota)

    db.commit()
    return {"mensagem": f"Notas de {payload.disciplina} publicadas com sucesso para {estudante.nome}!"}

@app.get("/api/estudante/grade-notas")
def obter_grade_estudante(user: models.Usuario = Depends(obter_usuario_atual), db: Session = Depends(get_db)):
    if user.perfil != "estudante":
        raise HTTPException(status_code=403, detail="Acesso exclusivo para estudantes.")
    
    if user.bloqueado_financeiro:
        return {
            "bloqueado_financeiro": True,
            "mensagem": "Acesso suspenso por pendências financeiras. Dirija-se à secretaria."
        }

    curso_nome = user.curso.nome if user.curso else "Não Atribuído"

    # Buscar todas as notas registradas no banco para o estudante
    notas_db = db.query(models.Nota).filter(models.Nota.estudante_id == user.id).all()

    grade = {1: [], 2: []}
    for n in notas_db:
        if n.semestre in grade:
            grade[n.semestre].append({
                "disciplina": n.disciplina,
                "teste": n.teste,
                "trabalho": n.trabalho,
                "exame": n.exame,
                "media": n.media
            })

    return {
        "bloqueado_financeiro": False,
        "curso": curso_nome,
        "grade": grade
    }

@app.post("/api/admin/cadastrar-usuario")
def cadastrar_usuario(payload: NovoUsuarioSchema, user: models.Usuario = Depends(obter_usuario_atual), db: Session = Depends(get_db)):
    if user.perfil != "admin":
        raise HTTPException(status_code=403, detail="Acesso restrito ao administrador.")
    
    if db.query(models.Usuario).filter(models.Usuario.email == payload.email).first():
        raise HTTPException(status_code=400, detail="E-mail já se encontra registado.")

    total_usuarios = db.query(models.Usuario).count()
    novo_usuario = models.Usuario(
        nome=payload.nome,
        email=payload.email,
        senha=payload.senha,
        perfil=payload.perfil,
        curso_id=payload.curso_id
    )

    if payload.perfil == "estudante":
        novo_usuario.estudante_id = f"EST{total_usuarios + 1:02d}"
        novo_usuario.bloqueado_financeiro = False

    db.add(novo_usuario)
    db.commit()
    return {"mensagem": f"Utilizador {payload.nome} cadastrado com sucesso!"}
