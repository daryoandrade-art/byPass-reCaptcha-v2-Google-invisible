# reCAPTCHA Invisible Bypass — Playwright

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
