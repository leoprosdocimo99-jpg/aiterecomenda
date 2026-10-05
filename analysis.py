"""
Extração de informações das respostas das IAs.

- detectar_mencao(): a escola-alvo foi citada? (ignora acentos e maiúsculas)
- extrair_escolas(): escolas citadas (lista conhecida + heurística "Escola X", "Colégio X"...)
- posicao_em_lista(): posição da escola-alvo numa lista numerada
- descricao_atribuida(): trecho da resposta que descreve a escola-alvo
- extrair_urls(): links e endereços citados
- analisar(): junta tudo em um dicionário pronto para gravar

Nada é inventado: se não há dado, o campo fica vazio/None.
"""

import re
import unicodedata
from urllib.parse import parse_qs, urlparse

import config


# ---------------------------------------------------------------------------
# Normalização (mantém o MESMO comprimento do texto original, para que as
# posições encontradas no texto normalizado valham no original)
# ---------------------------------------------------------------------------
def normalizar(texto: str) -> str:
    saida = []
    for ch in texto or "":
        base = unicodedata.normalize("NFD", ch)
        base = "".join(c for c in base if not unicodedata.combining(c)) or ch
        saida.append(base.lower()[0])
    return "".join(saida)


def _regex_termo(termo: str) -> re.Pattern:
    """Termo normalizado como palavra inteira (espaços flexíveis)."""
    partes = [re.escape(p) for p in normalizar(termo).split()]
    return re.compile(r"(?<!\w)" + r"[\s\-]+".join(partes) + r"(?!\w)")


# Palavras que indicam contexto de escola, usadas para o "nome curto".
_CONTEXTO_ESCOLA = re.compile(
    r"(?<!\w)(escola|escolas|colegio|colegios|educacao infantil|bercario|ensino|"
    r"matricula|mensalidade|pedagog\w*|alunos?|criancas?|turmas?|instituicao|"
    r"unidade|bairro|seminario|curitiba|infantil|bilingue|professor\w*)(?!\w)"
)
_JANELA_CONTEXTO = 150
_ITEM_LISTA = re.compile(r"^\s*(?:[#>*\-•]+\s*)?(?:\*\*)?\s*(\d{1,2})\s*[.)º°]\s+")
_INICIO_ITEM = re.compile(r"\s*(?:[#>*\-•]+\s*)?(?:\*\*)?\s*(?:\d{1,2}\s*[.)º°]\s*)?(?:\*\*)?\s*")


def _ocorrencias(texto: str, cliente: dict):
    """Lista de (inicio, fim) das menções à escola-alvo no texto."""
    if not texto:
        return []
    norm = normalizar(texto)
    achados = []

    # 1) Grafias inequívocas: sempre contam.
    for v in cliente.get("variantes", []):
        for m in _regex_termo(v).finditer(norm):
            achados.append((m.start(), m.end()))

    # 2) Nome curto ambíguo (ex.: "Lumen"): só como nome de escola.
    curtos = cliente.get("nome_curto") or []
    if isinstance(curtos, str):
        curtos = [curtos]
    excluir = [_regex_termo(e) for e in cliente.get("excluir_contexto", [])]
    for curto in curtos:
        for m in _regex_termo(curto).finditer(norm):
            ini, fim = m.start(), m.end()
            if any(a <= ini < b for a, b in achados):
                continue  # já contada como parte de uma grafia completa
            if not all(p[0].isupper() for p in texto[ini:fim].split()):
                continue  # minúsculo ("lúmen", "parlenda", "little kids") = palavra comum
            antes = norm[max(0, ini - 12):ini]
            if re.search(r"\d\s*$", antes):
                continue  # "800 lúmens", "1 lumen"
            janela = norm[max(0, ini - _JANELA_CONTEXTO):fim + _JANELA_CONTEXTO]
            if any(e.search(janela) for e in excluir):
                continue  # contexto de iluminação / documento da Igreja etc.
            inicio_linha = norm.rfind("\n", 0, ini) + 1
            # Nome no início de um item de lista ("1. Lumen –", "- **Lumen**").
            prefixo = texto[inicio_linha:ini]
            e_item_lista = bool(prefixo.strip()) and bool(_INICIO_ITEM.fullmatch(prefixo))
            if achados or e_item_lista or _CONTEXTO_ESCOLA.search(janela):
                achados.append((ini, fim))
    return sorted(set(achados))


