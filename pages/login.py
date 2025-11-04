import flet as ft
import unicodedata
import uuid
import math
from datetime import datetime, timezone, timedelta
from firebase_admin import credentials, firestore, initialize_app, _apps

# 🔥 Inicializa Firebase apenas uma vez
cred = credentials.Certificate("serviceAccountKey.json")
if not _apps:
    initialize_app(cred)
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


def obter_primeira_sala_disponivel():
    """
    Sugere a primeira sala livre (000–999) apenas se não houver nenhuma aguardando o segundo jogador.
    Igual ao comportamento do Supabase.
    """
    salas_ref = db.collection("salas")
    docs = list(salas_ref.stream())

    if not docs:
        return "000"

    salas_existentes = {doc.id for doc in docs}

    # 🚦 Verifica se há sala aguardando (sem player2)
    for doc in docs:
        data = doc.to_dict() or {}
        player2 = (data.get("player2") or {}).get("nome", "")
        status = data.get("game_status", "")
        if not player2 or status == "waiting":
            # print(f"💬 Sala {doc.id} está aguardando jogador (status={status})")
            return ""

    # 🧩 Se nenhuma sala está aguardando, retorna a primeira numérica livre
    for i in range(1000):
        codigo = f"{i:03d}"
        if codigo not in salas_existentes:
            return codigo

    return ""


