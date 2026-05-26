# reCAPTCHA Invisible Bypass — Playwright

> 🇧🇷 Português | 🇺🇸 [English below](#english-version)

---

Exemplo genérico de como contornar o **reCAPTCHA Invisible** em formulários de login usando Playwright.

---

## Como o reCAPTCHA Invisible funciona

O reCAPTCHA Invisible (v2 invisible / v3) **não exige interação do usuário** — não tem caixinha para marcar. Ele roda silenciosamente em background quando o formulário é submetido e analisa sinais do browser para decidir se é humano ou bot:

- Fingerprint do browser (User-Agent, plugins, canvas, WebGL)
- Presença de `navigator.webdriver = true` (flag padrão em browsers automatizados)
- Histórico de interações com o Google
- Comportamento de mouse e teclado

Se a requisição vier de um script HTTP puro (`requests`, `httpx`, `curl`), **o token do reCAPTCHA não é gerado** e o servidor rejeita o login.

---

## A solução

Usar um **browser real** (Chromium via Playwright) que executa o JavaScript do Google normalmente, com algumas técnicas para não ser detectado como automação:

| Técnica | O que faz |
|---|---|
| `--disable-blink-features=AutomationControlled` | Remove flag do Chrome que indica controle por WebDriver |
| `navigator.webdriver = undefined` | Sobrescreve a propriedade JS que sites verificam |
| User-Agent real | Evita detecção por string de UA genérica |
| `wait_until="networkidle"` | Garante que o JS do reCAPTCHA carregou antes de interagir |

Após o login, o browser é **fechado imediatamente**. Os cookies de sessão capturados são usados em todas as requisições seguintes via HTTP puro — sem manter nenhuma instância de browser aberta.

---

## Instalação

```bash
pip install -r requirements.txt
playwright install chromium
```

---

## Uso via CLI

```bash
# Headless (browser invisível)
python bypass.py --url https://exemplo.com/login --email user@email.com --senha minhasenha

# Com browser visível (útil para debug ou quando o reCAPTCHA exige interação manual)
python bypass.py --url https://exemplo.com/login --email user@email.com --senha minhasenha --no-headless

# Especificando o padrão da URL de sucesso pós-login
python bypass.py --url https://exemplo.com/login --email user@email.com --senha minhasenha --success "**/home**"
```

---

## Uso como módulo (síncrono)

```python
from bypass import _do_login_sync

cookies = _do_login_sync(
    login_url="https://exemplo.com/login",
    email="user@email.com",
    senha="minhasenha",
    headless=True,
    success_url_pattern="**/dashboard**",
    email_selector='input[name="email"]',
    senha_selector='input[name="password"]',
    cookie_names=["session_id", "csrf_token"],  # None = captura todos
)

# Usa os cookies nas próximas requisições via httpx/requests
import httpx
resp = httpx.get(
    "https://exemplo.com/api/dados",
    headers={"Cookie": "; ".join(f"{k}={v}" for k, v in cookies.items())}
)
```

---

## Uso como módulo (async — FastAPI / uvicorn)

```python
from bypass import login_async

cookies = await login_async(
    login_url="https://exemplo.com/login",
    email="user@email.com",
    senha="minhasenha",
)
```

O Playwright roda em thread separada via `run_in_executor` para não bloquear o loop de eventos do asyncio.

---

## Fluxo resumido

```
1. Abre Chromium headless disfarçado de browser real
2. Navega até a página de login (aguarda networkidle)
3. Preenche email e senha
4. Clica em submit → reCAPTCHA Invisible dispara em background
5. Google avalia o browser e aprova (ou não)
6. Servidor redireciona para URL de sucesso
7. Captura cookies de sessão
8. Fecha o browser
9. Usa os cookies em requisições HTTP puras daqui em diante
```

---
---

# English Version

> 🇺🇸 English | 🇧🇷 [Português acima](#recaptcha-invisible-bypass--playwright)

---

Generic example of how to bypass **Invisible reCAPTCHA** on login forms using Playwright.

---

## How Invisible reCAPTCHA works

Invisible reCAPTCHA (v2 invisible / v3) **requires no user interaction** — there is no checkbox to tick. It runs silently in the background when the form is submitted and analyzes browser signals to decide whether the visitor is human or a bot:

- Browser fingerprint (User-Agent, plugins, canvas, WebGL)
- Presence of `navigator.webdriver = true` (default flag in automated browsers)
- History of interactions with Google
- Mouse and keyboard behavior

If the request comes from a plain HTTP script (`requests`, `httpx`, `curl`), **the reCAPTCHA token is never generated** and the server rejects the login.

---

## The solution

Use a **real browser** (Chromium via Playwright) that runs Google's JavaScript normally, combined with a few techniques to avoid being detected as automation:

| Technique | What it does |
|---|---|
| `--disable-blink-features=AutomationControlled` | Removes the Chrome flag that signals WebDriver control |
| `navigator.webdriver = undefined` | Overwrites the JS property that sites check for bots |
| Real User-Agent | Avoids detection by a generic or headless UA string |
| `wait_until="networkidle"` | Ensures reCAPTCHA's JS has loaded before interacting |

After login, the browser is **closed immediately**. The captured session cookies are used in all subsequent requests via plain HTTP — no browser instance stays open.

---

## Installation

```bash
pip install -r requirements.txt
playwright install chromium
```

---

## CLI usage

```bash
# Headless (invisible browser)
python bypass.py --url https://example.com/login --email user@email.com --senha mypassword

# With visible browser (useful for debugging or when reCAPTCHA requires manual interaction)
python bypass.py --url https://example.com/login --email user@email.com --senha mypassword --no-headless

# Specifying the post-login success URL pattern
python bypass.py --url https://example.com/login --email user@email.com --senha mypassword --success "**/home**"
```

---

## Module usage (synchronous)

```python
from bypass import _do_login_sync

cookies = _do_login_sync(
    login_url="https://example.com/login",
    email="user@email.com",
    senha="mypassword",
    headless=True,
    success_url_pattern="**/dashboard**",
    email_selector='input[name="email"]',
    senha_selector='input[name="password"]',
    cookie_names=["session_id", "csrf_token"],  # None = capture all
)

# Use the cookies in subsequent requests via httpx/requests
import httpx
resp = httpx.get(
    "https://example.com/api/data",
    headers={"Cookie": "; ".join(f"{k}={v}" for k, v in cookies.items())}
)
```

---

## Module usage (async — FastAPI / uvicorn)

```python
from bypass import login_async

cookies = await login_async(
    login_url="https://example.com/login",
    email="user@email.com",
    senha="mypassword",
)
```

Playwright runs in a separate thread via `run_in_executor` so it does not block the asyncio event loop.

---

## Flow summary

```
1. Open headless Chromium disguised as a real browser
2. Navigate to the login page (wait for networkidle)
3. Fill in email and password
4. Click submit → Invisible reCAPTCHA fires in the background
5. Google evaluates the browser and approves (or not)
6. Server redirects to the success URL
7. Capture session cookies
8. Close the browser
9. Use the cookies in plain HTTP requests from this point on
```
