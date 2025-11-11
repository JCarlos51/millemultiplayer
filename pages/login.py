import flet as ft
import unicodedata
import uuid
import math
from datetime import datetime, timezone, timedelta
import os
import json
from firebase_admin import credentials, firestore, initialize_app, _apps
from difflib import SequenceMatcher

# 🔥 Inicializa o Firebase apenas uma vez
if not _apps:
    firebase_key_json = os.getenv("FIREBASE_KEY")

    if firebase_key_json:
        cred_info = json.loads(firebase_key_json)
        cred = credentials.Certificate(cred_info)
    else:
        cred = credentials.Certificate("serviceAccountKey.json")

    initialize_app(cred)

# Cria o cliente Firestore
db = firestore.client()


def normalizar_nome(nome: str) -> str:
    """Remove acentos e normaliza o nome para comparação segura."""
    if not nome:
        return ""
    nome = nome.strip().casefold()
    return ''.join(
        c for c in unicodedata.normalize('NFD', nome)
        if unicodedata.category(c) != 'Mn'
    )


def limpar_salas_antigas():
    """Remove salas com mais de 1 dia de existência para evitar acúmulo."""
    limite = datetime.now(timezone.utc) - timedelta(days=1)
    salas_ref = db.collection("salas")
    docs = salas_ref.stream()
    count = 0

    for doc in docs:
        data = doc.to_dict() or {}
        created_at = data.get("created_at")
        if created_at and created_at < limite:
            salas_ref.document(doc.id).delete()
            count += 1
            print(f"🗑️ Sala {doc.id} removida (criada em {created_at})")

    if count > 0:
        print(f"✅ {count} sala(s) antigas removidas.")


