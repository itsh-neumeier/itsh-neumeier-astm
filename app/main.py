import os
from urllib.parse import urlparse
from typing import Annotated

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import __version__
from .generator import apply_config, asterisk_status, render
from .i18n import SUPPORTED_LANGUAGES, get_language, translate
from .monitoring import build_monitoring_snapshot, tail_file
from .security import SESSION_COOKIE, create_session, load_secret, verify_session
from .store import Store


DATA_DIR = os.getenv("DATA_DIR", "/data")
store = Store(DATA_DIR)
generated_admin_password = store.init()
secret = load_secret(DATA_DIR)

if generated_admin_password:
    print("================================================================", flush=True)
    print("Initial admin login created", flush=True)
    print("User: admin", flush=True)
    print(f"Password: {generated_admin_password}", flush=True)
    print("Set ADMIN_PASSWORD before first start for a fixed password.", flush=True)
    print("================================================================", flush=True)

app = FastAPI(title="ITSH Neumeier Asterisk WebGUI AIO", version=__version__)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


def current_user(request: Request) -> str:
    username = verify_session(request.cookies.get(SESSION_COOKIE), secret)
    if not username:
        raise PermissionError
    return username


def redirect(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=303)


def safe_referer(request: Request) -> str:
    referer = request.headers.get("referer", "/")
    parsed = urlparse(referer)
    if parsed.netloc and parsed.netloc != request.url.netloc:
        return "/"
    return parsed.path or "/"


def context(request: Request, user: str, **extra):
    settings = store.get_settings()
    lang = get_language(request)
    base = {
        "request": request,
        "user": user,
        "version": __version__,
        "settings": settings,
        "lang": lang,
        "t": lambda key: translate(lang, key),
    }
    base.update(extra)
    return base


@app.exception_handler(PermissionError)
async def auth_exception_handler(request: Request, exc: PermissionError):
    return redirect("/login")


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    lang = get_language(request)
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "version": __version__,
            "error": None,
            "lang": lang,
            "t": lambda key: translate(lang, key),
        },
    )


@app.get("/language/{lang}")
def set_language(lang: str, request: Request):
    response = redirect(safe_referer(request))
    if lang in SUPPORTED_LANGUAGES:
        response.set_cookie("lang", lang, max_age=365 * 24 * 60 * 60, samesite="lax")
    return response


@app.post("/login")
def login(
    request: Request,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
):
    if not store.authenticate(username, password):
        lang = get_language(request)
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "version": __version__,
                "error": translate(lang, "login_failed"),
                "lang": lang,
                "t": lambda key: translate(lang, key),
            },
            status_code=401,
        )
    response = redirect("/")
    response.set_cookie(
        SESSION_COOKIE,
        create_session(username, secret),
        httponly=True,
        samesite="lax",
        max_age=12 * 60 * 60,
    )
    return response


@app.post("/logout")
def logout():
    response = redirect("/login")
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, user: str = Depends(current_user)):
    status = asterisk_status()
    return templates.TemplateResponse(
        "dashboard.html",
        context(
            request,
            user,
            numbers=store.list_rows("numbers"),
            clients=store.list_rows("clients"),
            inbound=store.list_rows("routes_inbound"),
            outbound=store.list_rows("routes_outbound"),
            status=status[:4000],
        ),
    )


@app.get("/monitoring", response_class=HTMLResponse)
def monitoring_page(request: Request, user: str = Depends(current_user)):
    snapshot = build_monitoring_snapshot(store)
    return templates.TemplateResponse(
        "monitoring.html",
        context(
            request,
            user,
            provider_statuses=snapshot["provider_statuses"],
            latest_calls=snapshot["latest_calls"],
            raw=snapshot["raw"],
            log=snapshot["log"],
        ),
    )


@app.get("/monitoring/logs", response_class=PlainTextResponse)
def monitoring_logs(user: str = Depends(current_user)):
    return tail_file(lines=250)


@app.get("/settings", response_class=HTMLResponse)
def settings_form(request: Request, user: str = Depends(current_user)):
    return templates.TemplateResponse("settings.html", context(request, user))


