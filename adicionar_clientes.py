"""
Adiciona os clientes parlenda, gaia e littlekids ao config.py que JÁ EXISTE
na sua pasta, copiando a estrutura do cliente "tistu" (que já funciona).

Uso (na pasta do projeto):
    py adicionar_clientes.py

- Faz backup do config.py antes (config_backup_AAAAMMDD_HHMMSS.py).
- Não altera nenhum cliente existente: só acrescenta os novos no fim do arquivo.
- Se encontrar algo que não consegue copiar com segurança, para sem mexer em nada.
"""

import copy
import importlib
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

MODELO = "tistu"
BAIRRO_MODELO_PADRAO = "Água Verde"

NOVOS = {
    "parlenda": {
        "nome": "Parlenda",
        "marca": "Escola Parlenda",
        "apelidos": ["Parlenda", "Escola Parlenda", "Parlenda Berçário e Escola", "CEI Parlenda"],
        "bairro": "Santo Inácio",
    },
    "gaia": {
        "nome": "Gaia",
        "marca": "Escola Gaia",
        "apelidos": ["Gaia", "Escola Gaia", "Gaia CEI", "Centro Educacional Gaia"],
        "bairro": "Bigorrilho",
    },
    "littlekids": {
        "nome": "Little Kids",
        "marca": "Little Kids Escola Bilíngue",
        "apelidos": ["Little Kids", "Little Kids Bilíngue", "Little Kids Escola Bilíngue", "Little Kids Baby"],
        "bairro": "Cabral",
    },
}

TIPOS_SIMPLES = (str, int, float, bool, type(None))


def parar(msg):
    print(f"\n✘ {msg}\nNada foi alterado. Mande esta mensagem para o Claude.")
    sys.exit(1)


def achar_dicionario_clientes(config):
    """Variável do config.py que contém o cliente modelo (ex.: CLIENTES)."""
    for nome in dir(config):
        valor = getattr(config, nome)
        if isinstance(valor, dict) and isinstance(valor.get(MODELO), dict):
            return nome, valor
    parar(f'Não encontrei no config.py um dicionário com o cliente "{MODELO}".')


def nomes_do_modelo(modelo: dict):
    """Grafias do nome da Tistu usadas no cadastro (da mais longa para a mais curta)."""
    achados = set()

    def varrer(v):
        if isinstance(v, str):
            for m in re.finditer(r"[\wÀ-ÿ ]*tistu[\wÀ-ÿ ]*", v, re.IGNORECASE):
                achados.add(m.group(0).strip())
        elif isinstance(v, dict):
            for x in v.values():
                varrer(x)
        elif isinstance(v, (list, tuple, set)):
            for x in v:
                varrer(x)

    varrer(modelo)
    return sorted(achados, key=len, reverse=True)


def converter(valor, novo_id, novo, bairro_modelo):
    """Copia um valor do modelo trocando Tistu → nova escola e bairro → novo bairro."""
    if isinstance(valor, dict):
        return {k: converter(v, novo_id, novo, bairro_modelo) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        itens = list(valor)
        if itens and all(isinstance(x, str) for x in itens) and any("tistu" in x.lower() for x in itens):
            if any(re.search(r"[\\()\[\]?*+|^$]", x) for x in itens):
                parar(f"Lista com expressões regulares no cliente {MODELO}: {itens}")
            return list(novo["apelidos"])  # lista de apelidos/grafias da escola
        convertidos = [converter(x, novo_id, novo, bairro_modelo) for x in itens]
        return convertidos if isinstance(valor, list) else tuple(convertidos)
    if isinstance(valor, str):
        s = valor
        if "tistu" in s.lower() and re.search(r"[\\()\[\]?*+|^$]", s):
            parar(f"Texto com expressão regular no cliente {MODELO}: {s!r}")
        for bairro in {bairro_modelo, "Água Verde", "Agua Verde"}:
            s = s.replace(bairro, novo["bairro"])
        s = re.sub(r"\bEscola Tistu\b", novo["marca"], s)
        s = re.sub(r"\bTistu\b", novo["nome"], s)
        s = re.sub(r"tistu", novo_id, s, flags=re.IGNORECASE)  # ids e pastas: saida_tistu → saida_parlenda
        return s
    if isinstance(valor, TIPOS_SIMPLES):
        return valor
    parar(f"Valor de tipo inesperado no cliente {MODELO}: {type(valor).__name__} = {valor!r}")


def conferir(valor, caminho=""):
    """Garante que não sobrou nenhuma referência à Tistu nem ao Água Verde."""
    if isinstance(valor, dict):
        for k, v in valor.items():
            conferir(v, f"{caminho}.{k}")
    elif isinstance(valor, (list, tuple)):
        for i, v in enumerate(valor):
            conferir(v, f"{caminho}[{i}]")
    elif isinstance(valor, str):
        baixo = valor.lower()
        if "tistu" in baixo or "agua verde" in baixo or "água verde" in baixo:
            parar(f"Sobrou referência ao cliente modelo em {caminho}: {valor!r}")


def main():
    pasta = Path(__file__).resolve().parent
    arquivo = pasta / "config.py"
    if not arquivo.exists():
        parar("config.py não encontrado. Rode este script dentro da pasta do projeto.")
    sys.path.insert(0, str(pasta))
    import config

    nome_var, clientes = achar_dicionario_clientes(config)
    modelo = clientes[MODELO]
    bairro_modelo = next((v for k, v in modelo.items() if "bairro" in k.lower() and isinstance(v, str)),
                         BAIRRO_MODELO_PADRAO)
    print(f'Modelo: cliente "{MODELO}" em {nome_var} (bairro {bairro_modelo})')
    print(f"Grafias da Tistu encontradas: {nomes_do_modelo(modelo)}")

    blocos = []
    for novo_id, novo in NOVOS.items():
        if novo_id in clientes:
            print(f'  - "{novo_id}" já existe no config.py → mantido como está')
            continue
        cfg = converter(copy.deepcopy(modelo), novo_id, novo, bairro_modelo)
        conferir(cfg, novo_id)
        blocos.append((novo_id, cfg))

    if not blocos:
        print("Nada a adicionar.")
        return

    from pprint import pformat
    texto = [f"\n\n# --- Clientes adicionados em {datetime.now():%d/%m/%Y %H:%M} "
             f"(mesma estrutura do cliente \"{MODELO}\") ---\n"]
    for novo_id, cfg in blocos:
        texto.append(f"{nome_var}[{novo_id!r}] = {pformat(cfg, width=100, sort_dicts=False)}\n")

    backup = pasta / f"config_backup_{datetime.now():%Y%m%d_%H%M%S}.py"
    shutil.copy2(arquivo, backup)
    with open(arquivo, "a", encoding="utf-8") as f:
        f.write("".join(texto))

    # Confere se o config.py continua válido; se não, desfaz.
    try:
        importlib.reload(config)
        assert all(nid in getattr(config, nome_var) for nid, _ in blocos)
    except Exception as exc:
        shutil.copy2(backup, arquivo)
        parar(f"O config.py ficou inválido ({exc}); backup restaurado.")

    print(f"\nBackup do config.py original: {backup.name}")
    for novo_id, cfg in blocos:
        print(f"\n✔ Cliente \"{novo_id}\" adicionado:")
        print(pformat(cfg, width=100, sort_dicts=False))
    print("\nAgora rode:")
    for novo_id, _ in blocos:
        print(f"  py main.py teste --cliente {novo_id}")


if __name__ == "__main__":
    main()
