# Pesquisa de Visibilidade de Escolas em IAs

Automação em Python (Playwright) que faz 30 perguntas comuns de pais sobre escolas
particulares de Curitiba ao **ChatGPT**, **Gemini**, **Claude** e **Perplexity** e verifica
se a escola-alvo aparece nas respostas, em que posição, com qual descrição, contra quais
concorrentes e com quais fontes.

## Escolas-alvo (clientes)

| `--cliente` | Escola | Bairro (P13, 14, 15, 29, 30) | Plataformas automatizadas | Pasta de resultados |
|---|---|---|---|---|
| `geracao` | Geração do Saber | Água Verde | chatgpt, gemini, claude, perplexity | `saida/` |
| `kambalhota` | Kambalhota | Seminário | chatgpt, gemini, perplexity | `saida_kambalhota/` |
| `lumen` | Escola Lumen | Seminário | chatgpt, gemini, perplexity | `saida_lumen/` |

Cada cliente grava **só na própria pasta** — rodar um nunca altera os resultados de outro.
As perguntas 26–29 usam o nome da escola; as perguntas 1–25 e 30 são neutras e iguais
para todos (exceto o bairro em 13, 14, 15 e 30).

**Ordem por plataforma:** 1–25 → 30 → 26, 27, 28, 29 (as quatro com o nome da escola sempre por último).

### Detecção de menção
- Sempre ignora acentos e maiúsculas/minúsculas.
- **Lumen:** "Escola Lumen", "Colégio Lumen" (e "Centro Educacional Lumen") sempre contam.
  "Lumen" sozinho só conta quando escrito como nome próprio (L maiúsculo) **e** em contexto
  de escola (perto de palavras como escola, educação infantil, Seminário, turmas…, ou como
  item de lista). Não conta: "800 lúmens", "fluxo luminoso em lumen", "Lumen Gentium",
  "lúmen intestinal" etc. (lista de exclusões em `config.py` → `excluir_contexto`).
- **Kambalhota:** "Kambalhota", "Centro Educacional Kambalhota", "CE Kambalhota".

## 1. Instalação (Windows)

Requisito: Python 3.10+ (python.org → marque "Add Python to PATH").

```powershell
cd C:\Projetos\pesquisa-visibilidade-ia
py -m venv .venv
.\.venv\Scripts\Activate.ps1      # se bloquear: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
py -m pip install -r requirements.txt
py -m playwright install chromium
py verificar.py                   # auto-diagnóstico (não abre navegador)
```

## 2. Login (uma vez só)

A automação **não** contorna login nem CAPTCHA. Faça o login manualmente; o perfil fica
salvo em `perfis/` e serve para todos os clientes.

```powershell
py main.py login --plataforma chatgpt
py main.py login --plataforma gemini
py main.py login --plataforma perplexity
```

Se o Google recusar o login no Chromium da automação, mude `NAVEGADOR_CANAL = "chrome"` no `config.py`.

## 3. Teste e execução — Escola Lumen

```powershell
py main.py teste --cliente lumen                          # P1 nas 3 plataformas → saida_lumen\pesquisa_visibilidade_teste.xlsx
py main.py executar --cliente lumen                       # 30 × 3 = 90 consultas
py main.py executar --cliente lumen --plataforma chatgpt  # só uma plataforma
py main.py executar --cliente lumen --apenas-erros        # refaz só as que falharam
py main.py exportar --cliente lumen                       # regenera o Excel
```

(Para os outros clientes, troque `--cliente lumen` por `geracao` ou `kambalhota`.)

- Pausa aleatória de 25–45 s entre consultas (`config.py` → `TEMPOS`).
- **Ctrl+C a qualquer momento**: rode o mesmo comando depois; consultas concluídas são puladas.
- Falhas ficam registradas com screenshot + HTML em `saida_lumen\screenshots\` e a execução segue.
- Se a sessão cair, a plataforma é interrompida e o script pede para refazer o login.
- Dica: desative a "Memória" do ChatGPT para que conversas anteriores não influenciem as respostas.

## 4. Resultados (em `saida_lumen/`)

| Arquivo | Conteúdo |
|---|---|
| `resultados.jsonl` | log de todas as tentativas, gravado na hora (fonte da verdade) |
| `pesquisa_visibilidade.xlsx` | aba **Consultas** (13 colunas) + aba **Análise** |
| `screenshots/` | evidências de falhas (PNG + HTML) |

**Integridade:** "Não" = a IA respondeu e não citou a escola; status `erro`/`erro_login` = falha
técnica (célula Sim/Não fica vazia, não conta como ausência); `resposta_insuficiente` = respondeu
sem conteúdo aproveitável. Nada é inventado.

## 5. Manutenção

Os seletores CSS de cada plataforma ficam em `config.py` → `CONFIG_PLATAFORMAS`. Se uma
interface mudar, inspecione o elemento no navegador (F12), atualize o seletor e rode `py main.py teste --cliente lumen`.

## 6. Nota ética

Perguntas neutras, respeito a login/limites/CAPTCHA, pausas entre consultas e volume baixo.
Automatizar interfaces web pode conflitar com os Termos de Uso das plataformas — use com moderação.