def detectar_mencao(texto: str, cliente: dict) -> bool:
    return bool(_ocorrencias(texto, cliente))


# ---------------------------------------------------------------------------
# URLs / fontes
# ---------------------------------------------------------------------------
_URL = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)
_DOMINIO = re.compile(r"(?<![@\w/])((?:[a-z0-9-]+\.)+(?:com\.br|org\.br|edu\.br|gov\.br|net\.br|com|org|net|br))(?:/[^\s)\]]*)?(?!\w)", re.IGNORECASE)


def limpar_url(url: str) -> str:
    url = url.strip().rstrip(".,;:")
    try:
        p = urlparse(url)
        if p.netloc.endswith("google.com") and p.path == "/url":
            q = parse_qs(p.query)
            for chave in ("q", "url"):
                if q.get(chave):
                    return q[chave][0]
    except ValueError:
        pass
    return url


def extrair_urls(texto: str, links: list | None = None, plataforma: str | None = None) -> list:
    """URLs dos links capturados + URLs/domínios escritos no texto (sem duplicar)."""
    vistos, saida = set(), []
    host_plataforma = ""
    if plataforma and plataforma in config.CONFIG_PLATAFORMAS:
        host_plataforma = urlparse(config.CONFIG_PLATAFORMAS[plataforma]["url_nova"]).netloc.replace("www.", "")

    def add(u):
        u = limpar_url(u)
        if not u or u.startswith(("javascript:", "mailto:", "#")):
            return
        host = urlparse(u if "://" in u else "http://" + u).netloc.replace("www.", "").lower()
        if host_plataforma and host.endswith(host_plataforma):
            return  # link interno da própria plataforma
        chave = u.lower().rstrip("/")
        if chave not in vistos:
            vistos.add(chave)
            saida.append(u)

    for l in links or []:
        add(l.get("href", "") if isinstance(l, dict) else str(l))
    for m in _URL.finditer(texto or ""):
        add(m.group(0))
    sem_urls = _URL.sub(" ", texto or "")
    for m in _DOMINIO.finditer(sem_urls):
        add(m.group(0))
    return saida


# ---------------------------------------------------------------------------
# Escolas citadas
# ---------------------------------------------------------------------------
_PREFIXOS = r"(?:Escola|Colégio|Colegio|Centro Educacional|Centro de Educação Infantil|CEI|CE|Berçário|Bercario|Instituto|Educandário|Creche|Espaço|Sistema de Ensino)"
_PALAVRA = r"(?:[A-ZÀ-Ý][\w'’\-.]*|\d+)"
_LIGA = r"(?:de|do|da|dos|das|e|&)"
_NOME_ESCOLA = re.compile(
    rf"\b({_PREFIXOS}(?:\s+{_LIGA})?(?:\s+{_PALAVRA})(?:\s+(?:{_LIGA}\s+)?{_PALAVRA}){{0,5}})"
)
# Palavras genéricas: "Escola Particular", "Escola Bilíngue" não são nomes.
_GENERICAS = {normalizar(p) for p in [
    "particular", "particulares", "publica", "publicas", "municipal", "estadual", "infantil",
    "bilingue", "integral", "curitiba", "parana", "brasil", "ensino", "fundamental", "medio",
    "educacao", "berçario", "bercario", "creche", "a", "o", "em", "no", "na", "com", "para",
    "seminario", "agua", "verde", "tradicional", "internacional", "construtivista", "montessori",
    "waldorf", "regular", "privada", "privadas", "de", "do", "da", "dos", "das", "e", "&",
]}
_PARAR_EM = re.compile(r"\s+(?:em|no|na|com|para|que|é|e\s+(?:a|o)\b)\s+.*$")


def _limpar_nome(nome: str) -> str:
    nome = _PARAR_EM.sub("", nome).strip(" .,:;-–—*")
    nome = re.sub(r"\s+(?:de|do|da|dos|das|e|&)$", "", nome)
    return re.sub(r"\s+", " ", nome)


