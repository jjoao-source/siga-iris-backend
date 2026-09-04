import os
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
from jose import JWTError, jwt

# CONFIGURAÇÕES DE SEGURANÇA
SECRET_KEY = "sua_chave_secreta_super_segura_aqui"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120

app = FastAPI(title="SIGA-Íris API")

# ---------------------------------------------------------
# CONFIGURAÇÃO DE CORS (Crucial para funcionar no Render + GitHub Pages)
# ---------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite requisições de qualquer origem (GitHub Pages, localhost, etc)
    allow_credentials=True,
    allow_methods=["*"],  # Permite GET, POST, OPTIONS, etc.
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# ---------------------------------------------------------
# BASE DE DADOS EM MEMÓRIA (Exemplo para testes)
# ---------------------------------------------------------
DB_CURSOS = [
    {"id": 1, "nome": "Engenharia Informática", "tipo": "Licenciatura"},
    {"id": 2, "nome": "Administração de Empresas", "tipo": "Licenciatura"},
    {"id": 3, "nome": "Medicina Geral", "tipo": "Mestrado Integral"}
]

DB_USUARIOS = {
    "admin@univ.br": {
        "nome": "Administrador do Sistema",
        "email": "admin@univ.br",
        "senha": "123",
        "perfil": "admin",
        "curso_id": None
    },
    "docente@univ.br": {
        "nome": "Prof. Doutor Carlos",
        "email": "docente@univ.br",
        "senha": "123",
        "perfil": "docente",
        "curso_id": 1,
        "disciplinas": {
            "1": ["Programação I", "Matemática Discreta"],
            "2": ["Algoritmos e Estruturas de Dados", "Base de Dados"]
        }
    },
    "estudante@univ.br": {
        "id": "EST01",
        "nome": "João Silva",
        "email": "estudante@univ.br",
        "senha": "123",
        "perfil": "estudante",
        "curso_id": 1,
        "bloqueado_financeiro": False,
        "grade": {
            "1": [
                {"disciplina": "Programação I", "teste": 14.0, "trabalho": 16.0, "exame": 15.0, "media": 15.0},
                {"disciplina": "Matemática Discreta", "teste": 12.0, "trabalho": 10.0, "exame": 11.0, "media": 11.0}
            ],
            "2": [
                {"disciplina": "Algoritmos e Estruturas de Dados", "teste": 0, "trabalho": 0, "exame": 0, "media": 0},
                {"disciplina": "Base de Dados", "teste": 0, "trabalho": 0, "exame": 0, "media": 0}
            ]
        }
    }
}

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
# FUNÇÕES AUXILIARES DE TOKEN
# ---------------------------------------------------------
def criar_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def obter_usuario_atual(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None or email not in DB_USUARIOS:
            raise HTTPException(status_code=401, detail="Token inválido ou utilizador não encontrado.")
        return DB_USUARIOS[email]
    except JWTError:
        raise HTTPException(status_code=401, detail="Token expirado ou inválido.")

# ---------------------------------------------------------
# ROTAS DA API
# ---------------------------------------------------------
@app.get("/")
def root():
    return {"status": "API SIGA-Íris a funcionar perfeitamente!"}

@app.post("/api/auth/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    usuario = DB_USUARIOS.get(form_data.username)
    if not usuario or usuario["senha"] != form_data.password:
        raise HTTPException(status_code=400, detail="Credenciais de acesso incorretas.")
    
    token = criar_token({"sub": usuario["email"], "perfil": usuario["perfil"]})
    return {
        "access_token": token,
        "token_type": "bearer",
        "perfil": usuario["perfil"],
        "nome": usuario["nome"]
    }

@app.get("/api/cursos")
def listar_cursos():
    return DB_CURSOS

@app.get("/api/docente/disciplinas")
def obter_disciplinas_docente(user: dict = Depends(obter_usuario_atual)):
    if user["perfil"] != "docente":
        raise HTTPException(status_code=430, detail="Acesso exclusivo para docentes.")
    return {"disciplinas": user.get("disciplinas", {})}

@app.post("/api/docente/publicar-nota")
def publicar_nota(payload: PublicarNotaSchema, user: dict = Depends(obter_usuario_atual)):
    if user["perfil"] != "docente":
        raise HTTPException(status_code=403, detail="Acesso exclusivo para docentes.")
    
    # Procura o estudante na base de dados pelo ID
    estudante = None
    for u in DB_USUARIOS.values():
        if u.get("id") == payload.estudante_id and u["perfil"] == "estudante":
            estudante = u
            break

    if not estudante:
        raise HTTPException(status_code=440, detail="Estudante não encontrado.")

    sem_str = str(payload.semestre)
    media = round((payload.teste + payload.trabalho + payload.exame) / 3, 1)

    # Atualiza ou adiciona a nota da disciplina no semestre correspondente
    grade_semestre = estudante["grade"].get(sem_str, [])
    atualizado = False
    for item in grade_semestre:
        if item["disciplina"] == payload.disciplina:
            item["teste"] = payload.teste
            item["trabalho"] = payload.trabalho
            item["exame"] = payload.exame
            item["media"] = media
            atualizado = True
            break

    if not atualizado:
        grade_semestre.append({
            "disciplina": payload.disciplina,
            "teste": payload.teste,
            "trabalho": payload.trabalho,
            "exame": payload.exame,
            "media": media
        })

    return {"mensagem": f"Notas de {payload.disciplina} publicadas com sucesso para {estudante['nome']}!"}

@app.get("/api/estudante/grade-notas")
def obter_grade_estudante(user: dict = Depends(obter_usuario_atual)):
    if user["perfil"] != "estudante":
        raise HTTPException(status_code=403, detail="Acesso exclusivo para estudantes.")
    
    if user.get("bloqueado_financeiro"):
        return {
            "bloqueado_financeiro": True,
            "mensagem": "Acesso suspenso por pendências financeiras. Dirija-se à secretaria."
        }

    # Procura o nome do curso pelo ID
    curso_nome = "Não Atribuído"
    for c in DB_CURSOS:
        if c["id"] == user.get("curso_id"):
            curso_nome = c["nome"]
            break

    return {
        "bloqueado_financeiro": False,
        "curso": curso_nome,
        "grade": user.get("grade", {})
    }

@app.post("/api/admin/cadastrar-usuario")
def cadastrar_usuario(payload: NovoUsuarioSchema, user: dict = Depends(obter_usuario_atual)):
    if user["perfil"] != "admin":
        raise HTTPException(status_code=403, detail="Acesso restrito ao administrador.")
    
    if payload.email in DB_USUARIOS:
        raise HTTPException(status_code=400, detail="E-mail já se encontra registado.")

    novo_usuario = {
        "nome": payload.nome,
        "email": payload.email,
        "senha": payload.senha,
        "perfil": payload.perfil,
        "curso_id": payload.curso_id
    }

    if payload.perfil == "estudante":
        novo_usuario["id"] = f"EST{len(DB_USUARIOS) + 1:02d}"
        novo_usuario["bloqueado_financeiro"] = False
        novo_usuario["grade"] = {"1": [], "2": []}

    DB_USUARIOS[payload.email] = novo_usuario
    return {"mensagem": f"Utilizador {payload.nome} cadastrado com sucesso!"}
