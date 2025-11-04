import flet as ft
from anim_manager import AnimationManager

def encerrar_view_atual(page: ft.Page, anim_manager: AnimationManager):
    # Cancelar qualquer animação em andamento
    anim_manager.stop_animation()

    # Remover overlays como áudio ou alertas
    page.overlay.clear()

    # Limpar a view atual, caso esteja usando page.views
    if hasattr(page, "views") and page.views:
        page.views.clear()

    # Atualizar visual
    page.update()
