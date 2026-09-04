import hashlib
import os
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from jose import JWTError, jwt

SECRET_KEY = "chave_super_secreta_universidade_ia"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

app = FastAPI(title="API Sistema Universitario")

if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def gerar_hash_senha(senha: str) -> str:
    salt = b"universidade_salt_fixo_2026"
    return hashlib.pbkdf2_hmac('sha256', senha.encode('utf-8'), salt, 100000).hex()

def verificar_senha(senha_digitada: str, hash_armazenado: str) -> bool:
    return gerar_hash_senha(senha_digitada) == hash_armazenado

HASH_PADRAO = gerar_hash_senha("123456")

CURSOS_DB = [
    {"id": 1, "nome": "Engenharia Informática", "tipo": "Licenciatura"},
    {"id": 2, "nome": "Gestão de Empresas", "tipo": "Licenciatura"},
    {"id": 3, "nome": "Direito", "tipo": "Licenciatura"},
    {"id": 4, "nome": "Medicina", "tipo": "Licenciatura"},
    {"id": 5, "nome": "Arquitetura", "tipo": "Licenciatura"},
    {"id": 6, "nome": "Psicologia", "tipo": "Licenciatura"},
    {"id": 7, "nome": "Economia", "tipo": "Licenciatura"},
    {"id": 8, "nome": "Mestrado em Inteligência Artificial", "tipo": "Mestrado"},
    {"id": 9, "nome": "Mestrado em Gestão de Projetos", "tipo": "Mestrado"},
    {"id": 10, "nome": "Mestrado em Direito Empresarial", "tipo": "Mestrado"}
]

DISCIPLINAS_LICENCIATURA = {
    1: ["Introdução à Programação", "Álgebra Linear", "Cálculo I", "Arquitetura de Computadores", "Sistemas Operativos", "Física Geral"],
    2: ["Algoritmos e Estruturas de Dados", "Bancos de Dados", "Cálculo II", "Redes de Computadores", "Engenharia de Software", "Estatística e Probabilidades"]
}

# ADICIONADO: Campo "propina_em_dia" para controlar o bloqueio financeiro individual
USUARIOS_DB = {
    "admin@univ.br": {
        "id": "ADM01", "nome": "Diretoria Acadêmica", "email": "admin@univ.br",
        "senha_hash": HASH_PADRAO, "perfil": "admin", "curso_id": None, "propina_em_dia": True
    },
    "professor@univ.br": {
        "id": "DOC01", "nome": "Prof. Carlos Silva", "email": "professor@univ.br",
        "senha_hash": HASH_PADRAO, "perfil": "docente", "curso_id": 1, "propina_em_dia": True
    },
    "aluno@univ.br": {
        "id": "EST01", "nome": "Ana Maria", "email": "aluno@univ.br",
        "senha_hash": HASH_PADRAO, "perfil": "estudante", "curso_id": 1, "propina_em_dia": False  # Altere para True para liberar as notas
    }
}

NOTAS_DB = [
    {"estudante_id": "EST01", "semestre": 1, "disciplina": "Introdução à Programação", "teste": 8.5, "trabalho": 9.0, "exame": 8.0},
    {"estudante_id": "EST01", "semestre": 1, "disciplina": "Álgebra Linear", "teste": 7.0, "trabalho": 7.5, "exame": 8.0},
    {"estudante_id": "EST01", "semestre": 2, "disciplina": "Bancos de Dados", "teste": 9.0, "trabalho": 8.5, "exame": 9.5}
]