def extrair_escolas(texto: str, cliente: dict) -> list:
    """Nomes de escolas citadas (escola-alvo incluída, com o nome oficial do cliente)."""
    if not texto:
        return []
    norm = normalizar(texto)
    encontradas = []

    def add(nome):
        if normalizar(nome) not in {normalizar(n) for n in encontradas}:
            encontradas.append(nome)

    if detectar_mencao(texto, cliente):
        add(cliente["nome"])
    for canonico, grafias in config.CONCORRENTES.items():
        if normalizar(canonico) == normalizar(cliente["nome"]):
            continue
        if any(_regex_termo(g).search(norm) for g in grafias):
            add(canonico)
    for m in _NOME_ESCOLA.finditer(texto):
        nome = _limpar_nome(m.group(1))
        palavras = nome.split()[1:]
        if not palavras or all(normalizar(p) in _GENERICAS for p in palavras):
            continue
        if detectar_mencao(nome, cliente):
            continue  # é a própria escola-alvo (já incluída acima)
        # Se já está coberta por um concorrente conhecido, não duplica.
        if any(any(_regex_termo(g).search(normalizar(nome)) for g in gr)
               for gr in config.CONCORRENTES.values()):
            continue
        add(nome)
    return encontradas


def concorrentes(escolas: list, cliente: dict) -> list:
    return [e for e in escolas if normalizar(e) != normalizar(cliente["nome"])]


# ---------------------------------------------------------------------------
# Posição em lista ordenada e descrição
# ---------------------------------------------------------------------------
def posicao_em_lista(texto: str, cliente: dict):
    """Número do item (1., 2) ...) em que a escola-alvo aparece; None se não há lista."""
    ocorr = _ocorrencias(texto, cliente)
    if not ocorr:
        return None
    # Monta os itens numerados com seus intervalos [inicio, fim) no texto.
    itens, pos = [], 0
    for linha in texto.splitlines(keepends=True):
        m = _ITEM_LISTA.match(linha)
        if m:
            itens.append([int(m.group(1)), pos, pos + len(linha)])
        elif itens and linha.strip() and not re.match(r"\s*#", linha):
            itens[-1][2] = pos + len(linha)  # continuação do item anterior
        pos += len(linha)
    for numero, a, b in itens:
        if any(a <= o < b for o, _ in ocorr):
            return numero
    return None


def descricao_atribuida(texto: str, cliente: dict, limite: int = 600) -> str:
    """Frases/itens da resposta que falam da escola-alvo (texto literal da IA)."""
    ocorr = _ocorrencias(texto, cliente)
    if not ocorr:
        return ""
    trechos = []
    for ini, _ in ocorr:
        # Do início da frase/linha até o fim da frase/linha.
        a = max(texto.rfind("\n", 0, ini), max(texto.rfind(s, 0, ini) for s in (". ", "! ", "? ")) + 1)
        a = max(a, 0)
        b_cands = [texto.find(s, ini) for s in ("\n", ". ", "! ", "? ")]
        b_cands = [b for b in b_cands if b >= 0]
        b = min(b_cands) + 1 if b_cands else len(texto)
        trecho = texto[a:b].strip(" \n-*•")
        # Itens de lista curtos: inclui a linha seguinte (geralmente a descrição).
        if len(trecho) < 40:
            prox = texto.find("\n", b)
            trecho = texto[a:prox if prox > 0 else len(texto)].strip(" \n-*•")
        trecho = re.sub(r"\s+", " ", trecho)
        if trecho and trecho not in trechos:
            trechos.append(trecho)
    return " | ".join(trechos)[:limite]


# ---------------------------------------------------------------------------
# Tudo junto
# ---------------------------------------------------------------------------
def analisar(texto: str, links: list, cliente: dict, plataforma: str | None = None) -> dict:
    escolas = extrair_escolas(texto, cliente)
    mencionada = detectar_mencao(texto, cliente)
    return {
        "escolas": escolas,
        "alvo_mencionado": mencionada,
        "posicao": posicao_em_lista(texto, cliente) if mencionada else None,
        "concorrentes": concorrentes(escolas, cliente),
        "descricao": descricao_atribuida(texto, cliente) if mencionada else "",
        "fontes": extrair_urls(texto, links, plataforma),
    }


def classificar_status(texto: str) -> str:
    """ok ou resposta_insuficiente (falhas de execução são definidas pelo runner)."""
    if not texto or len(texto.strip()) < config.MIN_CARACTERES_RESPOSTA:
        return "resposta_insuficiente"
    return "ok"