@app.post("/settings")
def settings_save(
    asterisk_ip: Annotated[str, Form()],
    unifi_ip: Annotated[str, Form()],
    unifi_port: Annotated[str, Form()],
    unifi_range: Annotated[str, Form()],
    provider_display_name: Annotated[str, Form()],
    provider_registrar: Annotated[str, Form()],
    provider_server_uri: Annotated[str, Form()],
    provider_from_domain: Annotated[str, Form()],
    external_signaling_address: Annotated[str, Form()] = "",
    external_media_address: Annotated[str, Form()] = "",
    local_net: Annotated[str, Form()] = "",
    provider_match_ip: Annotated[str, Form()] = "",
    provider_transport: Annotated[str, Form()] = "udp",
    provider_outbound_proxy: Annotated[str, Form()] = "",
    provider_use_registration: Annotated[str, Form()] = "no",
    user: str = Depends(current_user),
):
    store.update_settings(
        {
            "asterisk_ip": asterisk_ip,
            "unifi_ip": unifi_ip,
            "unifi_port": unifi_port,
            "unifi_range": unifi_range,
            "external_signaling_address": external_signaling_address,
            "external_media_address": external_media_address,
            "local_net": local_net,
            "provider_display_name": provider_display_name,
            "provider_registrar": provider_registrar,
            "provider_server_uri": provider_server_uri,
            "provider_from_domain": provider_from_domain,
            "provider_match_ip": provider_match_ip,
            "provider_transport": provider_transport,
            "provider_outbound_proxy": provider_outbound_proxy,
            "provider_use_registration": provider_use_registration,
        }
    )
    return redirect("/settings")


@app.get("/numbers", response_class=HTMLResponse)
def numbers_page(request: Request, user: str = Depends(current_user)):
    return templates.TemplateResponse(
        "numbers.html", context(request, user, numbers=store.list_rows("numbers"))
    )


@app.post("/numbers")
def add_number(
    did_plus: Annotated[str, Form()],
    sip_username: Annotated[str, Form()],
    sip_password: Annotated[str, Form()],
    user: str = Depends(current_user),
):
    store.add_number(did_plus, sip_username, sip_password)
    return redirect("/numbers")


@app.post("/numbers/{number_id}")
def update_number(
    number_id: int,
    did_plus: Annotated[str, Form()],
    sip_username: Annotated[str, Form()],
    sip_password: Annotated[str, Form()],
    user: str = Depends(current_user),
):
    store.update_number(number_id, did_plus, sip_username, sip_password)
    return redirect("/numbers")


@app.post("/numbers/{number_id}/provision-unifi")
def provision_unifi_number(number_id: int, user: str = Depends(current_user)):
    store.provision_unifi_number(number_id)
    return redirect("/routes")


@app.post("/delete/{table}/{row_id}")
def delete_row(table: str, row_id: int, user: str = Depends(current_user)):
    store.delete_row(table, row_id)
    return redirect("/" + ("routes" if table.startswith("routes_") else table))


@app.get("/clients", response_class=HTMLResponse)
def clients_page(request: Request, user: str = Depends(current_user)):
    return templates.TemplateResponse(
        "clients.html", context(request, user, clients=store.list_rows("clients"))
    )


@app.post("/clients")
def add_client(
    client_id: Annotated[str, Form()],
    name: Annotated[str, Form()],
    extension: Annotated[str, Form()],
    sip_username: Annotated[str, Form()],
    sip_password: Annotated[str, Form()],
    ip_acl: Annotated[str, Form()] = "",
    caller_id_plus: Annotated[str, Form()] = "",
    client_type: Annotated[str, Form()] = "generic",
    audio_codecs: Annotated[str, Form()] = "alaw,ulaw",
    video_profile: Annotated[str, Form()] = "none",
    enabled: Annotated[str | None, Form()] = None,
    user: str = Depends(current_user),
):
    video_codecs_by_profile = {
        "none": "",
        "h264": "h264",
        "h264_vp8": "h264,vp8",
    }
    store.add_client(
        {
            "client_id": client_id,
            "name": name,
            "extension": extension,
            "sip_username": sip_username,
            "sip_password": sip_password,
            "ip_acl": ip_acl,
            "caller_id_plus": caller_id_plus,
            "client_type": client_type,
            "audio_codecs": audio_codecs,
            "enabled": enabled,
            "video_enabled": video_profile != "none",
            "video_codecs": video_codecs_by_profile.get(video_profile, ""),
        }
    )
    return redirect("/clients")


