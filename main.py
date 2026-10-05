"""
Pesquisa de Visibilidade de Escolas em IAs — orquestrador (linha de comando).

Comandos:
  py main.py login --plataforma chatgpt        login manual (perfil salvo em perfis/)
  py main.py login --todas
  py main.py teste    --cliente lumen          pergunta 1 em cada plataforma do cliente
  py main.py executar --cliente lumen          pesquisa completa (retomável)
  py main.py executar --cliente lumen --plataforma gemini
  py main.py executar --cliente lumen --apenas-erros
  py main.py exportar --cliente lumen          regenera o Excel a partir do log
"""

import argparse
import random
import sys
import time
from datetime import datetime

import analysis
import config
import storage

# Console do Windows: garante acentos na saída.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def caminhos(cliente_id: str, teste: bool = False):
    pasta = config.pasta_saida(cliente_id)
    sufixo = "_teste" if teste else ""
    return {
        "pasta": pasta,
        "log": pasta / f"resultados{sufixo}.jsonl",
        "excel": pasta / f"pesquisa_visibilidade{sufixo}.xlsx",
        "screenshots": pasta / "screenshots",
    }


# ---------------------------------------------------------------------------
def cmd_login(args):
    from playwright.sync_api import sync_playwright

    from runners import abrir_contexto

    plataformas = config.ORDEM_PLATAFORMAS if args.todas else [args.plataforma]
    if not args.todas and not args.plataforma:
        sys.exit("Use --plataforma NOME ou --todas")
    with sync_playwright() as pw:
        for p in plataformas:
            cfg = config.CONFIG_PLATAFORMAS[p]
            print(f"\n=== Login: {cfg['nome']} ===")
            ctx = abrir_contexto(pw, p)
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(cfg["url_nova"])
            input("Faça o login na janela do navegador (inclusive 2FA), espere o chat "
                  "carregar e pressione ENTER aqui... ")
            ctx.close()
            print(f"Sessão de {cfg['nome']} salva em perfis/{p}")


# ---------------------------------------------------------------------------
def montar_fila(cliente_id, plataformas, registros, apenas_erros, teste):
    """Lista [(plataforma, [números pendentes na ordem exigida])]."""
    if teste:
        return [(p, [config.PERGUNTA_TESTE]) for p in plataformas]
    ultimos = storage.ultimos_por_consulta(registros)
    fila = []
    for p in plataformas:
        pendentes = []
        for n in config.ORDEM_EXECUCAO:
            r = ultimos.get((p, n))
            concluida = r is not None and r.get("status") in storage.STATUS_CONCLUIDOS
            if apenas_erros:
                if r is not None and not concluida:
                    pendentes.append(n)
            elif not concluida:
                pendentes.append(n)
        if pendentes:
            fila.append((p, pendentes))
    return fila


