@app.get("/api/estudante/grade-notas")
def obter_grade_notas(current_user: dict = Depends(get_current_user)):
    # Simulação da verificação de propinas (Altere para True para testar o bloqueio)
    propina_atrasada = True  

    if propina_atrasada:
        return {
            "curso": "Engenharia Informática",
            "tipo": "Licenciatura",
            "bloqueado_financeiro": True,
            "mensagem": "Notas temporariamente bloqueadas devido a pendências na propina. Por favor, regularize a situação na tesouraria/secretaria.",
            "grade": {1: [], 2: []}
        }

    # Se a propina estiver em dia:
    return {
        "curso": "Engenharia Informática",
        "tipo": "Licenciatura",
        "bloqueado_financeiro": False,
        "grade": {
            1: [
                {"disciplina": "Introdução à Programação", "teste": 14, "trabalho": 16, "exame": 15, "media": 15},
                {"disciplina": "Álgebra Linear", "teste": 12, "trabalho": 11, "exame": 13, "media": 12}
            ],
            2: [
                {"disciplina": "Algoritmos e Estruturas de Dados", "teste": "-", "trabalho": "-", "exame": "-", "media": "-"}
            ]
        }
    }
