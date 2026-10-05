"""
Configuração central da Pesquisa de Visibilidade em IAs.

Tudo o que costuma mudar fica aqui, sem precisar mexer no resto do código:
  - CLIENTES ............ uma entrada por escola-alvo (escolhida por --cliente)
  - PERGUNTAS ........... as 30 perguntas (modelos com {escola} e {bairro})
  - ORDEM_EXECUCAO ...... 1–25 → 30 → 26–29 (26–29 sempre por último)
  - CONCORRENTES ........ escolas conhecidas de Curitiba usadas na extração
  - TEMPOS .............. pausas e tempos de espera
  - CONFIG_PLATAFORMAS .. URLs e seletores CSS de cada IA
"""

from pathlib import Path

PASTA_PROJETO = Path(__file__).resolve().parent
PASTA_PERFIS = PASTA_PROJETO / "perfis"  # sessões de login (compartilhadas entre clientes)

# ---------------------------------------------------------------------------
# CLIENTES (escolas-alvo)
# ---------------------------------------------------------------------------
# Cada cliente tem:
#   nome ............... nome da escola (planilha e análise)
#   nome_perguntas ..... (opcional) como a escola é escrita nas perguntas 26–29
#                        ({escola}); se ausente, usa "nome"
#   bairro ............. bairro usado nas perguntas 13, 14, 15, 29 e 30 ({bairro})
#   variantes .......... grafias que SEMPRE contam como menção à escola
#                        (comparação ignora acentos e maiúsculas/minúsculas)
#   nome_curto ......... (opcional, texto ou lista) nome "solto" e ambíguo que só
#                        conta como menção quando escrito como nome próprio e em
#                        contexto de escola (ver analysis.py)
#   excluir_contexto ... (opcional) expressões que, perto do nome curto,
#                        indicam outro sentido da palavra (não é a escola)
#   pasta_saida ........ pasta exclusiva do cliente (log, Excel, screenshots)
#   plataformas ........ plataformas automatizadas para esse cliente
CLIENTES = {
    "geracao": {
        "nome": "Geração do Saber",
        "bairro": "Água Verde",
        "variantes": ["Geração do Saber"],
        "pasta_saida": "saida",
        "plataformas": ["chatgpt", "gemini", "claude", "perplexity"],
    },
    "kambalhota": {
        "nome": "Kambalhota",
        "bairro": "Seminário",
        "variantes": ["Kambalhota", "Centro Educacional Kambalhota", "CE Kambalhota"],
        "pasta_saida": "saida_kambalhota",
        # Claude é feito manualmente para este cliente.
        "plataformas": ["chatgpt", "gemini", "perplexity"],
    },
    "lumen": {
        "nome": "Escola Lumen",
        "bairro": "Seminário",
        # Estas grafias são inequívocas: sempre contam.
        "variantes": ["Escola Lumen", "Colégio Lumen", "Centro Educacional Lumen", "CE Lumen"],
        # "Lumen" sozinho é ambíguo (lúmen = unidade de luz; "Lumen Gentium" etc.).
        # Só conta quando escrito como nome próprio (L maiúsculo) e em contexto
        # de escola. Regras detalhadas em analysis.detectar_mencao().
        "nome_curto": "Lumen",
        "excluir_contexto": [
            "lumens", "lampada", "lampadas", "iluminacao", "luminoso", "luminosa",
            "fluxo luminoso", "watts", "led", "lux", "candela", "projetor", "projetores",
            "lumen gentium", "lumen fidei", "lumen christi",
        ],
        "pasta_saida": "saida_lumen",
        # Claude é feito manualmente para este cliente.
        "plataformas": ["chatgpt", "gemini", "perplexity"],
    },
    "parlenda": {
        "nome": "Parlenda",
        "nome_perguntas": "Escola Parlenda",
        "bairro": "Santo Inácio",
        "variantes": ["Escola Parlenda", "Parlenda Berçário e Escola", "CEI Parlenda"],
        # "parlenda" também é um gênero de rima infantil ("parlendas e cantigas"):
        # sozinho, só conta com P maiúsculo e em contexto de escola.
        "nome_curto": "Parlenda",
        "excluir_contexto": ["trava-lingua", "trava-linguas", "quadrinha", "quadrinhas",
                             "folclore", "folclorica", "folcloricas"],
        "pasta_saida": "saida_parlenda",
        "plataformas": ["chatgpt", "gemini", "perplexity"],
    },
    "gaia": {
        "nome": "Gaia",
        "nome_perguntas": "Escola Gaia",
        "bairro": "Bigorrilho",
        "variantes": ["Escola Gaia", "Gaia CEI", "Centro Educacional Gaia"],
        # "Gaia" sozinho é ambíguo (Vila Nova de Gaia, deusa, hipótese Gaia).
        "nome_curto": "Gaia",
        "excluir_contexto": ["vila nova de gaia", "hipotese gaia", "teoria gaia", "deusa",
                             "mitologia", "mitologia grega", "mae terra", "portugal"],
        "pasta_saida": "saida_gaia",
        "plataformas": ["chatgpt", "gemini", "perplexity"],
    },
    "littlekids": {
        "nome": "Little Kids",
        "nome_perguntas": "Little Kids Escola Bilíngue",
        "bairro": "Cabral",
        "variantes": ["Little Kids Escola Bilíngue", "Little Kids Bilíngue", "Little Kids Baby"],
        # "little kids" também é expressão comum em inglês: sozinho, só conta
        # escrito como nome ("Little Kids") e em contexto de escola.
        "nome_curto": "Little Kids",
        "pasta_saida": "saida_littlekids",
        "plataformas": ["chatgpt", "gemini", "perplexity"],
    },
}

