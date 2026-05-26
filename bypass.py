"""
bypass.py — Exemplo genérico de bypass de reCAPTCHA Invisible com Playwright

Como funciona o reCAPTCHA Invisible:
  - Diferente do reCAPTCHA v2 (caixinha "Não sou um robô"), o Invisible não exige
    interação do usuário. Ele roda silenciosamente em background ao submeter o form.
  - O Google analisa o comportamento do browser (mouse, fingerprint, histórico)
    e decide se é humano ou bot.
  - Se a requisição vier de um script HTTP puro (requests, httpx, curl), o token
    não é gerado e o login é bloqueado.

A solução:
  - Usar um browser real (Chromium via Playwright) que executa o JavaScript do Google.
  - Disfarçar sinais de automação para não ser detectado como bot.
  - Após o login bem-sucedido, capturar os cookies de sessão e fechar o browser.
  - Todas as requisições seguintes usam esses cookies via HTTP puro (sem browser).

Uso:
  python bypass.py --url https://exemplo.com/login --email user@email.com --senha minhasenha
  python bypass.py --url https://exemplo.com/login --email user@email.com --senha minhasenha --no-headless
"""

import asyncio
import logging
import sys
import argparse
from concurrent.futures import ThreadPoolExecutor

from playwright.sync_api import (
    sync_playwright,
    Browser,
    BrowserContext,
    Page,
    TimeoutError as PlaywrightTimeoutError,
)

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Executor dedicado — Playwright sync roda em thread separada para não
# conflitar com o loop de eventos do asyncio (necessário no Windows)
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="playwright")

LOGIN_TIMEOUT_MS = 60_000  # tempo máximo aguardando o redirect pós-login


# ---------------------------------------------------------------------------
# Core: login com Playwright (síncrono, roda em thread)
# ---------------------------------------------------------------------------

def _do_login_sync(
    login_url: str,
    email: str,
    senha: str,
    headless: bool = True,
    success_url_pattern: str = "**/dashboard**",
    email_selector: str = 'input[name="email"]',
    senha_selector: str = 'input[name="senha"]',
    submit_selector: str = 'button[type="submit"], input[type="submit"]',
    cookie_names: list[str] | None = None,
) -> dict[str, str]:
    """
    Abre o Chromium, preenche o formulário de login e aguarda o reCAPTCHA resolver.

    Parâmetros:
        login_url           — URL da página de login
        email               — credencial de acesso
        senha               — senha
        headless            — True = browser invisível | False = browser visível
        success_url_pattern — padrão glob da URL após login bem-sucedido
        email_selector      — seletor CSS do campo de email
        senha_selector      — seletor CSS do campo de senha
        submit_selector     — seletor CSS do botão de submit
        cookie_names        — lista de cookies a capturar (None = todos)

    Retorna:
        dict com os cookies de sessão capturados após o login
    """

    # No Windows o sync_playwright precisa do ProactorEventLoop internamente
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    with sync_playwright() as p:
        # ----------------------------------------------------------------
        # 1. Lança o browser disfarçado de usuário real
        # ----------------------------------------------------------------
        browser: Browser = p.chromium.launch(
            headless=headless,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                # Remove flag que indica ao site que é um browser controlado
                "--disable-blink-features=AutomationControlled",
            ],
        )

        context: BrowserContext = browser.new_context(
            # User-Agent de um Chrome real no Windows — evita detecção por UA
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768},
            locale="pt-BR",
        )

        page: Page = context.new_page()

        # ----------------------------------------------------------------
        # 2. Remove navigator.webdriver = true (principal flag de detecção)
        #    Esse script roda antes de qualquer JS da página
        # ----------------------------------------------------------------
        page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )

        captured_cookies: dict[str, str] = {}

        try:
            # ----------------------------------------------------------------
            # 3. Navega até a página de login e aguarda carregar completamente
            #    wait_until="networkidle" garante que o JS do reCAPTCHA já carregou
            # ----------------------------------------------------------------
            logger.info(f"Abrindo: {login_url}")
            page.goto(login_url, wait_until="networkidle", timeout=30_000)

            # ----------------------------------------------------------------
            # 4. Preenche o formulário
            # ----------------------------------------------------------------
            page.wait_for_selector(email_selector, timeout=15_000)
            logger.info("Preenchendo credenciais...")
            page.fill(email_selector, email)
            page.fill(senha_selector, senha)

            # ----------------------------------------------------------------
            # 5. Clica em submit
            #    O reCAPTCHA Invisible dispara automaticamente aqui.
            #    O Google avalia o comportamento do browser em background.
            #    Se aprovado, o form é submetido e o servidor redireciona.
            # ----------------------------------------------------------------
            logger.info("Submetendo formulário — aguardando reCAPTCHA resolver...")
            page.locator(submit_selector).first.click()

            # ----------------------------------------------------------------
            # 6. Aguarda o redirecionamento para a URL de sucesso
            #    Esse é o sinal de que o reCAPTCHA foi aprovado e o login ocorreu
            # ----------------------------------------------------------------
            page.wait_for_url(success_url_pattern, timeout=LOGIN_TIMEOUT_MS)
            logger.info("Login bem-sucedido! Capturando cookies...")

            # ----------------------------------------------------------------
            # 7. Captura os cookies de sessão
            #    A partir daqui o browser não é mais necessário.
            #    As próximas requisições usam esses cookies via HTTP puro.
            # ----------------------------------------------------------------
            all_cookies = context.cookies()
            for c in all_cookies:
                if cookie_names is None or c["name"] in cookie_names:
                    captured_cookies[c["name"]] = c["value"]

            logger.info(f"Cookies capturados: {list(captured_cookies.keys())}")
            return captured_cookies

        except Exception as e:
            import traceback
            logger.error(f"Falha no login:\n{traceback.format_exc()}")
            # Salva screenshot para diagnóstico
            try:
                page.screenshot(path="login_error.png")
                logger.error("Screenshot salvo em login_error.png")
            except Exception:
                pass
            raise RuntimeError(f"Falha no login: {type(e).__name__}: {e}") from e

        finally:
            # Browser sempre fechado ao final — não fica instância aberta
            browser.close()
            logger.info("Browser encerrado.")


