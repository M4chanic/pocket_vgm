#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Апдейтер m4pocket в духе pupdate: лежит в КОРНЕ SD-карты как файл
`m4pocket-update` (без расширения) — на macOS двойной клик открывает его
в Терминале; либо вручную: python3 m4pocket-update. Скачивает последний
релиз M4chanic/pocket_vgm и распаковывает его поверх карты (Cores/,
Assets/, Platforms/). Ваша музыка в Assets/riscv/common не удаляется (файлы релиза
перезаписываются, чужие не трогаются).

Репозиторий публичный — токен НЕ нужен. Если задан (переменная GH_TOKEN/
GITHUB_TOKEN или файл m4pocket_token.txt рядом), используется — полезно
против rate-limit GitHub API.

Ключи: --force — переустановить даже если версия совпадает;
       --tag vX.Y.Z — конкретный релиз вместо последнего.
"""

import argparse
import io
import json
import os
import ssl
import sys
import urllib.error
import urllib.request
import zipfile

REPO = "M4chanic/pocket_vgm"
API = "https://api.github.com/repos/" + REPO
ROOT = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(ROOT, "m4pocket_token.txt")
VERSION_FILE = os.path.join(ROOT, ".m4pocket_version")


class _StripAuthRedirect(urllib.request.HTTPRedirectHandler):
    """GitHub отдаёт ассеты редиректом на S3; S3 отвергает запрос, если в нём
    остался заголовок Authorization. Убираем его при редиректе."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None:
            new.remove_header("Authorization")
        return new


def _ssl_context(insecure=False):
    """CA-цепочка: certifi, если есть (фреймворковый Python на macOS без
    прогнанного Install Certificates.command не имеет системных CA)."""
    if insecure:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


_OPENER = urllib.request.build_opener(_StripAuthRedirect())


def set_opener(insecure):
    global _OPENER
    _OPENER = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=_ssl_context(insecure)),
        _StripAuthRedirect(),
    )


def http_get(url, token, accept):
    req = urllib.request.Request(url)
    req.add_header("Accept", accept)
    req.add_header("User-Agent", "m4pocket-updater")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    return _OPENER.open(req, timeout=60)


def get_token():
    """Опциональный токен (репо публичный): против rate-limit API."""
    for var in ("GH_TOKEN", "GITHUB_TOKEN"):
        if os.environ.get(var):
            return os.environ[var].strip(), "переменная " + var
    if os.path.isfile(TOKEN_FILE):
        with open(TOKEN_FILE, "r", encoding="utf-8") as f:
            tok = f.read().strip()
        if tok:
            return tok, "файл " + TOKEN_FILE
    return None, None


def whoami(token):
    """Логин владельца токена (None, если токен вовсе не валиден)."""
    try:
        with http_get("https://api.github.com/user", token,
                      "application/vnd.github+json") as r:
            return json.load(r).get("login")
    except (urllib.error.HTTPError, urllib.error.URLError, OSError):
        return None


TOKEN_HELP = """\
Репозиторий %s ПРИВАТНЫЙ: GitHub отвечает 404, если токен его не видит.
Как сделать рабочий токен (https://github.com/settings/tokens):
  * fine-grained: Generate new token -> Resource owner: владелец репо ->
    Repository access: Only select repositories -> выбрать pocket_vgm ->
    Permissions -> Contents: Read-only;
  * либо classic: Generate new token (classic) -> галочка на весь скоуп "repo".
Токен должен принадлежать аккаунту с доступом к репозиторию.""" % REPO


def pick_release(token, tag):
    url = API + ("/releases/tags/" + tag if tag else "/releases/latest")
    with http_get(url, token, "application/vnd.github+json") as r:
        rel = json.load(r)
    assets = [a for a in rel.get("assets", []) if a["name"].endswith(".zip")]
    if not assets:
        raise SystemExit("В релизе %s нет zip-ассета" % rel.get("tag_name"))
    return rel["tag_name"], assets[0]


