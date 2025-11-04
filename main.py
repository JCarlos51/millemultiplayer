# main.py

import flet as ft
import os
from pages.login import login_view
from pages.jogo import jogo_view
from pages.ajuda import ajuda_view
from pages.placar import placar_view


def main(page: ft.Page):
    page.title = "MilleBornes Multiplayer"
    page.favicon = "/assets/favicon.png"

    def route_change(e):
        page.views.clear()
        if page.route == "/":
            page.views.append(login_view(page))
        elif page.route == "/jogo":
            jogo = jogo_view(page)
            page.views.append(jogo)
            page.update()
        elif page.route == "/placar":
            page.views.append(placar_view(page))
        elif page.route == "/ajuda":
            page.views.append(ajuda_view(page))
            page.update()
        else:
            page.go("/")

        page.update()

    page.on_route_change = route_change
    page.go(page.route or "/")

# -------------------------------------------------------
# Execução automática conforme ambiente (Render x local)
# -------------------------------------------------------

if os.environ.get("RENDER") or os.environ.get("PORT"):
    # Modo Render (deploy online)
    ft.app(
        target=main,
        view=None,
        port=int(os.environ.get("PORT", 8000)),
        assets_dir="assets",
        route_url_strategy="path",
    )
else:
    # Modo local (abre no navegador automaticamente)
    ft.app(
        target=main,
        view=ft.WEB_BROWSER,
        assets_dir="assets",
        route_url_strategy="path",
    )
