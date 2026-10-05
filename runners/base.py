"""
Executor genérico de uma plataforma de IA, guiado pelos seletores do config.py.

Fluxo de cada consulta:
  nova_conversa() → verificar login → digitar() → enviar() →
  aguardar_resposta() (texto estável + sem botão "parar") → capturar texto e links

A automação NÃO contorna login, CAPTCHA ou limites: se a sessão cair,
levanta ErroLogin e o usuário refaz o login manualmente.
"""

import time
from datetime import datetime
from pathlib import Path

import config

# JS: devolve o texto visível da resposta com a numeração das listas <ol>
# (o innerText do navegador omite os marcadores "1.", "2." ...).
_JS_TEXTO = """
(el) => {
  const extras = [];
  el.querySelectorAll('ol').forEach(ol => {
    let n = parseInt(ol.getAttribute('start') || '1', 10);
    Array.from(ol.children).forEach(li => {
      if (li.tagName !== 'LI') return;
      const s = document.createElement('span');
      s.textContent = (n++) + '. ';
      li.insertBefore(s, li.firstChild);
      extras.push(s);
    });
  });
  const texto = el.innerText;
  extras.forEach(s => s.remove());
  return texto;
}
"""

_JS_LINKS = """
(els) => {
  const out = [];
  els.forEach(el => el.querySelectorAll('a[href]').forEach(a =>
      out.push({href: a.href, texto: (a.innerText || '').trim()})));
  return out;
}
"""


class ErroLogin(Exception):
    """Sessão deslogada: o usuário precisa rodar `main.py login`."""


def abrir_contexto(playwright, plataforma: str):
    """Abre o Chromium com o perfil salvo da plataforma (login persistente)."""
    perfil = config.PASTA_PERFIS / plataforma
    perfil.mkdir(parents=True, exist_ok=True)
    opcoes = dict(user_data_dir=str(perfil), headless=False, no_viewport=True,
                  locale="pt-BR", timezone_id="America/Sao_Paulo")
    if config.NAVEGADOR_CANAL:
        opcoes["channel"] = config.NAVEGADOR_CANAL
    return playwright.chromium.launch_persistent_context(**opcoes)


def _erro_de_rede(exc: Exception) -> bool:
    msg = str(exc)
    return "net::ERR" in msg or "Timeout" in type(exc).__name__ or "Timeout" in msg