@app.post("/clients/{row_id}")
def update_client(
    row_id: int,
    client_id: Annotated[str, Form()],
    name: Annotated[str, Form()],
    extension: Annotated[str, Form()],
    sip_username: Annotated[str, Form()],
    sip_password: Annotated[str, Form()],
    ip_acl: Annotated[str, Form()] = "",
    caller_id_plus: Annotated[str, Form()] = "",
    client_type: Annotated[str, Form()] = "generic",
    audio_codecs: Annotated[str, Form()] = "alaw,ulaw",
    video_profile: Annotated[str, Form()] = "none",
    enabled: Annotated[str | None, Form()] = None,
    user: str = Depends(current_user),
):
    video_codecs_by_profile = {
        "none": "",
        "h264": "h264",
        "h264_vp8": "h264,vp8",
    }
    store.update_client(
        row_id,
        {
            "client_id": client_id,
            "name": name,
            "extension": extension,
            "sip_username": sip_username,
            "sip_password": sip_password,
            "ip_acl": ip_acl,
            "caller_id_plus": caller_id_plus,
            "client_type": client_type,
            "audio_codecs": audio_codecs,
            "enabled": enabled,
            "video_enabled": video_profile != "none",
            "video_codecs": video_codecs_by_profile.get(video_profile, ""),
        },
    )
    return redirect("/clients")


@app.get("/routes", response_class=HTMLResponse)
def routes_page(request: Request, user: str = Depends(current_user)):
    numbers = store.list_rows("numbers")
    return templates.TemplateResponse(
        "routes.html",
        context(
            request,
            user,
            numbers=numbers,
            numbers_by_id={number["id"]: number["did_plus"] for number in numbers},
            inbound=store.list_rows("routes_inbound"),
            outbound=store.list_rows("routes_outbound"),
        ),
    )


@app.post("/routes/inbound")
def add_inbound_route(
    did_plus: Annotated[str, Form()],
    target_type: Annotated[str, Form()],
    target_id: Annotated[str, Form()],
    ring_seconds: Annotated[int, Form()] = 45,
    description: Annotated[str, Form()] = "",
    user: str = Depends(current_user),
):
    store.add_inbound_route(locals())
    return redirect("/routes")


@app.post("/routes/inbound/{route_id}")
def update_inbound_route(
    route_id: int,
    did_plus: Annotated[str, Form()],
    target_type: Annotated[str, Form()],
    target_id: Annotated[str, Form()],
    ring_seconds: Annotated[int, Form()] = 45,
    description: Annotated[str, Form()] = "",
    user: str = Depends(current_user),
):
    store.update_inbound_route(route_id, locals())
    return redirect("/routes")


@app.post("/routes/outbound")
def add_outbound_route(
    source_type: Annotated[str, Form()],
    source_id: Annotated[str, Form()],
    number_id: Annotated[int, Form()],
    caller_id_plus: Annotated[str, Form()] = "",
    description: Annotated[str, Form()] = "",
    user: str = Depends(current_user),
):
    store.add_outbound_route(locals())
    return redirect("/routes")


@app.post("/routes/outbound/{route_id}")
def update_outbound_route(
    route_id: int,
    source_type: Annotated[str, Form()],
    source_id: Annotated[str, Form()],
    number_id: Annotated[int, Form()],
    caller_id_plus: Annotated[str, Form()] = "",
    description: Annotated[str, Form()] = "",
    user: str = Depends(current_user),
):
    store.update_outbound_route(route_id, locals())
    return redirect("/routes")


@app.get("/preview", response_class=HTMLResponse)
def preview_page(request: Request, user: str = Depends(current_user)):
    rendered = render(store)
    return templates.TemplateResponse(
        "preview.html", context(request, user, rendered=rendered, result=None)
    )


@app.post("/apply", response_class=HTMLResponse)
def apply_page(request: Request, user: str = Depends(current_user)):
    result = apply_config(store, reload_asterisk=True)
    rendered = render(store)
    return templates.TemplateResponse(
        "preview.html", context(request, user, rendered=rendered, result=result)
    )


@app.get("/unifi", response_class=HTMLResponse)
def unifi_page(request: Request, user: str = Depends(current_user)):
    return templates.TemplateResponse(
        "text.html",
        context(request, user, title="UniFi Talk Konfiguration", text=render(store).unifi_summary),
    )


@app.get("/healthz")
def healthz():
    return {"ok": True, "version": __version__}