# ----------------------------------------------
# 🔹 Tela de login e criação automática de sala
# ----------------------------------------------
def login_view(page: ft.Page):
    page.title = "Mille Bornes"
    page.fonts = {"Lobster": "/fonts/Lobster.ttf"}
    page.padding = 0
    page.scroll = ft.ScrollMode.AUTO
    page.window.center()

    limpar_salas_antigas()

    # ------------------------------
    # Função principal (envio)
    # ------------------------------

    def similar(a, b):
        """Retorna o grau de similaridade (0 a 1) entre duas strings normalizadas."""
        return SequenceMatcher(None, a, b).ratio()

    def enviar_click(e):
        nome_jogador = name_player.value.strip()
        nome_oponente = oponente_esperado.value.strip()
        meu_id = str(uuid.uuid4())

        if not nome_jogador or not nome_oponente:
            page.snack_bar = ft.SnackBar(ft.Text("Preencha todos os campos!"), open=True)
            page.update()
            return

        jogador_cf = normalizar_nome(nome_jogador)
        oponente_cf = normalizar_nome(nome_oponente)

        try:
            # 🔍 Busca salas com status "waiting"
            salas_query = (
                db.collection("salas")
                .where("game_status", "==", "waiting")
                .stream()
            )

            sala_encontrada = None
            melhor_similaridade = 0.0
            sala_id_match = None

            for sala in salas_query:
                data = sala.to_dict() or {}
                p1_nome_cf = data.get("player1_nome_cf", "")
                oponente_esperado_cf = data.get("oponente_esperado", "")

                sim_p1 = similar(p1_nome_cf, oponente_cf)
                sim_oponente = similar(oponente_esperado_cf, jogador_cf)
                media_sim = (sim_p1 + sim_oponente) / 2

                print(f"🔍 Verificando sala {sala.id}: "
                      f"p1_nome={p1_nome_cf}, oponente_esperado={oponente_esperado_cf}, "
                      f"sim_p1={sim_p1:.2f}, sim_oponente={sim_oponente:.2f}, média={media_sim:.2f}")

                if sim_p1 >= 0.9 and sim_oponente >= 0.9:
                    sala_encontrada = sala
                    melhor_similaridade = media_sim
                    sala_id_match = sala.id
                    print(f"✅ Sala compatível encontrada: {sala_id_match} (similaridade média {media_sim:.2f})")
                    break

            if sala_encontrada:
                # 🎮 Jogador2 entra na sala encontrada
                sala_id = sala_encontrada.id
                sala_ref = db.collection("salas").document(sala_id)
                sala_data = sala_encontrada.to_dict()
                player1_nome = sala_data.get("player1", {}).get("nome", "")

                sala_ref.update({
                    "player2": {
                        "id": meu_id,
                        "nome": nome_jogador,
                        "oponente": player1_nome,
                        "hand": [],
                        "distance": 0,
                        "status": "Luz Vermelha",
                        "limite": False,
                        "last_card_played": "Nenhuma",
                        "safeties": [],
                        "com_200": "N",
                        "placar": {"total_geral": 0, "atual_mao": {}},
                    },
                    "player1.oponente": nome_jogador,
                    "game_status": "ready",
                })

                print(f"🎮 Jogador2 '{nome_jogador}' entrou na sala '{sala_id}' (encontrada automaticamente)")
                meu_caminho = "player2"

            else:
                # 🧩 Nenhuma sala compatível → Jogador1 cria nova
                sala_id = f"{jogador_cf}_{oponente_cf}"
                sala_ref = db.collection("salas").document(sala_id)

                sala_ref.set({
                    "player1": {
                        "id": meu_id,
                        "nome": nome_jogador,
                        "oponente": nome_oponente,
                        "hand": [],
                        "distance": 0,
                        "status": "Luz Vermelha",
                        "limite": False,
                        "last_card_played": "Nenhuma",
                        "safeties": [],
                        "com_200": "N",
                        "placar": {"total_geral": 0, "atual_mao": {}},
                    },
                    "player2": {
                        "id": "",
                        "nome": "",
                        "oponente": "",
                        "hand": [],
                        "distance": 0,
                        "status": "Luz Vermelha",
                        "limite": False,
                        "last_card_played": "Nenhuma",
                        "safeties": [],
                        "com_200": "N",
                        "placar": {"total_geral": 0, "atual_mao": {}},
                    },
                    "turn": "player1",
                    "game_status": "waiting",
                    "player1_nome_cf": jogador_cf,
                    "oponente_esperado": oponente_cf,
                    "created_at": datetime.now(timezone.utc),
                })

                print(f"🆕 Sala criada: {sala_id} aguardando '{nome_oponente}'")
                meu_caminho = "player1"

            # 💾 Armazena localmente e entra no jogo
            page.client_storage.set("nome_jogador", nome_jogador)
            page.client_storage.set("sala_jogador", sala_id)
            page.client_storage.set("nome_oponente", nome_oponente)
            page.client_storage.set("meu_caminho", meu_caminho)
            page.client_storage.set("jogador_id", meu_id)

            page.go("/jogo")

        except Exception as err:
            import traceback
            traceback.print_exc()
            page.snack_bar = ft.SnackBar(ft.Text(f"Erro: {err}"), open=True)
            page.update()

    # ------------------------------
    # Campos da tela
    # ------------------------------
    def update_button_state(e):
        button.disabled = (
            len(name_player.value.strip()) == 0 or
            len(oponente_esperado.value.strip()) == 0
        )
        page.update()

    name_player = ft.TextField(
        label="Seu nome",
        bgcolor="white",
        border_color="#d40000",
        border_radius=5,
        height=35,
        width=180,
        on_change=update_button_state
    )

    oponente_esperado = ft.TextField(
        label="Nome do oponente",
        bgcolor="white",
        border_color="#d40000",
        border_radius=5,
        height=35,
        width=180,
        on_change=update_button_state
    )

    button = ft.ElevatedButton(
        text="Entrar / Criar Sala",
        disabled=True,
        on_click=enviar_click,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=ft.border_radius.all(10)),
            color={"": "white"},
            bgcolor={"": "#d40000"},
        )
    )

    login_card = ft.Container(
        content=ft.Column(
            controls=[
                ft.Text("Entrar no jogo", size=18, weight=ft.FontWeight.BOLD, color="white"),
                ft.Row(
                    controls=[
                        ft.Container(content=name_player, expand=True),
                        ft.Container(content=oponente_esperado, expand=True),
                        ft.Container(content=button),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                ),
                ft.Text(
                    "Digite seu nome e o do seu oponente. "
                    "Se o oponente ainda não entrou, a sala será criada automaticamente.",
                    size=12,
                    color="white",
                    text_align=ft.TextAlign.CENTER
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10
        ),
        padding=15,
        bgcolor="#d40000",
        border_radius=20,
        width=500,
        alignment=ft.alignment.center
    )

    # ------------------------------
    # Layout visual
    # ------------------------------
    navbar = ft.Container(
        content=ft.ResponsiveRow(
            controls=[
                ft.Container(content=ft.Image(src="icons/JC.png", width=50),
                             col={"xs": 2, "sm": 1, "md": 1},
                             alignment=ft.alignment.center_left),
                ft.Container(content=ft.Text("Mille Bornes", size=38,
                                             font_family="Lobster",
                                             color="#180F4A",
                                             text_align=ft.TextAlign.CENTER),
                             col={"xs": 7, "sm": 9, "md": 10},
                             expand=True, alignment=ft.alignment.center),
                ft.Container(content=ft.TextButton(text="Ajuda",
                                                   on_click=lambda _: page.go("/ajuda"),
                                                   style=ft.ButtonStyle(
                                                       text_style=ft.TextStyle(weight=ft.FontWeight.BOLD, size=16))),
                             col={"xs": 3, "sm": 2, "md": 1},
                             alignment=ft.alignment.center_right),
            ],
            spacing=0,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER
        ),
        padding=ft.padding.only(left=20, right=20, top=20, bottom=20),
        bgcolor="white",
        shadow=ft.BoxShadow(blur_radius=5, color="#ccc"),
    )

    headline_col = ft.Column(
        controls=[
            ft.Text("J  o  g  o     d  e     c  a  r  t  a  s", size=16,
                    weight=ft.FontWeight.W_800, color="#180F4A",
                    text_align=ft.TextAlign.CENTER),
            ft.Text("Mille Bornes", size=50, weight=ft.FontWeight.BOLD,
                    color="#180F4A", text_align=ft.TextAlign.CENTER),
            ft.Text(
                "O objetivo do jogo é ser o primeiro a alcançar 5.000 pontos "
                "em várias mãos, completando viagens de exatamente 700 KM ou 1.000 KM.",
                color=ft.Colors.BLACK,
                text_align=ft.TextAlign.CENTER
            ),
            ft.Container(height=30),
            login_card,
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=20
    )

    img_headline = ft.Image(src="images/carro.png", width=300, height=200, fit=ft.ImageFit.CONTAIN)

    header = ft.ResponsiveRow(
        controls=[
            ft.Container(content=headline_col, col={"xs": 12, "md": 6}),
            ft.Container(content=img_headline, col={"xs": 12, "md": 6}, alignment=ft.alignment.center)
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        run_spacing=20
    )

    footer = ft.Container(
        content=ft.Column(controls=[
            ft.Text("Mille Bornes", size=16, weight=ft.FontWeight.W_400,
                    color=ft.Colors.WHITE, font_family='Lobster',
                    text_align=ft.TextAlign.CENTER),
            ft.Text("© Todos os direitos reservados.", color="white", size=12,
                    text_align=ft.TextAlign.CENTER)
        ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=2),
        bgcolor="#004C99",
        padding=ft.padding.symmetric(vertical=10),
        border_radius=10,
        margin=ft.margin.only(top=30),
        border=ft.border.all(width=2, color=ft.Colors.RED),
        alignment=ft.alignment.center
    )

    whatsapp_icon = ft.Container(
        content=ft.Image(src="images/whats.png", width=60),
        on_click=lambda _: page.launch_url("https://api.whatsapp.com/send?phone=5511998929788"),
        bottom=5, right=5,
    )

    return ft.View(
        route="/",
        controls=[
            ft.Stack(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Container(content=navbar),
                            ft.Container(content=header),
                            ft.Container(content=footer),
                        ],
                        expand=True,
                        spacing=15,
                    ),
                    whatsapp_icon
                ],
                expand=True,
            )
        ],
        scroll=ft.ScrollMode.AUTO
    )
