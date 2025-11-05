# jogo

import os
import json
import flet as ft
from uuid import uuid4
from deck import create_deck
import threading, time
import asyncio
from firebase_helpers import (
    jogar_carta, descartar_carta, corrigir_mao_jogador, distribuir_cartas,
    obter_nome_jogador, obter_sala_jogador
)
from firebase_admin import credentials, firestore, initialize_app, _apps

# 🔥 Inicializa Firebase apenas uma vez
if not _apps:
    firebase_key_json = os.getenv("FIREBASE_KEY")

    if firebase_key_json:
        # No Render: lê a chave da variável de ambiente
        cred_info = json.loads(firebase_key_json)
        cred = credentials.Certificate(cred_info)
    else:
        # Localmente: usa o arquivo físico
        cred = credentials.Certificate("serviceAccountKey.json")

    initialize_app(cred)

db = firestore.client()

COLLECTION = "salas"

def jogo_view(page: ft.Page):
    page.title = "Mille Bornes Multiplayer"
    page.scroll = ft.ScrollMode.AUTO
    page.padding = 20
    page.window.center()

    # 🔐 Persistência do ID do jogador (não gerar novo ID a cada partida)
    if not page.client_storage.contains_key("jogador_id"):
        novo_id = str(uuid4())
        page.client_storage.set("jogador_id", novo_id)
        # print(f"🔥 Novo JOGADOR_ID criado = {novo_id}")

    jogador_id = page.client_storage.get("jogador_id")
    # print(f"🔥 JOGADOR_ID = {jogador_id}")

    nome_jogador = obter_nome_jogador(page)
    sala_jogador = obter_sala_jogador(page)

    if not nome_jogador or not sala_jogador:
        page.dialog = ft.AlertDialog(
            title=ft.Text("Erro"),
            content=ft.Text("Sala ou jogador não definidos. Volte para a tela inicial."),
            actions=[ft.TextButton("OK", on_click=lambda e: page.go("/"))]
        )
        page.dialog.open = True
        page.update()
        return

    sala_ref = db.collection(COLLECTION).document(sala_jogador)

    nome_oponente = ft.Ref[ft.Text]()
    nome_local = ft.Ref[ft.Text]()
    turno_info = ft.Text(size=16, weight=ft.FontWeight.W_500, color=ft.Colors.GREY_600)

    # Estado do jogo
    estado_jogo = {
        "eh_player1": True,
        "turno": "player1",
        "meu": {},
        "meu_caminho": "",
        "ja_exibiu_placar": False,
        "deck_atual": []
    }

    # ✅ Recupera quem é o jogador (player1/player2), se já foi salvo
    if page.client_storage.contains_key("meu_caminho"):
        estado_jogo["meu_caminho"] = page.client_storage.get("meu_caminho")

    page.client_storage.set("placar_enviado", False)
    estado_jogo["ja_exibiu_dialogo_extensao"] = False

    # Refs
    distance_txt_player = ft.Ref[ft.Text]()
    status_txt_player = ft.Ref[ft.Text]()
    limit_txt_player = ft.Ref[ft.Text]()
    last_card_txt_player = ft.Ref[ft.Text]()
    safeties_txt_player = ft.Ref[ft.Text]()
    traffic_light_player = ft.Ref[ft.Image]()
    hand_column_player = ft.Ref[ft.Column]()
    txt_card_player = ft.Ref[ft.TextField]()
    timer_display = ft.Ref[ft.Text]()

    distance_txt_oponente = ft.Ref[ft.Text]()
    status_txt_oponente = ft.Ref[ft.Text]()
    limit_txt_oponente = ft.Ref[ft.Text]()
    last_card_txt_oponente = ft.Ref[ft.Text]()
    safeties_txt_oponente = ft.Ref[ft.Text]()
    traffic_light_oponente = ft.Ref[ft.Image]()
    hand_column_oponente = ft.Ref[ft.Column]()
    nome_oponente_barra = ft.Ref[ft.Text]()
    # 🆕 Refs para os containers do navbar e footer (para responsividade)
    navbar_container_ref = ft.Ref[ft.Container]()
    footer_container_ref = ft.Ref[ft.Container]()

    # COMPONENTES VISUAIS

    navbar = ft.Container(
        ref=navbar_container_ref,
        content=ft.ResponsiveRow(
            controls=[
                ft.Column(col={"xs": 3, "sm": 2, "md": 1}, controls=[ft.Image(src="icons/JC.png", width=50)]),
                ft.Column(col={"xs": 6, "sm": 8, "md": 10}, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                          controls=[ft.Text("Mille Bornes", size=38, font_family="Lobster", color="#180F4A",
                                            text_align=ft.TextAlign.CENTER)]),
                ft.Column(col={"xs": 3, "sm": 2, "md": 1}, controls=[ft.Image(src="images/carro.png", width=70)]),
            ],
            alignment=ft.MainAxisAlignment.SPACE_AROUND,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            run_spacing={"xs": 5, "sm": 0},
            spacing=0,
        ),
        bgcolor=ft.Colors.WHITE,
        padding=ft.Padding(left=10, right=10, top=5, bottom=5),
        height=60,
    )

    # Área do jogador
    player_area = ft.Container(
        expand=True,
        padding=10,
        bgcolor="#ffffff",
        border_radius=10,
        border=ft.border.all(width=1, color=ft.Colors.GREY_200),
        shadow=ft.BoxShadow(blur_radius=4, color=ft.Colors.BLACK12),
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text(
                            value=nome_jogador,
                            size=22,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.BLUE_500
                        ),
                        turno_info,
                        ft.Image(
                            ref=traffic_light_player,
                            src="images/red_light.png",
                            width=30
                        )
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                ),

                ft.Divider(
                    height=1,
                    thickness=2,
                    color=ft.Colors.BLUE_500
                ),
                # LINHA 1: Distância | Situação | Limite
                ft.ResponsiveRow(
                    controls=[
                        ft.Column(
                            col={"xs": 12},
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Text("Distância:", color="#180F4A", size=16, weight=ft.FontWeight.W_500),
                                        ft.Text(ref=distance_txt_player, value="0 Km", color=ft.Colors.GREY_500,
                                                size=16, style=ft.TextStyle(weight=ft.FontWeight.W_500)),
                                        ft.VerticalDivider(width=1, thickness=1, color=ft.Colors.GREY_400),
                                        ft.Text("Situação:", color="#180F4A", size=16, weight=ft.FontWeight.W_500),
                                        ft.Text(ref=status_txt_player, value="Luz Vermelha", color=ft.Colors.RED,
                                                size=16, style=ft.TextStyle(weight=ft.FontWeight.W_500)),
                                        ft.VerticalDivider(width=1, thickness=1, color=ft.Colors.GREY_400),
                                        ft.Text("Limite 50 km:", color="#180F4A", size=16,
                                                weight=ft.FontWeight.W_500),
                                        ft.Text(ref=limit_txt_player, value="Inativo", color=ft.Colors.GREY_500,
                                                size=16, weight=ft.FontWeight.W_500),
                                    ],
                                    spacing=5,
                                    run_spacing=5,
                                    wrap=True,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                                )
                            ]
                        )
                    ],
                    run_spacing={"xs": 5},
                ),
                # LINHA 2: Última carta jogada
                ft.ResponsiveRow(
                    controls=[
                        ft.Column(
                            col={"xs": 12},
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Text("Última carta jogada:", color="#180F4A", size=16,
                                                weight=ft.FontWeight.W_500),
                                        ft.Text(ref=last_card_txt_player, value="Nenhuma", color=ft.Colors.GREY_500,
                                                size=16, weight=ft.FontWeight.W_500),
                                    ],
                                    spacing=5,
                                    wrap=True
                                )
                            ]
                        ),
                    ],
                    run_spacing={"xs": 5},
                ),
                # LINHA 3: Segurança
                ft.ResponsiveRow(
                    controls=[
                        ft.Column(
                            col={"xs": 12},
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Text("Segurança:", color="#180F4A", size=16, weight=ft.FontWeight.W_500),
                                        ft.Text(ref=safeties_txt_player, value="Nenhuma", color=ft.Colors.GREY_500,
                                                size=16, weight=ft.FontWeight.W_500),
                                    ],
                                    spacing=5,
                                    wrap=True
                                )
                            ]
                        ),
                    ],
                    run_spacing={"xs": 5},
                ),
                ft.Divider(
                    height=1,
                    thickness=1,
                    color=ft.Colors.BLUE_500
                ),
                ft.Text(
                    value="Mão do jogador:",
                    color="#180F4A",
                    size=18,
                    weight=ft.FontWeight.W_500
                ),
                ft.Container(
                    expand=True,
                    content=ft.Row(  # <-- MUDANÇA: ft.Column para ft.Row para layout horizontal
                        ref=hand_column_player,
                        spacing=3,  # Aumenta o espaço horizontal entre as cartas
                        wrap=True,  # Permite que as cartas quebrem para a próxima linha
                        vertical_alignment=ft.CrossAxisAlignment.START,  # Alinha os botões verticalmente
                    ),
                ),

            ],
            spacing=10
        )
    )

    LIMITE_DISTANCIA = 1000

    # Barras de progresso
    barra_distancia_jogador = ft.ProgressBar(
        value=0.0,
        bgcolor=ft.Colors.GREY_200,
        color=ft.Colors.BLUE_500,
        height=12,
        expand=True  # Permite a expansão da barra de progresso
    )

    barra_distancia_computador = ft.ProgressBar(
        value=0.0,
        bgcolor=ft.Colors.GREY_200,
        color=ft.Colors.GREEN_400,
        height=12,
        expand=True  # Permite a expansão da barra de progresso
    )

    # Barras de progresso
    barra_distancia_jogador = ft.ProgressBar(
        value=0.0,
        bgcolor=ft.Colors.GREY_200,
        color=ft.Colors.BLUE_500,
        height=12,
        expand=True  # Permite a expansão da barra de progresso
    )

    barra_distancia_computador = ft.ProgressBar(
        value=0.0,
        bgcolor=ft.Colors.GREY_200,
        color=ft.Colors.GREEN_400,
        height=12,
        expand=True  # Permite a expansão da barra de progresso
    )

    graduacao_régua = ft.Column(
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,  # Center the whole ruler
        controls=[
            # Marcadores visuais
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,  # Space out the markers
                controls=[ft.Container(width=1, height=8, bgcolor=ft.Colors.GREY_600) for _ in range(11)],
                expand=True  # Garante que os marcadores preencham a largura total
            ),
            # Textos abaixo da régua
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,  # Space out the texts
                controls=[
                    ft.Text("0 Km", size=14, color=ft.Colors.GREY_600),
                    ft.Text("100", size=14, color=ft.Colors.GREY_600),
                    ft.Text("200", size=14, color=ft.Colors.GREY_600),
                    ft.Text("300", size=14, color=ft.Colors.GREY_600),
                    ft.Text("400", size=14, color=ft.Colors.GREY_600),
                    ft.Text("500", size=14, color=ft.Colors.GREY_600),
                    ft.Text("600", size=14, color=ft.Colors.GREY_600),
                    ft.Text("700", size=14, color=ft.Colors.RED),
                    ft.Text("800", size=14, color=ft.Colors.GREY_600),
                    ft.Text("900", size=14, color=ft.Colors.GREY_600),
                    ft.Text("1000", size=14, color=ft.Colors.RED),
                ],
                expand=True  # Garante que os textos preencham a largura total
            )
        ]
    )

    # Área das barras com graduação para ficar abaixo da área do computador
    progression_bars_area = ft.Column(
        visible=True,
        spacing=5,
        controls=[
            ft.Container(height=10),  # Espaçamento
            ft.Column(
                controls=[
                    ft.Text(
                        value=nome_jogador,
                        color="#180F4A",
                        size=18,
                        weight=ft.FontWeight.W_500
                    ),
                    barra_distancia_jogador,
                ],
                expand=True
            ),
            ft.Container(height=0),
            ft.Column(
                controls=[
                    ft.Text(
                        ref=nome_oponente_barra,
                        value="Oponente",
                        color="#180F4A",
                        size=18,
                        weight=ft.FontWeight.W_500
                    ),
                    barra_distancia_computador,
                ],
                expand=True
            ),
            graduacao_régua,
            ft.Container(height=20)
        ]
    )

    # Área do oponente
    oponente_area = ft.Container(
        expand=True,
        padding=10,
        bgcolor="#ffffff",
        border_radius=10,
        border=ft.border.all(width=1, color=ft.Colors.GREY_200),
        shadow=ft.BoxShadow(blur_radius=4, color=ft.Colors.BLACK12),
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Container(
                            content=ft.Text(
                                ref=nome_oponente,
                                value="Oponente",
                                size=22,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.BLUE_500
                            ),
                            alignment=ft.alignment.center_left,
                            expand=1
                        ),
                        ft.Container(
                            content=ft.Image(
                                ref=traffic_light_oponente,
                                src="images/red_light.png",
                                width=30
                            ),
                            alignment=ft.alignment.center_right,
                            expand=1
                        ),
                    ]
                ),
                ft.Divider(
                    height=1,
                    thickness=2,
                    color=ft.Colors.BLUE_500
                ),
                # LINHA 1: Distância | Situação | Limite (oponente)
                ft.ResponsiveRow(
                    controls=[
                        ft.Column(
                            col={"xs": 12},
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Text("Distância:", color="#180F4A", size=16, weight=ft.FontWeight.W_500),
                                        ft.Text(ref=distance_txt_oponente, value="0 Km", color=ft.Colors.GREY_500,
                                                size=16, weight=ft.FontWeight.W_500),
                                        ft.VerticalDivider(width=1, thickness=1, color=ft.Colors.GREY_400),
                                        ft.Text("Situação:", color="#180F4A", size=16, weight=ft.FontWeight.W_500),
                                        ft.Text(ref=status_txt_oponente, value="Luz Vermelha", color=ft.Colors.RED,
                                                size=16, weight=ft.FontWeight.W_500),
                                        ft.VerticalDivider(width=1, thickness=1, color=ft.Colors.GREY_400),
                                        ft.Text("Limite 50 km:", color="#180F4A", size=16, weight=ft.FontWeight.W_500),
                                        ft.Text(ref=limit_txt_oponente, value="Inativo", color=ft.Colors.GREY_500,
                                                size=16, weight=ft.FontWeight.W_500),
                                    ],
                                    spacing=5,
                                    run_spacing=5,
                                    wrap=True,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                                )
                            ]
                        )
                    ],
                    run_spacing={"xs": 5},
                ),
                # LINHA 2: Última carta jogada (oponente)
                ft.ResponsiveRow(
                    controls=[
                        ft.Column(
                            col={"xs": 12},
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Text("Última carta jogada:", color="#180F4A", size=16,
                                                weight=ft.FontWeight.W_500),
                                        ft.Text(ref=last_card_txt_oponente, value="Nenhuma", color=ft.Colors.GREY_500,
                                                size=16, weight=ft.FontWeight.W_500),
                                    ],
                                    spacing=5,
                                    wrap=True
                                )
                            ]
                        ),
                    ],
                    run_spacing={"xs": 5},
                ),
                # LINHA 3: Segurança (oponente)
                ft.ResponsiveRow(
                    controls=[
                        ft.Column(
                            col={"xs": 12},
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Text("Segurança:", color="#180F4A", size=16, weight=ft.FontWeight.W_500),
                                        ft.Text(ref=safeties_txt_oponente, value="Nenhuma", color=ft.Colors.GREY_500,
                                                size=16, weight=ft.FontWeight.W_500),
                                    ],
                                    spacing=5,
                                    wrap=True
                                )
                            ]
                        ),
                    ],
                    run_spacing={"xs": 5},
                ),
                ft.Divider(
                    height=1,
                    thickness=1,
                    color=ft.Colors.BLUE_500
                ),
                progression_bars_area,
                ft.Text(
                    ref=nome_local,
                    size=16,
                    weight=ft.FontWeight.W_400,
                    color=ft.Colors.GREY_600
                )
            ],
            spacing=10
        )
    )

    middle_area = ft.ResponsiveRow(
        controls=[
            ft.Column(col={"xs": 12, "md": 6}, controls=[player_area],
                      horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Column(col={"xs": 12, "md": 6}, controls=[oponente_area],
                      horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        vertical_alignment=ft.CrossAxisAlignment.START,
        run_spacing={"xs": 20, "sm": 20},
    )

    # Footer
    footer = ft.Container(
        ref=footer_container_ref,
        content=ft.ResponsiveRow(
            controls=[
                ft.Column(col={"xs": 12}, controls=[
                    ft.Text(
                        value="Mille Bornes",
                        size=16,
                        weight=ft.FontWeight.W_400,
                        color=ft.Colors.WHITE,
                        font_family='Lobster',
                        text_align=ft.TextAlign.CENTER,
                        width=float("inf")
                    ),
                    ft.Text(
                        value="© Todos os direitos reservados.",
                        color=ft.Colors.WHITE,
                        size=12,
                        text_align=ft.TextAlign.CENTER,
                        width=float("inf")
                    )
                ])
            ],
            spacing=0,
            run_spacing={"xs": 5},
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        bgcolor="#004C99",
        padding=ft.padding.only(top=0, bottom=0, left=20, right=20),
        border_radius=10,
        margin=ft.margin.only(top=0),
        border=ft.border.all(2, "red"),
        height=70,
    )

    confirm_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Carta inválida"),  # ✅ Título atualizado
        content=ft.Text("Conteúdo será atualizado na chamada."),  # 🔄 Conteúdo genérico
        actions=[],
        actions_alignment=ft.MainAxisAlignment.END
    )

    carta_para_descarte = {"valor": None, "motivo": "Motivo desconhecido"}  # 🔄 Adiciona 'motivo'

    def fechar_dialogo(e=None):
        confirm_dialog.open = False
        if hasattr(page, "dialog"):
            page.dialog = None
        page.update()

    def confirmar_descarte(e=None):
        if getattr(page, "dialog", None) and getattr(page.dialog, "open", False):
            page.dialog.open = False
            page.update()

        carta = carta_para_descarte["valor"]
        descartar_carta(sala_ref, estado_jogo, carta)
        confirm_dialog.open = False
        page.dialog = None
        page.snack_bar = ft.SnackBar(ft.Text(f"🗑️ Carta descartada: {carta['value']} ({carta['type']})"))
        page.snack_bar.open = True
        page.update()

    # Função para manipular o redimensionamento da página
    def _handle_resize(e):
        # Define a largura de um dispositivo móvel como < 768 pixels
        is_mobile_width = page.width < 768

        if navbar_container_ref.current:
            # Oculta a navbar em dispositivos móveis
            navbar_container_ref.current.visible = not is_mobile_width
        if footer_container_ref.current:
            # Oculta o footer em dispositivos móveis
            footer_container_ref.current.visible = not is_mobile_width

        page.update()

    def atualizar_barras(distancia_jogador, distancia_computador):
        if barra_distancia_jogador.page:
            barra_distancia_jogador.value = distancia_jogador / LIMITE_DISTANCIA
            barra_distancia_jogador.update()

        if barra_distancia_computador.page:
            barra_distancia_computador.value = distancia_computador / LIMITE_DISTANCIA
            barra_distancia_computador.update()

    def inicializar_sala(snapshot=None, changes=None, read_time=None):
        sala_data = snapshot.to_dict() if snapshot else None
        if not sala_data:
            sala_ref.set({
                "player1": {
                    "id": jogador_id,
                    "nome": nome_jogador,
                    "distance": 0,
                    "status": "Luz Vermelha",
                    "limite": False,
                    "last_card_played": "Nenhuma",
                    "safeties": [],
                    "com_200": "N",
                    "hand": [],
                    "extensao": False,
                    "aguardando_extensao": False,
                    "finalizar": False

                },
                "turn": "player1",
                "status": "waiting"
            })
        estado_jogo["ja_exibiu_dialogo_extensao"] = False
        page.update()

        # =========================
        # EXTENSÃO DE 1000KM
        # =========================
    def mostrar_extensao_dialogo(e=None):
        # print("🪧 Abrindo diálogo de extensão...")
        # 🔒 Garante que não há outro diálogo aberto
        if hasattr(page, "dialog") and page.dialog:
            page.dialog.open = False
            page.dialog = None
            page.update()

        page.dialog = dialog_extensao
        dialog_extensao.open = True
        page.update()

    def aceitar_extensao(e=None):
        sala_ref.update({
            f"{estado_jogo['meu_caminho']}.extensao": True,
            f"{estado_jogo['meu_caminho']}.aguardando_extensao": False,
            "extensao_ativa": False,
            "aguardando_extensao": False,
            "turn": "player2" if estado_jogo["eh_player1"] else "player1"
        })

        estado_jogo["ja_exibiu_dialogo_extensao"] = True

        if hasattr(page, "dialog") and page.dialog:
            page.dialog.open = False
            page.dialog = None  # 🧼 importante para limpar corretamente
            page.update()

    def recusar_extensao(e=None):
        sala_ref.update({
            f"{estado_jogo['meu_caminho']}.aguardando_extensao": False,
            f"{estado_jogo['meu_caminho']}.finalizar": True,
            "game_status": "finished"
        })

        estado_jogo["ja_exibiu_dialogo_extensao"] = True

        async def fechar_dialogo_e_redirecionar():
            if hasattr(page, "dialog") and page.dialog:
                page.dialog.open = False
                page.update()
                await asyncio.sleep(0.2)
                page.dialog = None
                page.update()

            page.on_keyboard_event = None

            calcular_e_enviar_placar_final(sala_ref, estado_jogo)
            estado_jogo["ja_exibiu_placar"] = True

            await asyncio.sleep(1.2)
            page.go("/placar")

        page.run_task(fechar_dialogo_e_redirecionar)

    dialog_extensao = ft.AlertDialog(
        modal=True,
        title=ft.Text("Extensão de 1000 km!"),
        content=ft.Text("Você atingiu 700 km! Deseja estender sua corrida para 1000 km?"),
        actions=[
            ft.TextButton("Sim", on_click=aceitar_extensao),
            ft.TextButton("Não", on_click=recusar_extensao),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    def distribuir_cartas_internamente():
        deck = create_deck()
        distribuir_cartas(sala_ref, deck)

    # 🧩 Flag global para evitar múltiplos cliques rápidos
    bloqueio_clique = {"ativo": False}

    def tentar_jogar_carta(carta):
        # Impede duplo clique enquanto a jogada anterior ainda é processada
        if bloqueio_clique["ativo"]:
            # print("⏳ Clique ignorado — jogada anterior ainda em andamento.")
            return

        bloqueio_clique["ativo"] = True  # 🔒 Ativa bloqueio temporário

        try:
            # Sucesso pode ser True, "EXTENSAO_PENDENTE", ou a string de MOTIVO
            sucesso = jogar_carta(sala_ref, estado_jogo, carta)
            if sucesso is True:
                corrigir_mao_jogador(sala_ref, estado_jogo)

            elif sucesso == "EXTENSAO_PENDENTE":
                # print("⏳ Extensão pendente. Aguardando decisão do jogador.")

                # 🛠️ Corrige a mão mesmo com extensão pendente
                corrigir_mao_jogador(sala_ref, estado_jogo)

                # Força atualização do snapshot com delay para refletir os 700km
                def recheck():
                    time.sleep(0.8)
                    snapshot = sala_ref.get()
                    on_snapshot([snapshot], None, None)

                threading.Thread(target=recheck).start()
                return

            else:
                carta_para_descarte["valor"] = carta

                # 🧠 Captura o motivo. Se for False, usa motivo genérico.
                motivo = sucesso if isinstance(sucesso, str) else "motivo não especificado pela regra"
                carta_para_descarte["motivo"] = motivo

                # 📝 Altera o conteúdo do diálogo com base na nova regra
                confirm_dialog.content = ft.Text(
                    f"A carta '{carta['value']}' não pode ser jogada agora porque {motivo}.\n\n"
                    f"Deseja descartá-la?"
                )

                confirm_dialog.actions = [
                    # 📝 Botão 'Não'
                    ft.TextButton("Não", on_click=fechar_dialogo),
                    # 📝 Botão 'Sim', com foco e aceitando ENTER
                    ft.ElevatedButton("Sim", on_click=confirmar_descarte, autofocus=True)
                ]

                page.dialog = confirm_dialog
                confirm_dialog.open = True
                page.update()

        finally:
            # 🔓 Libera o clique após pequeno intervalo (para evitar duplo toque)
            def liberar_bloqueio():
                time.sleep(0.6)
                bloqueio_clique["ativo"] = False

            threading.Thread(target=liberar_bloqueio).start()

    def on_snapshot(doc_snapshot, changes, read_time):
        if not doc_snapshot:
            return

        for doc in doc_snapshot:
            data = doc.to_dict()
            if not data:
                return

            # 🔓 Desbloqueia automaticamente após exibir o placar
            if data.get("game_status") == "finished" and estado_jogo.get("ja_exibiu_placar", False):
                if estado_jogo.get("bloquear_atualizacoes", False):
                    estado_jogo["bloquear_atualizacoes"] = False
                    # print("🔓 Bloqueio removido automaticamente após exibição do placar.")

            # 🧩 Ignora se o bloqueio estiver ativo (ex: recusar extensão)
            if estado_jogo.get("bloquear_atualizacoes", False):
                # print("⏸️ Snapshot ignorado: bloqueio ativo (bloquear_atualizacoes=True).")
                return

            jogador_1 = data.get("player1", {})
            jogador_2 = data.get("player2", {})

            p1_id = jogador_1.get("id")
            p2_id = jogador_2.get("id")

            # Redefine caminho automaticamente
            if not estado_jogo["meu_caminho"]:
                if jogador_id == p1_id:
                    estado_jogo["meu_caminho"] = "player1"
                elif jogador_id == p2_id:
                    estado_jogo["meu_caminho"] = "player2"
                else:
                    pass
                    # print("⚠️ jogador_id não corresponde a player1 nem player2.")

            # print("DEBUG: jogador_id local =", jogador_id)
            # print("DEBUG: player1.id =", p1_id)
            # print("DEBUG: player2.id =", p2_id)

            # ✅ Auto registro se jogador não estiver presente
            if jogador_id != p1_id and jogador_id != p2_id:
                # print("⚠️ Este jogador ainda não está na sala. Tentando se registrar...")

                if not p1_id:
                    # print("✅ Registrando jogador como player1")
                    sala_ref.update({
                        "player1": {
                            "id": jogador_id,
                            "nome": nome_jogador,
                            "distance": 0,
                            "status": "Luz Vermelha",
                            "limite": False,
                            "last_card_played": "Nenhuma",
                            "safeties": [],
                            "com_200": "N",
                            "hand": [],
                            "finalizar": False,
                            "placar": {"total_geral": 0, "atual_mao": {}}
                        }
                    })
                elif not p2_id:
                    # print("✅ Registrando jogador como player2")
                    sala_ref.update({
                        "player2": {
                            "id": jogador_id,
                            "nome": nome_jogador,
                            "distance": 0,
                            "status": "Luz Vermelha",
                            "limite": False,
                            "last_card_played": "Nenhuma",
                            "safeties": [],
                            "com_200": "N",
                            "hand": [],
                            "finalizar": False,
                            "placar": {"total_geral": 0, "atual_mao": {}}
                        }
                    })
                else:
                    pass
                    # print("❌ Sala cheia. Esse jogador não pode entrar.")
                return

            # print("🔥 JOGADOR_ID =", jogador_id)

            # ✅ Identifica o jogador
            eh_player1 = p1_id == jogador_id
            estado_jogo["eh_player1"] = eh_player1
            estado_jogo["turno"] = data.get("turn", "")
            estado_jogo["meu"] = jogador_1 if eh_player1 else jogador_2
            estado_jogo["meu_caminho"] = "player1" if eh_player1 else "player2"

            # ✅ Armazena no client_storage
            try:
                page.client_storage.set("meu_caminho", estado_jogo["meu_caminho"])
                page.client_storage.set("eh_player1", eh_player1)
            except Exception as e:
                pass
                # print(f"⚠️ Erro ao salvar dados no client_storage: {e}")

            meu = estado_jogo["meu"]
            oponente = jogador_2 if eh_player1 else jogador_1

            # ✅ Criação automática do deck
            if "deck" not in data:
                if p1_id and p2_id:
                    # print("✅ Deck ausente. Distribuindo cartas.")
                    distribuir_cartas_internamente()
                else:
                    pass
                    # print("⚠️ Deck ausente mas jogadores ainda não prontos.")
                return

            # ✅ Verifica se precisa mostrar extensão
            extensao_ativa = data.get("extensao_ativa", False)
            distancia_meu = meu.get("distance", 0)

            # print("🔍 VERIFICAÇÃO EXTENSÃO:")
            # print(f"  - distancia_meu = {distancia_meu}")
            # print(f"  - meu.aguardando_extensao = {meu.get('aguardando_extensao')}")
            # print(f"  - meu.extensao = {meu.get('extensao')}")
            # print(f"  - meu.finalizar = {meu.get('finalizar')}")
            # print(f"  - extensao_ativa = {extensao_ativa}")

            if (
                    distancia_meu == 700
                    and meu.get("aguardando_extensao", False)
                    and not estado_jogo.get("ja_exibiu_dialogo_extensao", False)
            ):
                # print("✅ Condições para extensão atendidas. Exibindo diálogo.")
                estado_jogo["ja_exibiu_dialogo_extensao"] = True
                mostrar_extensao_dialogo()

            # 🎨 --- Atualização de UI completa ---
            nome_oponente.current.value = oponente.get("nome", "Oponente")
            if nome_oponente_barra.current:
                nome_oponente_barra.current.value = oponente.get("nome", "Oponente")

            deck = data.get("deck", [])
            nome_local.current.value = f"Qtde cartas: {len(deck)}"

            turno_info.value = "✅ Sua vez!" if (
                    (eh_player1 and data["turn"] == "player1")
                    or (not eh_player1 and data["turn"] == "player2")
            ) else "⏳ Aguardando o outro jogador..."

            # 🃏 Mão do jogador
            # print(f"DEBUG: Mão do jogador no snapshot: {meu.get('hand', [])}")
            hand_column_player.current.controls.clear()
            is_my_turn = (eh_player1 and data["turn"] == "player1") or (not eh_player1 and data["turn"] == "player2")

            for carta_item in meu.get("hand", []):
                tipo = carta_item.get("type")
                cor = ft.Colors.BLACK
                icone = "❓"
                if tipo == "ataque":
                    icone = "⚠️"
                    cor = ft.Colors.RED
                elif tipo == "defesa":
                    icone = "🛡️"
                    cor = ft.Colors.GREEN
                elif tipo == "segurança":
                    icone = "⭐"
                    cor = ft.Colors.ORANGE
                elif tipo == "distancia":
                    icone = "🚗"
                    cor = ft.Colors.BLUE

                hand_column_player.current.controls.append(
                    ft.ElevatedButton(
                        text=f"{icone} {carta_item['value']}",
                        on_click=(lambda e, c=carta_item: tentar_jogar_carta(c)) if is_my_turn else None,
                        opacity=1.0 if is_my_turn else 0.5,
                        disabled=not is_my_turn,
                        style=ft.ButtonStyle(
                            color=cor,
                            padding=ft.Padding(8, 4, 8, 4),
                            shape=ft.RoundedRectangleBorder(radius=6),
                            bgcolor=ft.Colors.WHITE,
                            side=ft.BorderSide(2, cor)
                        )
                    )
                )

            # print(f"DEBUG: Número de controles na mão (após populado): {len(hand_column_player.current.controls)}")

            # 🧭 UI - jogador
            if distance_txt_player.current:
                distance_txt_player.current.value = f'{meu.get("distance", 0)} Km'
                distance_txt_player.current.color = ft.Colors.BLUE if meu.get("distance", 0) > 0 else ft.Colors.GREY_500

            if status_txt_player.current:
                status_txt_player.current.value = meu.get("status", "Luz Vermelha")
                status_txt_player.current.color = ft.Colors.GREEN if meu.get("status") == "Luz Verde" else ft.Colors.RED

            if limit_txt_player.current:
                limite = meu.get("limite", False)
                limit_txt_player.current.value = "Ativo" if limite else "Inativo"
                limit_txt_player.current.color = ft.Colors.AMBER_700 if limite else ft.Colors.GREY_500

            if last_card_txt_player.current:
                ultima = meu.get("last_card_played", "Nenhuma")
                last_card_txt_player.current.value = ultima
                last_card_txt_player.current.color = ft.Colors.BLUE if ultima != "Nenhuma" else ft.Colors.GREY_500

            if safeties_txt_player.current:
                segs = ' | '.join(meu.get("safeties", [])) or "Nenhuma"
                safeties_txt_player.current.value = segs
                safeties_txt_player.current.color = ft.Colors.ORANGE if meu.get("safeties") else ft.Colors.GREY_500

            if traffic_light_player.current and traffic_light_player.current.page:
                status = meu.get("status", "")
                limite = meu.get("limite", False)
                if status in ["Luz Vermelha", "Sem Gasolina", "Pneu Furado", "Acidente"]:
                    img = "images/red_light.png"
                elif limite:
                    img = "images/yellow_light.png"
                else:
                    img = "images/green_light.png"
                traffic_light_player.current.src = img
                traffic_light_player.current.update()

            # 🧭 UI - oponente
            if distance_txt_oponente.current:
                distance_txt_oponente.current.value = f'{oponente.get("distance", 0)} Km'
                distance_txt_oponente.current.color = ft.Colors.BLUE if oponente.get("distance",
                                                                                     0) > 0 else ft.Colors.GREY_500

            if status_txt_oponente.current:
                status_txt_oponente.current.value = oponente.get("status", "Luz Vermelha")
                status_txt_oponente.current.color = ft.Colors.GREEN if oponente.get(
                    "status") == "Luz Verde" else ft.Colors.RED

            if limit_txt_oponente.current:
                limite_op = oponente.get("limite", False)
                limit_txt_oponente.current.value = "Ativo" if limite_op else "Inativo"
                limit_txt_oponente.current.color = ft.Colors.AMBER_700 if limite_op else ft.Colors.GREY_500

            if last_card_txt_oponente.current:
                ultima_op = oponente.get("last_card_played", "Nenhuma")
                last_card_txt_oponente.current.value = ultima_op
                last_card_txt_oponente.current.color = ft.Colors.BLUE if ultima_op != "Nenhuma" else ft.Colors.GREY_500

            if safeties_txt_oponente.current:
                segs_op = ' | '.join(oponente.get("safeties", [])) or "Nenhuma"
                safeties_txt_oponente.current.value = segs_op
                safeties_txt_oponente.current.color = ft.Colors.ORANGE if oponente.get(
                    "safeties") else ft.Colors.GREY_500

            if traffic_light_oponente.current and traffic_light_oponente.current.page:
                status = oponente.get("status", "")
                limite = oponente.get("limite", False)
                if status in ["Luz Vermelha", "Sem Gasolina", "Pneu Furado", "Acidente"]:
                    img = "images/red_light.png"
                elif limite:
                    img = "images/yellow_light.png"
                else:
                    img = "images/green_light.png"
                traffic_light_oponente.current.src = img
                traffic_light_oponente.current.update()

            # 🏁 Atualiza barras de progresso
            atualizar_barras(meu.get("distance", 0), oponente.get("distance", 0))

            # 🧮 Finaliza jogo e abre placar
            if data.get("game_status") == "finished" and not estado_jogo.get("ja_exibiu_placar", False):
                calcular_e_enviar_placar_final(sala_ref, estado_jogo)
                estado_jogo["ja_exibiu_placar"] = True

                import threading
                def delayed_redirect():
                    import time
                    time.sleep(1.5)
                    try:
                        page.go("/placar")
                        # print("➡️ Redirecionado para /placar.")
                    except Exception as e:
                        pass
                        # print(f"⚠️ Erro no redirecionamento para placar: {e}")

                threading.Thread(target=delayed_redirect).start()

            # 🔄 Atualiza página de forma segura
            try:
                if hasattr(page, "update") and callable(page.update):
                    page.update()
            except Exception as e:
                pass
                # print(f"⚠️ Erro ao atualizar página: {e}")

    sala_ref.on_snapshot(on_snapshot)
    snapshot = sala_ref.get()
    inicializar_sala(snapshot=snapshot)

    # 1. Cria e armazena o objeto View
    view = ft.View(
        route="/jogo",
        controls=[
            confirm_dialog,
            dialog_extensao,  # Dialog_extensao now defined once and added here.
            ft.Column(
                spacing=10,
                controls=[
                    navbar,
                    middle_area,
                    ft.Divider(),
                    ft.Text(f"🃏 Sala: {sala_jogador}", size=22, weight=ft.FontWeight.BOLD),
                    footer
                ],
                scroll=ft.ScrollMode.ADAPTIVE,
                expand=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER
            )
        ]
    )
    # 2. Anexa o manipulador de redimensionamento
    view.on_resize = _handle_resize

    # 3. Força a execução inicial para ajustar visibilidade no carregamento
    _handle_resize(None)

    # 4. Retorna a view configurada
    return view


def calcular_e_enviar_placar_final(sala_ref, estado_jogo):
    snapshot = sala_ref.get()
    sala_data = snapshot.to_dict()

    meu_caminho = estado_jogo["meu_caminho"]
    oponente_caminho = "player2" if meu_caminho == "player1" else "player1"

    meu = sala_data.get(meu_caminho, {})
    oponente = sala_data.get(oponente_caminho, {})

    # print(f"🚗 Estado do jogador: distancia={meu.get('distance')} | com_200={meu['com_200']}")

    # print("📍 ENTRANDO EM calcular_e_enviar_placar_final")

    # ✅ Evita computar placar duplicado
    if meu.get("placar_registrado", False):
        # print("⚠️ Placar já foi registrado para este jogador. Ignorando duplicata.")
        return

    deck_vazio = not sala_data.get("deck")

    # Variáveis do Jogador Local (MEU)
    distance = meu.get("distance", 0)
    extensao = meu.get("extensao", False)
    safeties = meu.get("safeties", [])
    resposta = meu.get("safety_responses", 0)

    # Variáveis do Oponente
    distance_op = oponente.get("distance", 0)
    extensao_op = oponente.get("extensao", False)
    safeties_op = oponente.get("safeties", [])
    resposta_op = oponente.get("safety_responses", 0)

    # ====================================================================
    # 🎯 LÓGICA CORRIGIDA PARA BÔNUS 'PERCURSO COMPLETADO'
    # ====================================================================

    # 1. Determina o limite de distância FINAL da mão (1000km se qualquer um aceitou a extensão)
    limite_efetivo = 1000 if extensao or extensao_op else 700

    # Lógica para o Jogador Local (MEU)
    # 2. Verifica se MEU atingiu o limite FINAL da mão (700km ou 1000km)
    atingiu_limite_final = (
            (distance == 1000 and limite_efetivo == 1000) or
            (distance == 700 and limite_efetivo == 700)
    )

    # 3. Define se MEU é o Vencedor da Mão: Atingiu o limite FINAL E tem a maior distância.
    #    (Se o deck acabou e ambos atingiram o limite, é um empate, ambos recebem o bônus)
    eh_vencedor_da_mao = (
            atingiu_limite_final and
            distance >= distance_op
    )

    # 4. Aplica o bônus de Percurso Completado
    placar_mao_percurso_completo = 0
    # O bônus é aplicado se é o vencedor que atingiu o limite, ou se o deck acabou (empate) e atingiu o limite.
    if eh_vencedor_da_mao:
        if limite_efetivo == 1000:
            placar_mao_percurso_completo = 300
        elif limite_efetivo == 700:
            placar_mao_percurso_completo = 200

    # 🎯 Bônus por fim de baralho
    # Corrigido: o bônus de fim de baralho só deve ser dado se o jogador completou o percurso e o deck esgotou
    bonus_fim_baralho = 0
    if deck_vazio and atingiu_limite_final:
        bonus_fim_baralho = 500 if limite_efetivo == 700 else 400

    placar_mao = {
        "distancia": distance,
        "segurancas": len(safeties) * 100,
        "todas_segurancas": 400 if len(safeties) == 4 else 0,
        "seguranca_em_resposta": resposta * 300,
        "percurso_completo": placar_mao_percurso_completo,  # <-- CORRIGIDO AQUI
        "com_200": (
            300 if meu.get("com_200") == "N" and distance == 1000 else
            200 if meu.get("com_200") == "N" and distance == 700 else
            0
        ),
        "oponente_zero": (
            500 if distance == 1000 and distance_op == 0 else
            300 if distance == 700 and distance_op == 0 else
            0
        ),
        "bonus_extensao": 300 if extensao else 0,
        "fim_do_baralho": bonus_fim_baralho,
    }

    placar_mao["total_da_mao"] = sum(placar_mao.values())

    # Lógica para o Oponente
    # 2. Verifica se OPONENTE atingiu o limite FINAL da mão (700km ou 1000km)
    atingiu_limite_final_op = (
            (distance_op == 1000 and limite_efetivo == 1000) or
            (distance_op == 700 and limite_efetivo == 700)
    )

    # 3. Define se OPONENTE é o Vencedor da Mão: Atingiu o limite FINAL E tem a maior distância (ou empate)
    eh_vencedor_da_mao_op = (
            atingiu_limite_final_op and
            distance_op >= distance
    )

    # 4. Aplica o bônus de Percurso Completado
    placar_oponente_percurso_completo = 0
    if eh_vencedor_da_mao_op:
        if limite_efetivo == 1000:
            placar_oponente_percurso_completo = 300
        elif limite_efetivo == 700:
            placar_oponente_percurso_completo = 200

    # 🎯 Bônus por fim de baralho
    bonus_fim_baralho_op = 0
    if deck_vazio and atingiu_limite_final_op:
        bonus_fim_baralho_op = 500 if limite_efetivo == 700 else 400

    placar_oponente = {
        "distancia": distance_op,
        "segurancas": len(safeties_op) * 100,
        "todas_segurancas": 400 if len(safeties_op) == 4 else 0,
        "seguranca_em_resposta": resposta_op * 300,
        "percurso_completo": placar_oponente_percurso_completo,  # <-- CORRIGIDO AQUI
        "com_200": (
            300 if oponente.get("com_200") == "N" and distance_op == 1000 else
            200 if oponente.get("com_200") == "N" and distance_op == 700 else
            0
        ),
        "oponente_zero": (
            500 if distance_op == 1000 and distance == 0 else
            300 if distance_op == 700 and distance == 0 else
            0
        ),
        "bonus_extensao": 300 if extensao_op else 0,
        "fim_do_baralho": bonus_fim_baralho_op,
    }

    placar_oponente["total_da_mao"] = sum(placar_oponente.values())

    # 🧮 Soma do total geral
    novo_total_meu = meu.get("placar", {}).get("total_geral", 0) + placar_mao["total_da_mao"]
    novo_total_oponente = oponente.get("placar", {}).get("total_geral", 0) + placar_oponente["total_da_mao"]

    # 📝 Atualizar Firestore
    updates = {
        f"{meu_caminho}.placar.atual_mao": placar_mao,
        f"{meu_caminho}.placar.total_geral": novo_total_meu,
        f"{meu_caminho}.placar_registrado": True,
        f"{meu_caminho}.placar_visto": True,  # ✅ Marca que o jogador viu o placar
        f"{oponente_caminho}.placar.atual_mao": placar_oponente,
        f"{oponente_caminho}.placar.total_geral": novo_total_oponente
    }

    # 🧠 Verifica se é fim de jogo com vencedor
    fim_de_jogo = (novo_total_meu >= 5000 or novo_total_oponente >= 5000) and (novo_total_meu != novo_total_oponente)

    # 📝 Envia atualizações para o Firestore
    sala_ref.update(updates)

    # print("✅ Placar da mão registrado no Firestore:", placar_mao)

# ===========================================================
# 🔧 Utilitários para abrir e fechar diálogos com segurança
# ===========================================================
async def abrir_dialogo_com_segurança(page, novo_dialogo: ft.AlertDialog):
    if getattr(page, "dialog", None):
        try:
            page.dialog.open = False
            page.update()
            await asyncio.sleep(0.1)
            page.dialog = None
        except Exception as e:
            pass
            # print(f"⚠️ Erro ao fechar diálogo anterior: {e}")

    page.dialog = novo_dialogo
    novo_dialogo.open = True

    try:
        page.update()
        await asyncio.sleep(0.05)
        # print("✅ Diálogo aberto com sucesso:", getattr(novo_dialogo.title, "value", "Sem título"))
    except Exception as e:
        pass
        # print(f"❌ Falha ao abrir diálogo: {e}")


async def fechar_dialogo_com_segurança(page):
    if getattr(page, "dialog", None):
        try:
            page.dialog.open = False
            page.update()
            await asyncio.sleep(0.05)
            page.dialog = None
        except Exception as e:
            pass
            # print(f"⚠️ Erro ao fechar diálogo: {e}")