CIDADE = "Curitiba"

# ---------------------------------------------------------------------------
# PERGUNTAS (modelos). {escola} e {bairro} vêm do cliente escolhido.
# Para "geracao", o texto final é idêntico ao original da pesquisa.
# ---------------------------------------------------------------------------
PERGUNTAS = {
    1: "Quais são as melhores escolas particulares de Curitiba?",
    2: "Quais são as melhores escolas de educação infantil em Curitiba?",
    3: "Melhor berçário particular em Curitiba.",
    4: "Escola bilíngue para educação infantil em Curitiba.",
    5: "Escola com aula de inglês todos os dias em Curitiba.",
    6: "Escola particular com período integral em Curitiba.",
    7: "Escola com turmas pequenas e atenção individual em Curitiba.",
    8: "Escola com muita área verde e contato com a natureza em Curitiba.",
    9: "Escola construtivista ou com pedagogia de projetos em Curitiba.",
    10: "Escola com boa alimentação e nutricionista em Curitiba.",
    11: "Melhores escolas particulares de ensino fundamental em Curitiba.",
    12: "Escola particular com bom custo-benefício em Curitiba.",
    13: "Escola de educação infantil no bairro {bairro}, em Curitiba.",
    14: "Escola particular perto do bairro {bairro}, em Curitiba.",
    15: "Berçário no bairro {bairro} ou região, em Curitiba.",
    16: "Escola infantil com câmeras para os pais acompanharem em Curitiba.",
    17: "Escola com atividades extracurriculares (música, esporte, robótica) em Curitiba.",
    18: "Escola com boa adaptação para crianças de 1 a 3 anos em Curitiba.",
    19: "Escola com educação socioemocional em Curitiba.",
    20: "Escola particular com segurança e portaria controlada em Curitiba.",
    21: "Escola com horário estendido para pais que trabalham em Curitiba.",
    22: "Qual escola infantil tem as melhores avaliações em Curitiba?",
    23: "Escola particular com metodologia Montessori em Curitiba.",
    24: "Escola que aceita crianças com necessidades especiais em Curitiba.",
    25: "Escola infantil com piscina ou aula de natação em Curitiba.",
    26: "Vale a pena a {escola}?",
    27: "O que os pais dizem da {escola}?",
    28: "Quanto custa a mensalidade da {escola}?",
    29: "{escola} ou outra escola do bairro {bairro}: qual é melhor?",
    30: "Qual a melhor escola para meu filho de 2 anos no bairro {bairro}?",
}

# Ordem obrigatória: 1–25, depois 30, por último 26, 27, 28, 29.
ORDEM_EXECUCAO = list(range(1, 26)) + [30] + [26, 27, 28, 29]

PERGUNTA_TESTE = 1  # usada no modo "teste"


def pergunta_texto(cliente_id: str, numero: int) -> str:
    """Texto final da pergunta para um cliente."""
    c = CLIENTES[cliente_id]
    return PERGUNTAS[numero].format(escola=c.get("nome_perguntas", c["nome"]), bairro=c["bairro"])


def pasta_saida(cliente_id: str) -> Path:
    return PASTA_PROJETO / CLIENTES[cliente_id]["pasta_saida"]


# ---------------------------------------------------------------------------
# CONCORRENTES conhecidos (nome canônico → grafias aceitas).
# Usado junto com a extração heurística de "Escola X", "Colégio X" etc.
# As escolas-alvo dos outros clientes também entram como concorrentes.
# ---------------------------------------------------------------------------
CONCORRENTES = {
    "Colégio Positivo": ["Colégio Positivo", "Positivo Júnior", "Positivo Jr", "Escola Positivo"],
    "Colégio Marista Santa Maria": ["Marista Santa Maria", "Colégio Santa Maria"],
    "Colégio Marista Paranaense": ["Marista Paranaense"],
    "Colégio Bom Jesus": ["Bom Jesus"],
    "Colégio Sion": ["Colégio Sion", "Nossa Senhora de Sion"],
    "Colégio Medianeira": ["Colégio Medianeira", "Nossa Senhora Medianeira"],
    "Colégio Dom Bosco": ["Dom Bosco"],
    "Colégio Suíço-Brasileiro": ["Suíço-Brasileiro", "Suico Brasileiro", "Colégio Suíço"],
    "International School of Curitiba": ["International School of Curitiba", "Escola Internacional de Curitiba"],
    "Maple Bear": ["Maple Bear"],
    "Colégio Opet": ["Colégio Opet", "Opet"],
    "Colégio Sesi": ["Colégio Sesi", "Sesi Internacional"],
    "Colégio Expoente": ["Expoente"],
    "Colégio Martinus": ["Martinus"],
    "Colégio Bagozzi": ["Bagozzi"],
    "Colégio Sagrado Coração de Jesus": ["Sagrado Coração de Jesus"],
    "Colégio Adventista": ["Adventista"],
    "Escola Waldorf Anabá": ["Waldorf Anabá", "Anabá"],
    "Escola Waldorf Turmalina": ["Turmalina"],
    "Colégio Integral": ["Colégio Integral"],
    "Colégio Decisivo": ["Colégio Decisivo"],
    "Colégio Nossa Senhora do Rosário": ["Nossa Senhora do Rosário"],
    "Colégio Militar de Curitiba": ["Colégio Militar"],
    "Colégio Estadual do Paraná": ["Colégio Estadual do Paraná"],
    "Escola Bilíngue Pueri Domus": ["Pueri Domus"],
    "Escola Montessori": ["Montessori Curitiba"],
}
# Escolas-alvo de todos os clientes (entram como concorrentes dos outros).
for _cid, _c in CLIENTES.items():
    CONCORRENTES.setdefault(_c["nome"], list(_c["variantes"]))