class ExecutorPlataforma:
    def __init__(self, contexto, plataforma: str, pasta_screenshots: Path):
        self.contexto = contexto
        self.plataforma = plataforma
        self.cfg = config.CONFIG_PLATAFORMAS[plataforma]
        self.pasta_screenshots = pasta_screenshots
        self.page = contexto.pages[0] if contexto.pages else contexto.new_page()
        self.page.set_default_timeout(config.TEMPOS["carregar_pagina"] * 1000)

    # ------------------------------------------------------------------
    def _visivel(self, seletor: str) -> bool:
        if not seletor:
            return False
        try:
            loc = self.page.locator(seletor)
            return any(loc.nth(i).is_visible() for i in range(min(loc.count(), 5)))
        except Exception:
            return False

    def verificar_login(self):
        for s in self.cfg.get("indicadores_login", []):
            if self._visivel(s):
                raise ErroLogin(f"Sessão deslogada em {self.cfg['nome']} (indicador: {s})")
        url = self.page.url.lower()
        if any(t in url for t in ("/login", "/auth", "accounts.google.com/signin", "servicelogin")):
            raise ErroLogin(f"Sessão deslogada em {self.cfg['nome']} (URL de login: {self.page.url})")

    def nova_conversa(self):
        """Abre a URL de conversa nova. Erro de rede/timeout → espera e tenta 1 vez mais."""
        for tentativa in (1, 2):
            try:
                self.page.goto(self.cfg["url_nova"], wait_until="domcontentloaded")
                self.page.wait_for_timeout(3000)
                return
            except Exception as exc:
                if tentativa == 2 or not _erro_de_rede(exc):
                    raise
                print(f"    rede instável ({str(exc)[:80]}); nova tentativa em "
                      f"{config.TEMPOS['espera_retentativa']}s")
                time.sleep(config.TEMPOS["espera_retentativa"])

    def digitar(self, texto: str):
        """Digita a pergunta. Se a caixa não aparecer, recarrega e tenta mais uma vez."""
        seletor = self.cfg["seletor_entrada"]
        for tentativa in (1, 2):
            try:
                caixa = self.page.locator(seletor).first
                caixa.wait_for(state="visible", timeout=config.TEMPOS["esperar_entrada"] * 1000)
                caixa.click()
                try:
                    caixa.fill(texto)
                except Exception:
                    self.page.keyboard.type(texto, delay=15)
                self.page.wait_for_timeout(500)
                return
            except Exception:
                self.verificar_login()
                if tentativa == 2:
                    raise
                self.page.reload(wait_until="domcontentloaded")
                self.page.wait_for_timeout(4000)

    def enviar(self):
        botao = self.cfg.get("seletor_botao_enviar")
        if botao:
            try:
                loc = self.page.locator(botao).first
                loc.wait_for(state="visible", timeout=5000)
                if loc.is_enabled():
                    loc.click()
                    return
            except Exception:
                pass
        self.page.keyboard.press("Enter")

    def _elementos_resposta(self):
        for s in self.cfg["seletores_resposta"]:
            loc = self.page.locator(s)
            try:
                if loc.count() > 0:
                    return loc
            except Exception:
                continue
        return None

    def aguardar_resposta(self):
        """Espera a resposta terminar: texto parado por N s e sem botão 'parar'.
        Retorna (texto, completa: bool)."""
        t = config.TEMPOS
        inicio = time.time()
        while time.time() - inicio < t["inicio_resposta"]:
            loc = self._elementos_resposta()
            if loc is not None and self._texto(loc.last).strip():
                break
            self.page.wait_for_timeout(1000)
        else:
            self.verificar_login()
            raise TimeoutError("A resposta não começou a aparecer (verifique seletores_resposta)")

        ultimo, desde = "", time.time()
        while time.time() - inicio < t["resposta_max"]:
            self.page.wait_for_timeout(1500)
            loc = self._elementos_resposta()
            atual = self._texto(loc.last) if loc is not None else ""
            gerando = self._visivel(self.cfg.get("seletor_parando", ""))
            if atual != ultimo or gerando:
                ultimo, desde = atual, time.time()
            elif atual.strip() and time.time() - desde >= t["estabilidade"]:
                return atual, True
        return ultimo, False

    def _texto(self, elemento) -> str:
        try:
            return elemento.evaluate(_JS_TEXTO) or ""
        except Exception:
            try:
                return elemento.inner_text()
            except Exception:
                return ""

    def capturar_links(self) -> list:
        links = []
        loc = self._elementos_resposta()
        if loc is not None:
            try:
                links += loc.last.evaluate("(el) => (" + _JS_LINKS + ")([el])")
            except Exception:
                pass
        for s in self.cfg.get("seletores_fontes", []):
            try:
                links += self.page.locator(s).evaluate_all(
                    "(as) => as.map(a => ({href: a.href, texto: (a.innerText||'').trim()}))")
            except Exception:
                pass
        return links

    def salvar_evidencia(self, numero: int, motivo: str) -> str:
        """Screenshot + HTML da página para diagnóstico manual."""
        self.pasta_screenshots.mkdir(parents=True, exist_ok=True)
        base = self.pasta_screenshots / f"{self.plataforma}_P{numero:02d}_{datetime.now():%Y%m%d_%H%M%S}_{motivo}"
        try:
            self.page.screenshot(path=str(base.with_suffix(".png")), full_page=True)
            base.with_suffix(".html").write_text(self.page.content(), encoding="utf-8")
            return base.name
        except Exception:
            return ""

    # ------------------------------------------------------------------
    def consultar(self, numero: int, pergunta: str) -> dict:
        """Executa uma consulta completa. Nunca levanta exceção, exceto ErroLogin
        (para interromper a plataforma) e KeyboardInterrupt."""
        inicio = time.time()
        reg = {"resposta": "", "links": [], "status": "erro", "observacoes": "", "url": ""}
        try:
            self.nova_conversa()
            self.verificar_login()
            self.digitar(pergunta)
            self.enviar()
            texto, completa = self.aguardar_resposta()
            reg["resposta"] = texto.strip()
            reg["links"] = self.capturar_links()
            reg["url"] = self.page.url
            if completa:
                reg["status"] = "ok"
            else:
                reg["observacoes"] = "Tempo máximo excedido; texto parcial salvo (será refeita)."
                reg["evidencia"] = self.salvar_evidencia(numero, "timeout")
        except ErroLogin as exc:
            reg["status"] = "erro_login"
            reg["observacoes"] = str(exc)
            reg["evidencia"] = self.salvar_evidencia(numero, "login")
            reg["duracao_s"] = round(time.time() - inicio, 1)
            raise ErroLoginComRegistro(reg) from exc
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            reg["observacoes"] = f"{type(exc).__name__}: {str(exc).splitlines()[0][:300] if str(exc) else ''}"
            reg["evidencia"] = self.salvar_evidencia(numero, "erro")
        reg["duracao_s"] = round(time.time() - inicio, 1)
        return reg


class ErroLoginComRegistro(ErroLogin):
    def __init__(self, registro: dict):
        super().__init__(registro.get("observacoes", ""))
        self.registro = registro
