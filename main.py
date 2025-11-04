# main

import flet as ft
import os
from pages.login import login_view
from pages.jogo import jogo_view
from pages.ajuda import ajuda_view
from pages.placar import placar_view

def main(page: ft.Page):
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


# Roda como servidor web no Render
ft.app(
    target=main,
    view=None,
    port=int(os.environ.get("PORT", 8000)),
    assets_dir="assets",
    route_url_strategy="path"
)

# ft.app(target=main, assets_dir="assets", route_url_strategy="path", view=ft.WEB_BROWSER)