# ---------------------------------------------------------------------------
# TEMPOS (segundos)
# ---------------------------------------------------------------------------
TEMPOS = {
    "pausa_min": 25,             # pausa aleatória entre consultas
    "pausa_max": 45,
    "carregar_pagina": 60,       # timeout de navegação
    "esperar_entrada": 30,       # até a caixa de texto aparecer
    "inicio_resposta": 90,       # até a resposta começar a aparecer
    "resposta_max": 300,         # tempo máximo total de uma resposta
    "estabilidade": 6,           # texto parado por N s (e sem botão "parar") = terminou
    "espera_retentativa": 15,    # espera antes de tentar de novo após erro de rede
}

# Se o login do Google recusar o Chromium do Playwright, use o Chrome instalado:
# NAVEGADOR_CANAL = "chrome"
NAVEGADOR_CANAL = None

# ---------------------------------------------------------------------------
# PLATAFORMAS — seletores CSS (listas separadas por vírgula = qualquer um serve)
# ---------------------------------------------------------------------------
CONFIG_PLATAFORMAS = {
    "chatgpt": {
        "nome": "ChatGPT",
        "url_nova": "https://chatgpt.com/",
        "seletor_entrada": "#prompt-textarea, div[data-composer-editor-host] textarea",
        "seletor_botao_enviar": "button[data-testid='send-button']",
        "seletores_resposta": ["div[data-message-author-role='assistant']"],
        "seletor_parando": "button[data-testid='stop-button']",
        "seletores_fontes": [],
        "indicadores_login": ["button[data-testid='login-button']", "a[href*='auth/login']"],
    },
    "gemini": {
        "nome": "Gemini",
        "url_nova": "https://gemini.google.com/app",
        "seletor_entrada": "rich-textarea div[contenteditable='true'], div.ql-editor[contenteditable='true']",
        "seletor_botao_enviar": "button.send-button, button[aria-label*='Enviar'], button[aria-label*='Send']",
        "seletores_resposta": ["model-response message-content", "message-content", "model-response"],
        "seletor_parando": "button[aria-label*='Parar'], button[aria-label*='Stop']",
        "seletores_fontes": ["sources-list a[href]", "source-footnote a[href]"],
        "indicadores_login": ["a[href*='accounts.google.com/ServiceLogin']", "a[aria-label*='Fazer login']"],
    },
    "claude": {
        "nome": "Claude",
        "url_nova": "https://claude.ai/new",
        "seletor_entrada": "div[contenteditable='true'].ProseMirror, div[contenteditable='true']",
        "seletor_botao_enviar": "button[aria-label*='Send'], button[aria-label*='Enviar']",
        "seletores_resposta": ["div.font-claude-response", "div[data-is-streaming]"],
        "seletor_parando": "button[aria-label*='Stop'], button[aria-label*='Parar']",
        "seletores_fontes": [],
        "indicadores_login": ["a[href*='/login']", "button:has-text('Continue with Google')"],
    },
    "perplexity": {
        "nome": "Perplexity",
        "url_nova": "https://www.perplexity.ai/",
        # Hoje a caixa é <div contenteditable="true" id="ask-input" role="textbox">.
        "seletor_entrada": "#ask-input",
        "seletor_botao_enviar": "button[aria-label='Submit'], button[aria-label*='Enviar']",
        "seletores_resposta": ["div[id^='markdown-content']", "div.prose"],
        "seletor_parando": "button[aria-label*='Stop'], button[aria-label*='Parar']",
        "seletores_fontes": ["div[class*='citation'] a[href]", "a[data-testid*='source']", "a.citation"],
        "indicadores_login": [],
    },
}

ORDEM_PLATAFORMAS = ["chatgpt", "gemini", "claude", "perplexity"]

# Respostas com menos caracteres que isto são "resposta_insuficiente".
MIN_CARACTERES_RESPOSTA = 80