def criar_token_acesso(data: dict):
    to_encode = data.copy()
    expiracao = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expiracao})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def obter_usuario_atual(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None or email not in USUARIOS_DB:
            raise HTTPException(status_code=401, detail="Token inválido")
        return USUARIOS_DB[email]
    except JWTError:
        raise HTTPException(status_code=401, detail="Sessão expirada ou inválida")

@app.get("/")
def home():
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return {"mensagem": "Arquivo index.html não encontrado."}

@app.post("/api/auth/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    usuario = USUARIOS_DB.get(form_data.username)
    if not usuario or not verificar_senha(form_data.password, usuario["senha_hash"]):
        raise HTTPException(status_code=400, detail="E-mail ou senha incorretos")
    
    token = criar_token_acesso(data={"sub": usuario["email"], "perfil": usuario["perfil"]})
    return {
        "access_token": token, 
        "token_type": "bearer",
        "perfil": usuario["perfil"], 
        "nome": usuario["nome"],
        "id": usuario["id"], 
        "curso_id": usuario["curso_id"]
    }

@app.get("/api/cursos")
def listar_cursos():
    return CURSOS_DB

class NovoUsuario(BaseModel):
    nome: str
    email: str
    senha: str
    perfil: str
    curso_id: int

class EditarUsuario(BaseModel):
    email: str
    nome: str
    nova_senha: Optional[str] = None

@app.get("/api/admin/usuarios")
def listar_usuarios(usuario_atual: dict = Depends(obter_usuario_atual)):
    if usuario_atual["perfil"] != "admin":
        raise HTTPException(status_code=403, detail="Acesso restrito.")
    
    lista = []
    totais = {"estudantes": 0, "docentes": 0}
    
    for u in USUARIOS_DB.values():
        if u["perfil"] in ["estudante", "docente"]:
            curso = next((c["nome"] for c in CURSOS_DB if c["id"] == u["curso_id"]), "Não definido")
            lista.append({
                "id": u["id"],
                "nome": u["nome"],
                "email": u["email"],
                "perfil": u["perfil"],
                "curso": curso
            })
            if u["perfil"] == "estudante":
                totais["estudantes"] += 1
            else:
                totais["docentes"] += 1

    return {"totais": totais, "usuarios": lista}

@app.post("/api/admin/cadastrar-usuario")
def cadastrar_usuario(dados: NovoUsuario, usuario_atual: dict = Depends(obter_usuario_atual)):
    if usuario_atual["perfil"] != "admin":
        raise HTTPException(status_code=403, detail="Acesso restrito.")
    
    if dados.email in USUARIOS_DB:
        raise HTTPException(status_code=400, detail="E-mail já cadastrado.")

    novo_id = f"{'DOC' if dados.perfil == 'docente' else 'EST'}{len(USUARIOS_DB) + 1:02d}"
    
    USUARIOS_DB[dados.email] = {
        "id": novo_id,
        "nome": dados.nome,
        "email": dados.email,
        "senha_hash": gerar_hash_senha(dados.senha),
        "perfil": dados.perfil,
        "curso_id": dados.curso_id,
        "propina_em_dia": True
    }
    return {"mensagem": "Usuário cadastrado com sucesso!"}

@app.put("/api/admin/editar-usuario")
def editar_usuario(dados: EditarUsuario, usuario_atual: dict = Depends(obter_usuario_atual)):
    if usuario_atual["perfil"] != "admin":
        raise HTTPException(status_code=403, detail="Acesso restrito.")
    
    if dados.email not in USUARIOS_DB:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    USUARIOS_DB[dados.email]["nome"] = dados.nome
    if dados.nova_senha and dados.nova_senha.strip():
        USUARIOS_DB[dados.email]["senha_hash"] = gerar_hash_senha(dados.nova_senha)

    return {"mensagem": "Dados do usuário atualizados com sucesso!"}

@app.delete("/api/admin/deletar-usuario/{email}")
def deletar_usuario(email: str, usuario_atual: dict = Depends(obter_usuario_atual)):
    if usuario_atual["perfil"] != "admin":
        raise HTTPException(status_code=403, detail="Acesso restrito.")
    
    if email not in USUARIOS_DB:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    del USUARIOS_DB[email]
    return {"mensagem": "Usuário removido com sucesso!"}

# ROTA ATUALIZADA COM VERIFICAÇÃO DE BLOQUEIO FINANCEIRO
@app.get("/api/estudante/grade-notas")
def obter_grade_notas(usuario_atual: dict = Depends(obter_usuario_atual)):
    if usuario_atual["perfil"] != "estudante":
        raise HTTPException(status_code=403, detail="Acesso exclusivo para estudantes.")
    
    curso = next((c for c in CURSOS_DB if c["id"] == usuario_atual["curso_id"]), None)
    
    if not curso or curso["tipo"] == "Mestrado":
        return {"tipo": "Mestrado", "mensagem": "Disponíveis brevemente"}

    # VERIFICAÇÃO DE PROPINAS EM ATRASO
    if not usuario_atual.get("propina_em_dia", True):
        return {
            "tipo": "Licenciatura",
            "curso": curso["nome"],
            "bloqueado_financeiro": True,
            "mensagem": "Notas temporariamente bloqueadas devido a pendências no pagamento de propinas. Por favor, regularize a sua situação na secretaria.",
            "grade": {1: [], 2: []}
        }

    estudante_id = usuario_atual["id"]
    grade = {1: [], 2: []}

    for sem in [1, 2]:
        for disc in DISCIPLINAS_LICENCIATURA[sem]:
            nota = next((n for n in NOTAS_DB if n["estudante_id"] == estudante_id and n["disciplina"] == disc), None)
            grade[sem].append({
                "disciplina": disc,
                "teste": nota["teste"] if nota else "-",
                "trabalho": nota["trabalho"] if nota else "-",
                "exame": nota["exame"] if nota else "-",
                "media": round((nota["teste"] + nota["trabalho"] + nota["exame"]) / 3, 1) if nota else "-"
            })

    return {
        "tipo": "Licenciatura", 
        "curso": curso["nome"], 
        "bloqueado_financeiro": False,
        "grade": grade
    }

class PublicarNota(BaseModel):
    estudante_id: str
    semestre: int
    disciplina: str
    teste: float
    trabalho: float
    exame: float

@app.post("/api/docente/publicar-nota")
def publicar_nota(dados: PublicarNota, usuario_atual: dict = Depends(obter_usuario_atual)):
    if usuario_atual["perfil"] != "docente":
        raise HTTPException(status_code=403, detail="Apenas docentes podem publicar notas.")
    
    existente = next((n for n in NOTAS_DB if n["estudante_id"] == dados.estudante_id and n["disciplina"] == dados.disciplina), None)
    if existente:
        raise HTTPException(status_code=403, detail="Nota já publicada. Requer autorização do Administrador para alterar.")

    NOTAS_DB.append(dados.dict())
    return {"mensagem": "Nota publicada com sucesso!"}