def login_view(page: ft.Page):
    page.title = "Mille Bornes"
    page.fonts = {"Lobster": "/fonts/Lobster.ttf"}
    page.padding = 0
    page.scroll = ft.ScrollMode.AUTO
    page.window.center()

    # 🧹 Limpa salas antigas antes de sugerir nova
    limpar_salas_antigas()

    # ------------------------------
    # Funções auxiliares de UI
    # ------------------------------
    def somente_numeros(e):
        e.control.value = ''.join(filter(str.isdigit, e.control.value))[:3]
        update_button_state(e)

    def update_button_state(e):
        button.disabled = (
            len(name_player.value.strip()) == 0 or
            len(oponente_esperado.value.strip()) == 0 or
            len(room_number.value.strip()) != 3
        )
        page.update()

    # ------------------------------
    # Lógica principal de envio
    # ------------------------------
    def enviar_click(e):
        nome_jogador = name_player.value.strip()
        nome_oponente = oponente_esperado.value.strip()
        sala_id = room_number.value.strip().zfill(3)
        meu_id = str(uuid.uuid4())

        if not nome_jogador or not nome_oponente or not sala_id:
            page.snack_bar = ft.SnackBar(ft.Text("Preencha todos os campos!"), open=True)
            page.update()
            return

        try:
            sala_ref = db.collection("salas").document(sala_id)
            doc = sala_ref.get()
            jogador_cf = normalizar_nome(nome_jogador)
            oponente_cf = normalizar_nome(nome_oponente)
            meu_caminho = None

            if not doc.exists:
                # 1️⃣ Criar nova sala (player1)
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
                    "oponente_esperado": nome_oponente.lower(),
                    "created_at": datetime.now(timezone.utc),
                })
                meu_caminho = "player1"
                # print(f"🆕 Sala criada: {sala_id} com player1 = {nome_jogador}")

            else:
                # 2️⃣ Sala já existe → entrar como player2 ou retornar como player1
                sala_data = doc.to_dict()
                p1_nome = normalizar_nome((sala_data.get("player1") or {}).get("nome", ""))
                p2_nome = normalizar_nome((sala_data.get("player2") or {}).get("nome", ""))
                esperado_bd = normalizar_nome(sala_data.get("oponente_esperado") or "")

                # print(f"DEBUG: jogador={jogador_cf}, oponente={oponente_cf}, p1={p1_nome}, p2={p2_nome}, esperado={esperado_bd}")

                if jogador_cf == p1_nome:
                    meu_caminho = "player1"

                elif (not p2_nome and jogador_cf == esperado_bd) or (jogador_cf == p2_nome):
                    meu_caminho = "player2"
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
                        "game_status": "ready"
                    })
                    # print(f"👤 Jogador 2 ({nome_jogador}) entrou na sala {sala_id}.")

                else:
                    msg = "Combinação inválida ou sala cheia."
                    # print(f"⚠️ {msg}")
                    page.snack_bar = ft.SnackBar(ft.Text(msg), open=True)
                    page.update()
                    return

            if meu_caminho:
                page.client_storage.set("nome_jogador", nome_jogador)
                page.client_storage.set("sala_jogador", sala_id)
                page.client_storage.set("nome_oponente", nome_oponente)
                page.client_storage.set("meu_caminho", meu_caminho)
                page.client_storage.set("jogador_id", meu_id)
                # print(f"✅ Entrou na sala {sala_id} como {meu_caminho} ({meu_id})")
                page.go("/jogo")

        except Exception as err:
            import traceback
            traceback.print_exc()
            page.snack_bar = ft.SnackBar(ft.Text(f"Erro: {err}"), open=True)
            page.update()

    # ⚙️ Campos
    sala_sugerida = obter_primeira_sala_disponivel()

    name_player = ft.TextField(
        label="Nome do jogador",
        bgcolor="white",
        border_color="#d40000",
        border_radius=5,
        height=35,
        width=160,
        on_change=update_button_state
    )

    oponente_esperado = ft.TextField(
        label="Nome do oponente",
        bgcolor="white",
        border_color="#d40000",
        border_radius=5,
        height=35,
        width=160,
        on_change=update_button_state
    )

    room_number = ft.TextField(
        label="Sala",
        value=sala_sugerida,
        bgcolor="white",
        border_color="#d40000",
        border_radius=5,
        height=35,
        width=80,
        max_length=3,
        keyboard_type=ft.KeyboardType.NUMBER,
        on_change=somente_numeros
    )

    button = ft.ElevatedButton(
        text="Enviar",
        disabled=True,
        on_click=enviar_click,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=ft.border_radius.all(10))
        )
    )

    # 🔹 Navbar, cabeçalho, card, footer e ícone do WhatsApp
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
            ft.Container(content=ft.Column(
                controls=[
                    ft.Text("J  o  g  o     d  e     c  a  r  t  a  s", size=16,
                            weight=ft.FontWeight.W_800, color="#180F4A",
                            text_align=ft.TextAlign.CENTER),
                    ft.Text("Mille Bornes", size=50, weight=ft.FontWeight.BOLD,
                            color="#180F4A", text_align=ft.TextAlign.CENTER),
                    ft.Text(value=("O objetivo do jogo é ser o primeiro a alcançar o total de 5.000 pontos "
                                   "em várias mãos do jogo. Para isso os jogadores tentarão completar viagens "
                                   "de exatamente 700 KM ou 1.000 KM em cada mão jogada."),
                            color=ft.Colors.BLACK, text_align=ft.TextAlign.CENTER),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                width=500, alignment=ft.alignment.center),

            ft.Container(height=30),

            ft.Container(content=ft.Column(
                controls=[
                    ft.Text("Login", size=18, weight=ft.FontWeight.BOLD),
                    ft.Row(controls=[
                        ft.Container(content=name_player, expand=True),
                        ft.Container(content=oponente_esperado, expand=True),
                        ft.Container(content=room_number, width=58),
                        ft.Container(content=button),
                    ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=15, bgcolor=ft.Colors.RED,
                border_radius=20, width=500, alignment=ft.alignment.center)
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=20
    )

    img_headline = ft.Image(src="images/carro.png", width=300, height=200, fit=ft.ImageFit.CONTAIN)

    header = ft.ResponsiveRow(
        controls=[
            ft.Container(content=headline_col, col={"xs": 12, "md": 6}),
            ft.Container(content=img_headline, col={"xs": 12, "md": 6},
                         alignment=ft.alignment.center)
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        run_spacing=20
    )

    card = ft.Container(
        content=ft.Row(controls=[
            ft.Container(content=ft.Image(
                src="images/manual-book.png", width=45,
                tooltip=ft.Tooltip(
                    message=("O baralho consiste de um jogo de 100 cartas..."),
                    border_radius=10,
                    text_style=ft.TextStyle(size=14, color=ft.Colors.WHITE),
                    gradient=ft.LinearGradient(begin=ft.alignment.top_left,
                                               end=ft.alignment.Alignment(0.8, 1),
                                               colors=["#0000FF", "#1E90FF", "#00BFFF"],
                                               tile_mode=ft.GradientTileMode.MIRROR,
                                               rotation=math.pi / 3),
                )),
                padding=8, bgcolor="white", border_radius=8,
                border=ft.border.all(width=1, color=ft.Colors.RED),
            )
        ], alignment=ft.MainAxisAlignment.START),
        margin=ft.margin.only(top=30, left=20),
        expand=True
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

    def on_mount(e):
        # 🔄 Reexecuta limpeza e sugestão de sala ao montar
        limpar_salas_antigas()
        room_number.value = obter_primeira_sala_disponivel()
        page.update()

    page.on_mount = on_mount

    return ft.View(
        route="/",
        controls=[
            ft.Stack(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Container(content=navbar),
                            ft.Container(content=header),
                            ft.Container(content=card),
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
