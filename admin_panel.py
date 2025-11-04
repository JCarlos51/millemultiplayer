import flet as ft
import firebase_admin
from firebase_admin import credentials, firestore

# Inicializa Firebase Admin SDK
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

COLLECTION = "salas"

def main(page: ft.Page):
    page.title = "Painel Admin - Mille Multiplayer"
    page.scroll = True

    lista_salas = ft.Column()
    status = ft.Text()
    refresh_button = ft.ElevatedButton("🔄 Atualizar Salas")

    def format_valor(valor, nivel=0):
        """Formata recursivamente o conteúdo de dicionários/listas"""
        prefixo = "  " * nivel
        if isinstance(valor, dict):
            linhas = []
            for k, v in valor.items():
                linhas.append(f"{prefixo}- {k}:")
                linhas.append(format_valor(v, nivel + 1))
            return "\n".join(linhas)
        elif isinstance(valor, list):
            if not valor:
                return f"{prefixo}[]"
            return "\n".join([format_valor(item, nivel + 1) for item in valor])
        else:
            return f"{prefixo}{valor}"

    def listar_salas(e):
        lista_salas.controls.clear()
        docs = db.collection(COLLECTION).stream()

        for doc in docs:
            data = doc.to_dict()
            sala_id = doc.id
            turno = data.get("turn", "-")
            vencedor = data.get("vencedor", None)
            status_sala = data.get("status", "-")
            deck = data.get("deck", [])

            linha_info = [
                ft.Text(f"🆔 Sala: {sala_id} | Status: {status_sala} | Turno: {turno} | Deck: {len(deck)} cartas", weight="bold")
            ]

            for label in ["player1", "player2"]:
                if label in data:
                    p = data[label]
                    linha_info.append(ft.Text(
                        f"{label.upper()} - {p.get('nome', '')} | "
                        f"Distância: {p.get('distance', 0)} km | "
                        f"Status: {p.get('status', '')} | "
                        f"Limite: {'Sim' if p.get('limite', False) else 'Não'} | "
                        f"Última Carta: {p.get('last_card_played', '')} | "
                        f"Seguranças: {', '.join(p.get('safeties', [])) or 'Nenhuma'}"
                    ))

            if vencedor:
                linha_info.append(ft.Text(f"🏁 Vencedor: {vencedor}", color=ft.Colors.GREEN_900, weight="bold"))

            # Exibir dados completos formatados
            linha_info.append(ft.Text("📋 Dados completos da sala:", weight="w600"))
            linha_info.append(
                ft.Text(format_valor(data), size=12, selectable=True, font_family="Courier New")
            )

            delete_btn = ft.IconButton(
                icon=ft.Icons.DELETE,
                tooltip=f"Excluir sala {sala_id}",
                on_click=lambda e, sala=sala_id: excluir_sala(sala)
            )

            lista_salas.controls.append(ft.Card(
                content=ft.Container(
                    content=ft.Column(linha_info + [delete_btn]),
                    padding=10,
                    bgcolor=ft.Colors.BLUE_GREY_50,
                    border_radius=6
                )
            ))

        page.update()

    def excluir_sala(room_id):
        db.collection(COLLECTION).document(room_id).delete()
        status.value = f"✅ Sala '{room_id}' excluída."
        listar_salas(None)

    refresh_button.on_click = listar_salas

    page.add(
        ft.Text("🎮 Painel de Administração do Mille Bornes", size=22, weight="bold"),
        refresh_button,
        lista_salas,
        ft.Divider(),
        status
    )

    listar_salas(None)

ft.app(target=main)