# ---------------------------------------------------------------------------
# Interface assíncrona (para uso em projetos com asyncio/FastAPI)
# ---------------------------------------------------------------------------

async def login_async(
    login_url: str,
    email: str,
    senha: str,
    headless: bool = True,
    success_url_pattern: str = "**/dashboard**",
    email_selector: str = 'input[name="email"]',
    senha_selector: str = 'input[name="senha"]',
    submit_selector: str = 'button[type="submit"], input[type="submit"]',
    cookie_names: list[str] | None = None,
) -> dict[str, str]:
    """
    Versão async de _do_login_sync.
    Roda o Playwright em thread separada para não bloquear o loop de eventos.
    Ideal para uso com FastAPI, uvicorn ou qualquer servidor async.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        lambda: _do_login_sync(
            login_url=login_url,
            email=email,
            senha=senha,
            headless=headless,
            success_url_pattern=success_url_pattern,
            email_selector=email_selector,
            senha_selector=senha_selector,
            submit_selector=submit_selector,
            cookie_names=cookie_names,
        ),
    )


# ---------------------------------------------------------------------------
# Execução direta via CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Bypass de reCAPTCHA Invisible via Playwright"
    )
    parser.add_argument("--url",         required=True,  help="URL da página de login")
    parser.add_argument("--email",       required=True,  help="Email de acesso")
    parser.add_argument("--senha",       required=True,  help="Senha")
    parser.add_argument("--success",     default="**/dashboard**", help="Padrão glob da URL pós-login")
    parser.add_argument("--no-headless", action="store_true",      help="Exibe o browser (útil para debug)")
    args = parser.parse_args()

    cookies = _do_login_sync(
        login_url=args.url,
        email=args.email,
        senha=args.senha,
        headless=not args.no_headless,
        success_url_pattern=args.success,
    )

    print("\nCookies capturados:")
    for name, value in cookies.items():
        print(f"  {name} = {value[:40]}{'...' if len(value) > 40 else ''}")