def cmd_executar(args, teste=False):
    cliente_id = args.cliente
    cliente = config.CLIENTES[cliente_id]
    if args.plataforma:
        if args.plataforma not in cliente["plataformas"]:
            sys.exit(f"A plataforma '{args.plataforma}' não está configurada para o cliente "
                     f"'{cliente_id}' (plataformas: {', '.join(cliente['plataformas'])}).")
        plataformas = [args.plataforma]
    else:
        plataformas = list(cliente["plataformas"])

    cam = caminhos(cliente_id, teste)
    cam["pasta"].mkdir(parents=True, exist_ok=True)
    registros = storage.ler_registros(cam["log"])
    fila = montar_fila(cliente_id, plataformas, registros, getattr(args, "apenas_erros", False), teste)

    print(f"Cliente: {cliente['nome']} ({cliente['bairro']}) → pasta {cam['pasta'].name}/")
    if not fila:
        print("Nada pendente — todas as consultas já foram concluídas.")
        storage.exportar_excel(cliente_id, registros, cam["excel"])
        return
    total = sum(len(ns) for _, ns in fila)
    print(f"Consultas a executar: {total} — " + ", ".join(f"{p}: {len(ns)}" for p, ns in fila))

    from playwright.sync_api import sync_playwright

    from runners import ErroLoginComRegistro, ExecutorPlataforma, abrir_contexto

    feitas = 0
    sessoes_caidas = []
    try:
        with sync_playwright() as pw:
            for p, numeros in fila:
                nome_p = config.CONFIG_PLATAFORMAS[p]["nome"]
                print(f"\n=== {nome_p}: {len(numeros)} consulta(s) ===")
                ctx = abrir_contexto(pw, p)
                try:
                    exe = ExecutorPlataforma(ctx, p, cam["screenshots"])
                    for i, n in enumerate(numeros):
                        pergunta = config.pergunta_texto(cliente_id, n)
                        data_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        print(f"  [{nome_p}] P{n:02d}: {pergunta}")
                        login_caiu = False
                        try:
                            res = exe.consultar(n, pergunta)
                        except ErroLoginComRegistro as exc:
                            res, login_caiu = exc.registro, True
                        registro = {
                            "cliente": cliente_id, "plataforma": p, "numero": n,
                            "ordem": config.ORDEM_EXECUCAO.index(n) + 1,
                            "pergunta": pergunta, "data_hora": data_hora, **res,
                            "escolas": [], "alvo_mencionado": None, "posicao": None,
                            "concorrentes": [], "descricao": "", "fontes": [],
                        }
                        if res["status"] == "ok":
                            registro["status"] = analysis.classificar_status(res["resposta"])
                            registro.update(analysis.analisar(res["resposta"], res.get("links"), cliente, p))
                        storage.gravar_registro(cam["log"], registro)
                        registros.append(registro)
                        storage.exportar_excel(cliente_id, registros, cam["excel"])
                        feitas += 1
                        mencao = {True: "MENCIONADA", False: "não citada", None: "-"}[registro["alvo_mencionado"]]
                        print(f"     → status={registro['status']} | {cliente['nome']}: {mencao}"
                              + (f" | {registro['observacoes']}" if registro.get("observacoes") else ""))
                        if login_caiu:
                            print(f"  !! Sessão de {nome_p} caiu. Rode: py main.py login --plataforma {p}")
                            sessoes_caidas.append(p)
                            break
                        if i < len(numeros) - 1:
                            pausa = random.uniform(config.TEMPOS["pausa_min"], config.TEMPOS["pausa_max"])
                            print(f"     pausa de {pausa:.0f}s")
                            time.sleep(pausa)
                finally:
                    try:
                        ctx.close()
                    except Exception:
                        pass
    except KeyboardInterrupt:
        print("\nInterrompido pelo usuário (Ctrl+C). Tudo o que foi capturado está salvo.")
        print("Para continuar, rode o mesmo comando de novo.")

    storage.exportar_excel(cliente_id, registros, cam["excel"])
    ultimos = storage.ultimos_por_consulta(registros)
    falhas = [k for k, r in ultimos.items() if r.get("status") not in storage.STATUS_CONCLUIDOS]
    print(f"\nConsultas executadas nesta rodada: {feitas}")
    print(f"Excel: {cam['excel']}")
    if falhas and not teste:
        print(f"Consultas com falha pendentes: {len(falhas)} → "
              f"py main.py executar --cliente {cliente_id} --apenas-erros")
    if sessoes_caidas:
        print("Refaça o login em: " + ", ".join(sessoes_caidas))


def cmd_exportar(args):
    cam = caminhos(args.cliente)
    registros = storage.ler_registros(cam["log"])
    destino = storage.exportar_excel(args.cliente, registros, cam["excel"])
    print(f"{len(registros)} registro(s) no log → {destino}")


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Pesquisa de visibilidade de escolas em IAs")
    sub = ap.add_subparsers(dest="comando", required=True)

    p_login = sub.add_parser("login", help="login manual nas plataformas")
    p_login.add_argument("--plataforma", choices=config.ORDEM_PLATAFORMAS)
    p_login.add_argument("--todas", action="store_true")

    for nome, ajuda in [("teste", "pergunta 1 em cada plataforma"),
                        ("executar", "pesquisa completa (retomável)"),
                        ("exportar", "regenera o Excel a partir do log")]:
        sp = sub.add_parser(nome, help=ajuda)
        sp.add_argument("--cliente", required=True, choices=list(config.CLIENTES))
        if nome != "exportar":
            sp.add_argument("--plataforma", choices=config.ORDEM_PLATAFORMAS)
        if nome == "executar":
            sp.add_argument("--apenas-erros", action="store_true",
                            help="refaz só as consultas que falharam")

    args = ap.parse_args()
    if args.comando == "login":
        cmd_login(args)
    elif args.comando == "teste":
        cmd_executar(args, teste=True)
    elif args.comando == "executar":
        cmd_executar(args)
    elif args.comando == "exportar":
        cmd_exportar(args)


if __name__ == "__main__":
    main()
