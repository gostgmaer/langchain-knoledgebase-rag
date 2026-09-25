"""Preflight check of the environment files the RAG stack depends on.

Reads (never modifies) the real env files of: the RAG API, the RAG frontend, IAM,
the gateway, notification-service and file-upload-service, and reports what is
missing, still a placeholder, too short, or out of sync between services.
Secret VALUES are never printed - only key names and PASS/WARN/FAIL.

    python scripts/preflight_env.py
    python scripts/preflight_env.py --infra "C:/path/to/easydev-infra"
    python scripts/preflight_env.py --providers     # also list provider keys still to fill

Exit code 0 when there are no FAIL lines.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import socket
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent.parent
DEFAULT_INFRA = HERE.parent.parent.parent / "docker network" / "easydev-infra"

PLACEHOLDER = re.compile(r"(change[_-]?me|placeholder|your[_-]|<.+>|^x{3,}$|^todo$|example\.com/?$)", re.I)

results: list[tuple[str, str, str]] = []


def rec(level: str, area: str, msg: str) -> None:
    results.append((level, area, msg))


def load(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if value[:1] in "\"'" and value[-1:] == value[:1] and len(value) >= 2:
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].strip()
        env[key] = value
    return env


def fp(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:8]


def is_placeholder(value: str) -> bool:
    return (not value) or bool(PLACEHOLDER.search(value))


class Env:
    def __init__(self, name: str, *paths: Path):
        self.name = name
        self.paths = paths
        self.missing_files = [p for p in paths if not p.exists()]
        self.values: dict[str, str] = {}
        for p in paths:
            self.values.update(load(p))

    def get(self, key: str) -> str:
        return self.values.get(key, "")

    def require(self, key: str, *, min_len: int = 0, secret: bool = False, url: bool = False, hexlen: int = 0) -> None:
        v = self.get(key)
        area = self.name
        if key not in self.values:
            rec("FAIL", area, f"{key} is not set")
        elif not v:
            rec("FAIL", area, f"{key} is empty")
        elif is_placeholder(v):
            rec("FAIL" if secret or url else "WARN", area, f"{key} still looks like a placeholder")
        elif min_len and len(v) < min_len:
            rec("FAIL", area, f"{key} is too short ({len(v)} chars, needs {min_len}+)")
        elif hexlen and not re.fullmatch(rf"[0-9a-fA-F]{{{hexlen}}}", v):
            rec("FAIL", area, f"{key} must be exactly {hexlen} hex characters")
        elif url and not re.match(r"^[a-z][a-z0-9+.-]*://", v, re.I):
            rec("FAIL", area, f"{key} must be a URL (scheme://host)")
        else:
            rec("PASS", area, f"{key} ok")

    def optional(self, key: str, note: str) -> None:
        v = self.get(key)
        if not v or is_placeholder(v):
            rec("WARN", self.name, f"{key} not set - {note}")


def same(a: Env, ak: str, b: Env, bk: str, why: str) -> None:
    av, bv = a.get(ak), b.get(bk)
    label = f"{a.name}.{ak} == {b.name}.{bk}"
    if not av or not bv:
        rec("FAIL", "match", f"{label}: one side is not set ({why})")
    elif av == bv:
        rec("PASS", "match", f"{label} (fp {fp(av)})")
    else:
        rec("FAIL", "match", f"{label}: values differ (fp {fp(av)} vs {fp(bv)}) - {why}")


def url_port(value: str) -> int | None:
    try:
        return urlparse(value).port
    except ValueError:
        return None


def reachable(uri: str, timeout: float = 2.0) -> bool | None:
    if uri.startswith("mongodb+srv://"):
        return None  # DNS SRV; cannot cheaply probe
    p = urlparse(uri)
    host = p.hostname
    if not host:
        return None
    port = p.port or 27017
    if host in ("host.docker.internal", "mongo", "mongodb"):
        host = "127.0.0.1"
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--infra", default=str(DEFAULT_INFRA))
    ap.add_argument("--all", action="store_true", help="also list passing checks")
    ap.add_argument("--providers", action="store_true", help="also list provider keys still to fill")
    args = ap.parse_args()
    infra = Path(args.infra)
    core = infra / "stacks" / "core" / "env"
    util = infra / "stacks" / "utility" / "env"

    rag = Env("RAG .env", HERE / ".env")
    fe = Env("frontend .env.local", HERE / "frontend" / ".env.local")
    iam = Env("IAM", core / ".env.shared", core / ".env.auth")
    gw = Env("gateway", core / ".env.shared", core / ".env.gateway")
    notif = Env("notification", util / ".env.app")
    upl = Env("file-upload", util / ".env.file-upload")

    for e in (rag, fe, iam, gw, notif, upl):
        for p in e.missing_files:
            rec("FAIL", e.name, f"file not found: {p}")

    # ---------------------------------------------------------------- RAG
    for k in ("DATABASE_URL", "REDIS_URL", "IAM_BASE_URL", "UPLOAD_SERVICE_URL"):
        rag.require(k, url=True)
    rag.require("JWT_SECRET", min_len=16, secret=True)
    for k in ("IAM_CLIENT_ID", "IAM_CLIENT_SECRET"):
        v = rag.get(k)
        if not v:
            rec("FAIL", rag.name, f"{k} is not set (required to boot; a placeholder is fine)")
        else:
            rec("PASS" if not is_placeholder(v) else "WARN", rag.name, f"{k} present" if not is_placeholder(v) else f"{k} is a placeholder (fine - only the unused service-token flow reads it)")
    rag.require("IAM_INTROSPECTION_API_KEY", secret=True)
    rag.require("FILE_UPLOAD_HMAC_SECRET", min_len=32, secret=True)
    for k in ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"):
        rag.require(k, secret=k == "POSTGRES_PASSWORD")
    for k in ("OPENWEATHER_API_KEY", "NEWSAPI_API_KEY"):
        if not rag.get(k):
            rec("FAIL", rag.name, f"{k} is not set (required to boot even if the tool is unused; a placeholder is fine)")
        else:
            rec("PASS", rag.name, f"{k} present")
    prov = (rag.get("LLM_PROVIDER") or "google").lower()
    key_for = {"google": "GOOGLE_API_KEY", "openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "groq": "GROQ_API_KEY"}.get(prov)
    if key_for:
        rag.require(key_for, secret=True)
    rag.require("LLM_MODEL")
    emb_prov = (rag.get("EMBEDDING_PROVIDER") or "google").lower()
    emb_key = key_for if emb_prov == prov else {"google": "GOOGLE_API_KEY", "openai": "OPENAI_API_KEY"}.get(emb_prov)
    if emb_key and emb_key != key_for:
        rag.require(emb_key, secret=True)
    auth_req = rag.get("AUTH_REQUIRED").lower() == "true"
    rec("PASS" if auth_req else "WARN", rag.name, "AUTH_REQUIRED=true" if auth_req else "AUTH_REQUIRED is not true - the API accepts anonymous callers (dev only)")
    if rag.get("VECTOR_STORE_BACKEND", ).lower() != "pgvector":
        rec("WARN", rag.name, "VECTOR_STORE_BACKEND is not pgvector (chroma needs extra setup)")
    if rag.get("LANGCHAIN_TRACING_V2").lower() == "true" and not rag.get("LANGCHAIN_API_KEY"):
        rec("WARN", rag.name, "LANGCHAIN_TRACING_V2=true but LANGCHAIN_API_KEY is empty (set it false)")
    db_pw = re.search(r"://[^:]+:([^@]+)@", rag.get("DATABASE_URL"))
    if db_pw and rag.get("POSTGRES_PASSWORD") and db_pw.group(1) != rag.get("POSTGRES_PASSWORD"):
        rec("FAIL", "match", "RAG DATABASE_URL password differs from POSTGRES_PASSWORD")
    elif db_pw:
        rec("PASS", "match", "RAG DATABASE_URL password == POSTGRES_PASSWORD")

    # ----------------------------------------------------------- frontend
    fe.require("RAG_API_URL", url=True)
    fe.require("AUTH_GATEWAY_URL", url=True)
    if fe.get("RAG_API_URL") and rag.get("PORT") is not None:
        rec("PASS", fe.name, f"RAG_API_URL port {url_port(fe.get('RAG_API_URL'))} (compose publishes the API on 8088)")

    # ---------------------------------------------------------------- IAM
    compose_text = ""
    cf = infra / "stacks" / "core" / "docker-compose.local.build.yml"
    if cf.exists():
        compose_text = cf.read_text(encoding="utf-8", errors="replace")

    def iam_value(key: str) -> str:
        return iam.get(key)

    for k, mn in (("COOKIE_SECRET", 16), ("SSO_SECRET", 16), ("JWT_REFRESH_SECRET", 32), ("JWT_MAGIC_LINK_SECRET", 16)):
        iam.require(k, min_len=mn, secret=True)
    for k in ("FRONTEND_URL", "AUTH_PUBLIC_BASE_URL"):
        iam.require(k, url=True)
    iam.require("DATABASE_URL", url=True)
    iam.require("BACKUP_CODE_ENCRYPTION_KEY", hexlen=64, secret=True)
    if not (iam.get("JWT_PRIVATE_KEY") or iam.get("JWT_PRIVATE_KEY_PATH")) or not (iam.get("JWT_PUBLIC_KEY") or iam.get("JWT_PUBLIC_KEY_PATH")):
        rec("FAIL", iam.name, "RS256 key pair missing (JWT_PRIVATE_KEY/JWT_PUBLIC_KEY or their _PATH variants)")
    else:
        rec("PASS", iam.name, "RS256 key pair configured")
    # IAM's seed falls back to built-in dev credentials when these are unset
    # (prisma/seed.ts). Fine locally - MUST be set explicitly in production.
    unset = [k for k in ("BOOTSTRAP_SUPER_ADMIN_EMAIL", "BOOTSTRAP_SUPER_ADMIN_PASSWORD", "BOOTSTRAP_SERVICE_ACCOUNT_EMAIL", "BOOTSTRAP_SERVICE_ACCOUNT_PASSWORD") if not iam.get(k)]
    if unset:
        rec("WARN", iam.name, f"{', '.join(unset)} not set - IAM seeds built-in dev defaults (OK locally, set them in production)")
    else:
        rec("PASS", iam.name, "bootstrap admin / service account credentials set")
    eff = Env("IAM(effective bootstrap)")
    eff.values["SA_EMAIL"] = iam.get("BOOTSTRAP_SERVICE_ACCOUNT_EMAIL") or "service-account@example.com"
    eff.values["SUPER_EMAIL"] = iam.get("BOOTSTRAP_SUPER_ADMIN_EMAIL") or "super-admin@example.com"
    eff.values["SUPER_PW"] = iam.get("BOOTSTRAP_SUPER_ADMIN_PASSWORD") or "ChangeMe@Local123!"
    eff.values["SA_PW"] = iam.get("BOOTSTRAP_SERVICE_ACCOUNT_PASSWORD") or eff.values["SUPER_PW"]
    iam.require("IAM_INTROSPECTION_API_KEY", secret=True)

    cors = [o.strip().rstrip("/") for o in iam.get("CORS_ORIGINS").split(",") if o.strip()]
    if not cors:
        rec("FAIL", iam.name, "CORS_ORIGINS is empty (production boot fails; also the trusted-origin list for social login)")
    else:
        for need, label in ((fe.get("AUTH_GATEWAY_URL"), "gateway origin (social login trust)"), (iam.get("FRONTEND_URL"), "frontend origin")):
            o = urlparse(need)
            origin = f"{o.scheme}://{o.netloc}" if o.netloc else ""
            if origin and origin not in cors:
                rec("FAIL", iam.name, f"CORS_ORIGINS does not include the {label}: {origin}")
            elif origin:
                rec("PASS", iam.name, f"CORS_ORIGINS includes the {label}")

    for k in ("NOTIFICATION_SERVICE_URL", "FILE_UPLOAD_SERVICE_URL", "NOTIFICATION_SERVICE_API_KEY"):
        if iam.get(k):
            rec("PASS", iam.name, f"{k} set in env files")
        elif k in compose_text:
            rec("PASS", iam.name, f"{k} injected by the core compose file")
        else:
            rec("FAIL", iam.name, f"{k} is not set in env files or the compose file (IAM will not boot)" if k.endswith("URL") else f"{k} not found")

    same(rag, "IAM_INTROSPECTION_API_KEY", iam, "IAM_INTROSPECTION_API_KEY", "RAG must send IAM's key")

    # ------------------------------------------------------------ gateway
    gw.require("FRONTEND_URL", url=True)
    gw.require("AUTH_SERVICE_URL", url=True)
    gw.require("REDIS_URL", url=True)
    gcors = gw.get("CORS_ORIGINS")
    fo = urlparse(iam.get("FRONTEND_URL") or "http://localhost:3000")
    if gcors and f"{fo.scheme}://{fo.netloc}" not in [c.strip().rstrip("/") for c in gcors.split(",")]:
        rec("FAIL", gw.name, "gateway CORS_ORIGINS does not include the frontend origin")
    elif gcors:
        rec("PASS", gw.name, "gateway CORS_ORIGINS includes the frontend origin")
    else:
        rec("FAIL", gw.name, "gateway CORS_ORIGINS is empty")
    gwe, gwp = gw.get("IAM_ADMIN_EMAIL"), gw.get("IAM_ADMIN_PASSWORD")
    pairs = {"service account": (eff.get("SA_EMAIL"), eff.get("SA_PW")), "super admin": (eff.get("SUPER_EMAIL"), eff.get("SUPER_PW"))}
    if not gwe or not gwp:
        rec("FAIL", "match", "gateway IAM_ADMIN_EMAIL / IAM_ADMIN_PASSWORD not set")
    else:
        hit = [n for n, (e, pw) in pairs.items() if e == gwe and pw == gwp]
        if hit:
            rec("PASS", "match", f"gateway IAM_ADMIN_* == IAM {hit[0]} credentials")
        else:
            rec("FAIL", "match", "gateway IAM_ADMIN_EMAIL/PASSWORD match neither IAM's service account nor its super admin (gateway cannot log in to IAM)")
    for k in ("COMMUNICATION_URL", "PAYMENT_SERVICE_URL", "DASHBOARD_URL"):
        if gw.get(k):
            rec("PASS", gw.name, f"{k} set (product URL required to boot; the service need not run)")
        else:
            rec("FAIL", gw.name, f"{k} is not set - the gateway refuses to boot without it (a placeholder URL is fine)")
    fus = gw.get("FILE_UPLOAD_SERVICE_URL")
    if not fus:
        rec("WARN", gw.name, "FILE_UPLOAD_SERVICE_URL unset: the gateway falls back to a HOSTED Render URL - set http://file-upload-service:3000")
    elif "onrender.com" in fus or "vercel.app" in fus:
        rec("FAIL", gw.name, "FILE_UPLOAD_SERVICE_URL points at a hosted service, not the local one")
    nsu = gw.get("NOTIFICATION_SERVICE_URL")
    if nsu and ("vercel.app" in nsu or "onrender.com" in nsu):
        rec("FAIL", gw.name, "NOTIFICATION_SERVICE_URL points at a hosted service (would send real email)")

    # -------------------------------------------------------- notification
    notif.require("API_KEY", secret=True)
    notif.require("MONGODB_URI", secret=True)
    notif.require("REDIS_URL", url=True)
    notif.require("EMAIL_HOST")
    notif.require("EMAIL_PORT")
    if notif.get("EMAIL_HOST") not in ("mailpit", "localhost", "127.0.0.1", "host.docker.internal") and not notif.get("EMAIL_USER"):
        rec("WARN", notif.name, "EMAIL_HOST is a real SMTP server but EMAIL_USER is empty")
    else:
        rec("PASS", notif.name, f"SMTP target: {notif.get('EMAIL_HOST')}:{notif.get('EMAIL_PORT')}")
    iam_nkey_env = Env("IAM(NOTIFICATION key)", core / ".env.shared", core / ".env.auth", core / ".env.gateway")
    if iam_nkey_env.get("NOTIFICATION_SERVICE_API_KEY"):
        same(notif, "API_KEY", iam_nkey_env, "NOTIFICATION_SERVICE_API_KEY", "callers must send notification's API_KEY")
    else:
        rec("WARN", "match", "NOTIFICATION_SERVICE_API_KEY is not in the core env files (maybe compose-injected); confirm it equals notification API_KEY")

    # --------------------------------------------------------- file-upload
    upl.require("MONGO_URI", secret=True)
    upl.require("GATEWAY_INTERNAL_SECRET", min_len=32, secret=True)
    st = upl.get("STORAGE_TYPE") or "local"
    rec("PASS", upl.name, f"STORAGE_TYPE={st}")
    if st == "local":
        upl.require("LOCAL_SIGNED_URL_SECRET", min_len=32, secret=True)
    exts = upl.get("ALLOWED_FILE_EXTENSIONS")
    if exts:
        missing = [e for e in (".pdf", ".docx", ".txt", ".md", ".csv") if e not in exts]
        rec("WARN" if missing else "PASS", upl.name, f"ALLOWED_FILE_EXTENSIONS missing: {', '.join(missing)}" if missing else "ALLOWED_FILE_EXTENSIONS covers pdf, docx, txt, md, csv")
    hm = upl.get("FILE_UPLOAD_HMAC_SECRET") or upl.get("GATEWAY_INTERNAL_SECRET")
    tmp = Env("file-upload(effective)")
    tmp.values["S"] = hm
    same(rag, "FILE_UPLOAD_HMAC_SECRET", tmp, "S", "RAG signs uploads with the upload service's secret")
    if upl.get("FILE_UPLOAD_HMAC_SECRET") and upl.get("GATEWAY_INTERNAL_SECRET") and upl.get("FILE_UPLOAD_HMAC_SECRET") != upl.get("GATEWAY_INTERNAL_SECRET"):
        rec("WARN", upl.name, "FILE_UPLOAD_HMAC_SECRET differs from GATEWAY_INTERNAL_SECRET (the service prefers GATEWAY_INTERNAL_SECRET)")

    # ------------------------------------------------------ mongo reachable
    for env, key in ((notif, "MONGODB_URI"), (upl, "MONGO_URI")):
        uri = env.get(key)
        if uri and not is_placeholder(uri):
            r = reachable(uri)
            if r is True:
                rec("PASS", env.name, f"{key} host is reachable from this machine")
            elif r is False:
                rec("FAIL", env.name, f"{key} host is NOT reachable from this machine (is MongoDB running?)")
            else:
                rec("WARN", env.name, f"{key} is a mongodb+srv URI - reachability not probed")

    # ------------------------------------------------ provider values (todo)
    if "--providers" in sys.argv:
        prov_keys = [
            (rag, ["GOOGLE_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GROQ_API_KEY", "OPENWEATHER_API_KEY", "NEWSAPI_API_KEY", "SERPER_API_KEY", "TAVILY_API_KEY", "LANGCHAIN_API_KEY"]),
            (iam, ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "MICROSOFT_CLIENT_ID", "MICROSOFT_CLIENT_SECRET", "MICROSOFT_TENANT_ID", "FACEBOOK_APP_ID", "FACEBOOK_APP_SECRET", "TURNSTILE_SECRET_KEY"]),
            (notif, ["MONGODB_URI", "EMAIL_USER", "EMAIL_PASS"]),
            (upl, ["MONGO_URI", "R2_ENDPOINT", "R2_ACCESS_KEY", "R2_SECRET", "R2_BUCKET", "AZURE_CONNECTION_STRING", "AZURE_CONTAINER"]),
        ]
        print("Provider values (state only - validity cannot be checked):")
        for env, keys in prov_keys:
            print()
            print(f"  {env.name}")
            for k in keys:
                v = env.get(k)
                s = "MISSING" if k not in env.values else ("empty" if not v else ("placeholder" if is_placeholder(v) else "set"))
                print(f"    {k:28s} {s}")
        print()

    # --------------------------------------------------------------- report
    order = {"FAIL": 0, "WARN": 1, "PASS": 2}
    show_pass = "--all" in sys.argv
    counts = {"FAIL": 0, "WARN": 0, "PASS": 0}
    for lvl, area, msg in sorted(results, key=lambda r: (order[r[0]], r[1])):
        counts[lvl] += 1
        if lvl != "PASS" or show_pass:
            print(f"{lvl:4}  [{area}] {msg}")
    print(f"\n{counts['FAIL']} FAIL, {counts['WARN']} WARN, {counts['PASS']} PASS" + ("" if show_pass else "  (use --all to list PASS lines)"))
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