def installed_version():
    try:
        with open(VERSION_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return None


def download(asset, token):
    print("Качаю %s (%.1f МБ)..." % (asset["name"], asset["size"] / 1e6))
    # url ассета через API + Accept: octet-stream работает и для приватных репо
    with http_get(asset["url"], token, "application/octet-stream") as r:
        return r.read()


def extract(data):
    n = 0
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for m in z.infolist():
            name = m.filename
            if name.startswith("/") or ".." in name.replace("\\", "/").split("/"):
                raise SystemExit("Подозрительный путь в архиве: " + name)
            z.extract(m, ROOT)
            if not name.endswith("/"):
                n += 1
    return n


def migrate_old_core():
    """Перенос со старого имени ядра agg23.RISCV/riscv -> M4chanic.PocketVGM/pocketvgm."""
    old_core = os.path.join(ROOT, "Cores", "agg23.RISCV")
    old_assets = os.path.join(ROOT, "Assets", "riscv", "common")
    if not os.path.isdir(old_core) and not os.path.isdir(old_assets):
        return
    print("Найдено старое ядро agg23.RISCV (до переименования в M4chanic.PocketVGM).")
    ans = input("Перенести музыку в Assets/pocketvgm/common и удалить старое ядро? [y/N]: ")
    if not ans.strip().lower().startswith("y"):
        print("Оставил как есть; музыку можно перенести вручную.")
        return
    import shutil
    new_assets = os.path.join(ROOT, "Assets", "pocketvgm", "common")
    os.makedirs(new_assets, exist_ok=True)
    if os.path.isdir(old_assets):
        for name in os.listdir(old_assets):
            src = os.path.join(old_assets, name)
            dst = os.path.join(new_assets, name)
            if name == "boot.bin" or os.path.exists(dst):
                continue
            shutil.move(src, dst)
        shutil.rmtree(os.path.join(ROOT, "Assets", "riscv"), ignore_errors=True)
    shutil.rmtree(old_core, ignore_errors=True)
    for p in (os.path.join(ROOT, "Platforms", "riscv.json"),
              os.path.join(ROOT, "Platforms", "_images", "riscv.bin")):
        try:
            os.remove(p)
        except OSError:
            pass
    print("Миграция готова: музыка в Assets/pocketvgm/common, старое ядро удалено.")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description="Обновление ядра m4pocket на SD-карте")
    ap.add_argument("--force", action="store_true", help="ставить даже без новой версии")
    ap.add_argument("--tag", help="конкретный релиз (vX.Y.Z) вместо последнего")
    ap.add_argument("--insecure", action="store_true",
                    help="не проверять TLS-сертификаты (когда на маке не настроены CA)")
    args = ap.parse_args()
    set_opener(args.insecure)

    token, source = get_token()
    if token:
        print("Токен: %s...%s (%s)" % (token[:8], token[-4:], source))

    try:
        tag, asset = pick_release(token, args.tag)
    except urllib.error.URLError as e:
        if "CERTIFICATE_VERIFY_FAILED" in str(e):
            raise SystemExit(
                "TLS-сертификаты Python не настроены (типично для python.org-сборки "
                "на macOS).\nВарианты:\n"
                "  1) запустить: /Applications/Python*/Install Certificates.command\n"
                "  2) pip3 install certifi\n"
                "  3) повторить с флагом --insecure (без проверки сертификатов)")
        raise
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise SystemExit("GitHub ответил 401: токен невалиден (опечатка, отозван "
                             "или истёк).\n" + TOKEN_HELP)
        if e.code == 403:
            raise SystemExit("GitHub ответил 403 — вероятно, rate-limit API.\n"
                             "Подождите немного или положите GitHub-токен в "
                             "m4pocket_token.txt (любой, без особых прав).")
        if e.code == 404:
            raise SystemExit("GitHub ответил 404 — релиз/репозиторий не найден.")
        raise

    cur = installed_version()
    print("Установлено: %s, доступно: %s" % (cur or "ничего", tag))
    if cur == tag and not args.force:
        print("Уже актуально. Для переустановки: --force")
        return

    n = extract(download(asset, token))
    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        f.write(tag + "\n")
    migrate_old_core()
    print("Готово: %s, файлов распаковано: %d, карта: %s" % (tag, n, ROOT))
    print("Вставьте SD в Pocket — ядро M4chanic.PocketVGM, музыка в Assets/pocketvgm/common.")


if __name__ == "__main__":
    main()
