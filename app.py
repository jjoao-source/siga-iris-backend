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

models.Base.metadata.create_all(bind=engine)

SECRET_KEY = "sua_chave_secreta_super_segura_aqui"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120

app = FastAPI(title="SIGA-Íris API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Função auxiliar para calcular estado do estudante segundo normas académicas de Moçambique
def calcular_desempenho(t1: float, t2: float, trab: float, ex: Optional[float] = None, rec: Optional[float] = None):
    mf = round((t1 + t2 + trab) / 3, 1)
    
    if mf < 10.0:
        return mf, mf, "Excluído"
    
    if ex is None:
        return mf, mf, "Admitido"
    
    if ex >= 10.0:
        media_final = round((mf + ex) / 2, 1)
        return mf, media_final, "Aprovado"
    
    if rec is None:
        return mf, mf, "Recorrência"
    
    if rec >= 10.0:
        media_final = round((mf + rec) / 2, 1)
        return mf, media_final, "Aprovado na Recorrência"
    
    return mf, mf, "Reprovado"

@app.on_event("startup")
def startup_db_seed():
    db = next(get_db())
    if db.query(models.Curso).count() == 0:
        db.add_all([
            models.Curso(id=1, nome="Engenharia Informática", tipo="Licenciatura"),
            models.Curso(id=2, nome="Administração de Empresas", tipo="Licenciatura")
        ])
        db.commit()

    if db.query(models.Usuario).count() == 0:
        admin = models.Usuario(nome="Administrador", email="admin@univ.br", senha="123", perfil="admin")
        docente = models.Usuario(nome="Prof. Doutor Carlos", email="docente@univ.br", senha="123", perfil="docente", curso_id=1)
        estudante = models.Usuario(estudante_id="EST01", nome="João Silva", email="estudante@univ.br", senha="123", perfil="estudante", curso_id=1)
        db.add_all([admin, docente, estudante])
        db.commit()
        db.refresh(estudante)

        mf, mf_final, estado = calcular_desempenho(14.0, 15.0, 16.0, 15.0)
        db.add(models.Nota(
            estudante_id=estudante.id, semestre=1, disciplina="Programação I",
            teste1=14.0, teste2=15.0, trabalho=16.0, media_frequencia=mf,
            exame=15.0, media_final=mf_final, estado=estado
        ))
        db.commit()

class PublicarNotaSchema(BaseModel):
    estudante_id: str
    semestre: int
    disciplina: str
    teste1: float
    teste2: float
    trabalho: float
    exame: Optional[float] = None
    recorrencia: Optional[float] = None

class NovoUsuarioSchema(BaseModel):
    nome: str
    email: str
    senha: str
    perfil: str
    curso_id: Optional[int] = None

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

@app.get("/")
def root():
    return {"status": "API SIGA-Íris com regras de avaliação moçambicanas activa!"}

@app.post("/api/auth/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter(models.Usuario.email == form_data.username).first()
    if not usuario or usuario.senha != form_data.password:
        raise HTTPException(status_code=400, detail="Credenciais de acesso incorretas.")
    
    token = criar_token({"sub": usuario.email, "perfil": usuario.perfil})
    return {"access_token": token, "token_type": "bearer", "perfil": usuario.perfil, "nome": usuario.nome}

@app.get("/api/cursos")
def listar_cursos(db: Session = Depends(get_db)):
    return db.query(models.Curso).all()

@app.get("/api/docente/disciplinas")
def obter_disciplinas_docente(user: models.Usuario = Depends(obter_usuario_atual)):
    if user.perfil != "docente":
        raise HTTPException(status_code=403, detail="Acesso exclusivo para docentes.")
    return {"disciplinas": {"1": ["Programação I", "Matemática Discreta"], "2": ["Algoritmos", "Base de Dados"]}}

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

    mf, mf_final, estado = calcular_desempenho(
        payload.teste1, payload.teste2, payload.trabalho, payload.exame, payload.recorrencia
    )

    nota_existente = db.query(models.Nota).filter(
        models.Nota.estudante_id == estudante.id,
        models.Nota.semestre == payload.semestre,
        models.Nota.disciplina == payload.disciplina
    ).first()

    if nota_existente:
        nota_existente.teste1 = payload.teste1
        nota_existente.teste2 = payload.teste2
        nota_existente.trabalho = payload.trabalho
        nota_existente.media_frequencia = mf
        nota_existente.exame = payload.exame
        nota_existente.recorrencia = payload.recorrencia
        nota_existente.media_final = mf_final
        nota_existente.estado = estado
    else:
        nova_nota = models.Nota(
            estudante_id=estudante.id,
            semestre=payload.semestre,
            disciplina=payload.disciplina,
            teste1=payload.teste1,
            teste2=payload.teste2,
            trabalho=payload.trabalho,
            media_frequencia=mf,
            exame=payload.exame,
            recorrencia=payload.recorrencia,
            media_final=mf_final,
            estado=estado
        )
        db.add(nova_nota)

    db.commit()
    return {"mensagem": f"Notas de {payload.disciplina} atualizadas com sucesso! Estado: {estado}"}

@app.get("/api/estudante/grade-notas")
def obter_grade_estudante(user: models.Usuario = Depends(obter_usuario_atual), db: Session = Depends(get_db)):
    if user.perfil != "estudante":
        raise HTTPException(status_code=403, detail="Acesso exclusivo para estudantes.")
    
    if user.bloqueado_financeiro:
        return {"bloqueado_financeiro": True, "mensagem": "Acesso suspenso por pendências financeiras."}

    curso_nome = user.curso.nome if user.curso else "Não Atribuído"
    notas_db = db.query(models.Nota).filter(models.Nota.estudante_id == user.id).all()

    grade = {1: [], 2: []}
    for n in notas_db:
        if n.semestre in grade:
            grade[n.semestre].append({
                "disciplina": n.disciplina,
                "teste1": n.teste1,
                "teste2": n.teste2,
                "trabalho": n.trabalho,
                "media_frequencia": n.media_frequencia,
                "exame": n.exame,
                "recorrencia": n.recorrencia,
                "media_final": n.media_final,
                "estado": n.estado
            })

    return {"bloqueado_financeiro": False, "curso": curso_nome, "grade": grade}

# ROTA DE ESTATÍSTICAS PARA OS CARTÕES DO ADMIN
@app.get("/api/admin/stats")
def obter_estatisticas_admin(user: models.Usuario = Depends(obter_usuario_atual), db: Session = Depends(get_db)):
    if user.perfil != "admin":
        raise HTTPException(status_code=403, detail="Acesso restrito ao administrador.")
    
    docentes_count = db.query(models.Usuario).filter(models.Usuario.perfil == "docente").count()
    estudantes_count = db.query(models.Usuario).filter(models.Usuario.perfil == "estudante").count()
    
    return {
        "total_docentes": docentes_count,
        "total_estudantes": estudantes_count,
        "aprovacao_media": "84.2%",
        "propinas_regularizadas": "91.5%"
    }

# ROTAS PARA LISTAGEM E CADASTRO DE UTILIZADORES (ADMIN)
@app.get("/api/admin/usuarios")
@app.get("/api/usuarios")
def listar_usuarios(user: models.Usuario = Depends(obter_usuario_atual), db: Session = Depends(get_db)):
    if user.perfil != "admin":
        raise HTTPException(status_code=403, detail="Acesso restrito ao administrador.")
    
    usuarios = db.query(models.Usuario).all()
    resultado = []
    
    for u in usuarios:
        curso_nome = u.curso.nome if u.curso else "N/A"
        id_visivel = u.estudante_id if u.perfil == "estudante" else f"DOC{u.id:02d}" if u.perfil == "docente" else f"ADM{u.id:02d}"
        
        resultado.append({
            "id": id_visivel,
            "nome": u.nome,
            "email": u.email,
            "perfil": u.perfil,
            "curso": curso_nome,
            "bloqueado_financeiro": u.bloqueado_financeiro
        })
        
    return resultado

@app.post("/api/admin/cadastrar-usuario")
@app.post("/api/admin/usuarios")
@app.post("/api/usuarios")
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
