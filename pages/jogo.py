# jogo

import os
import json
import flet as ft
from players_area import AreaDeJogoDoJogador
from progression_bar import AreaDeProgressoComparativo
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
    print('Jogo View')
    page.title = "Mille Bornes Multiplayer"
    page.scroll = ft.ScrollMode.AUTO
    page.padding = 20
    page.window.center()

    # 🔐 Persistência do ID do jogador (não gerar novo ID a cada partida)
    if not page.client_storage.contains_key("jogador_id"):
        novo_id = str(uuid4())
        page.client_storage.set("jogador_id", novo_id)
        print(f"🔥 Novo JOGADOR_ID criado = {novo_id}")

    jogador_id = page.client_storage.get("jogador_id")
    print(f"🔥 JOGADOR_ID = {jogador_id}")

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
        # print(f'Estado do Jogo {estado_jogo["meu_caminho"]}')

    page.client_storage.set("placar_enviado", False)
    estado_jogo["ja_exibiu_dialogo_extensao"] = False

    # Refs para os componentes globais e a barra de progresso
    nome_oponente = ft.Ref[ft.Text]()  # Nome do oponente na área principal
    nome_oponente_barra = ft.Ref[ft.Text]()  # Ref para o nome na área da barra de progresso

    # 🧩 Referências necessárias para as barras de progresso
    barra_distancia_jogador = ft.Ref[ft.ProgressBar]()  # Controle real da barra do jogador local
    barra_distancia_computador = ft.Ref[ft.ProgressBar]()  # Controle real da barra do oponente

    # 🎨 Definição dos Controles reais (com Refs)
    barra_jogador_control = ft.ProgressBar(
        ref=barra_distancia_jogador,
        value=0.0,
        height=10,
        color=ft.Colors.BLUE_500,
        bgcolor=ft.Colors.GREY_300
    )

    barra_oponente_control = ft.ProgressBar(
        ref=barra_distancia_computador,
        value=0.0,
        height=10,
        color=ft.Colors.GREEN_500,
        bgcolor=ft.Colors.GREY_300
    )

    # 📏 Definição da régua de graduação (usando a definição mais detalhada)
    graduacao_régua = ft.Column(
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            # Marcadores visuais
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[ft.Container(width=1, height=8, bgcolor=ft.Colors.GREY_600) for _ in range(11)],
                expand=True
            ),
            # Textos abaixo da régua
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Text("0 Km", size=12, color=ft.Colors.GREY_600),
                    ft.Text("100", size=12, color=ft.Colors.GREY_600),
                    ft.Text("200", size=12, color=ft.Colors.GREY_600),
                    ft.Text("300", size=12, color=ft.Colors.GREY_600),
                    ft.Text("400", size=12, color=ft.Colors.GREY_600),
                    ft.Text("500", size=12, color=ft.Colors.GREY_600),
                    ft.Text("600", size=12, color=ft.Colors.GREY_600),
                    ft.Text("700", size=12, color=ft.Colors.RED),
                    ft.Text("800", size=12, color=ft.Colors.GREY_600),
                    ft.Text("900", size=12, color=ft.Colors.GREY_600),
                    ft.Text("1000", size=12, color=ft.Colors.RED),
                ],
                expand=True
            )
        ]
    )

    # 🆕 Refs para os containers do navbar e footer (para responsividade)
    navbar_container_ref = ft.Ref[ft.Container]()
    footer_container_ref = ft.Ref[ft.Container]()

    # NOVAS INSTÂNCIAS DE COMPONENTES
    area_jogador_local = AreaDeJogoDoJogador(nome_jogador=nome_jogador, eh_local=True)
    area_oponente = AreaDeJogoDoJogador(nome_jogador="Oponente", eh_local=False)
    # O nome do oponente será atualizado dinamicamente pelo on_snapshot

    # 🌟 NOVO: Instancia o componente de progresso comparativo
    progression_bars_area = AreaDeProgressoComparativo(
        barra_jogador=barra_jogador_control,
        barra_oponente=barra_oponente_control,
        graduacao_regua=graduacao_régua,
        nome_jogador=nome_jogador,
        nome_oponente_ref=nome_oponente_barra  # Passa a Ref para o componente gerenciar
    )

    # COMPONENTES VISUAIS

    # navbar com Ref e visibilidade controlada
    navbar = ft.Container(
        ref=navbar_container_ref,
        content=ft.ResponsiveRow(
            controls=[
                ft.Column(col={"xs": 3, "sm": 2, "md": 1}, controls=[ft.Image(src="icons/JC.png", width=50)]),
                ft.Column(col={"xs": 6, "sm": 8, "md": 10}, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                          controls=[ft.Text("Mille Bornes", size=34, font_family="Lobster", color="#180F4A",
                                            text_align=ft.TextAlign.CENTER)]),
                ft.Column(col={"xs": 3, "sm": 2, "md": 1}, controls=[ft.Image(src="images/carro.png", width=60)]),
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
        # ... outros paddings/estilos
        content=area_jogador_local  # Já é um UserControl, então pode ser adicionado diretamente
    )

    LIMITE_DISTANCIA = 1000

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
                area_oponente,  # <-- O corpo principal agora é a classe
                progression_bars_area,  # <-- Usa a NOVA CLASSE aqui
                ft.Text(ref=nome_local, size=16, weight=ft.FontWeight.W_400, color=ft.Colors.GREY_600)
            ],
            spacing=5
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

    # Footer com Ref e visibilidade controlada
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
        padding=ft.padding.only(top=20, bottom=0, left=20, right=20),
        border_radius=10,
        margin=ft.margin.only(top=80),
        border=ft.border.all(2, "red"),
        # height=70,
        visible=True
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
        # As refs são usadas diretamente para atualizar as barras de progresso
        # O .page é usado como uma checagem de segurança (controle anexado)
        if barra_distancia_jogador.current and barra_distancia_jogador.current.page:
            barra_distancia_jogador.current.value = distancia_jogador / LIMITE_DISTANCIA
            barra_distancia_jogador.current.update()

        if barra_distancia_computador.current and barra_distancia_computador.current.page:
            barra_distancia_computador.current.value = distancia_computador / LIMITE_DISTANCIA
            barra_distancia_computador.current.update()

    def mostrar_extensao_dialogo(e=None):
        print("🪧 Abrindo diálogo de extensão...")

        # Não feche diálogos existentes. Apenas abra o novo.
        page.dialog = dialog_extensao
        dialog_extensao.open = True
        page.update()

    def aceitar_extensao(e):
        print("🟢 Jogador ACEITOU a extensão — ativando e passando turno.")

        eh_player1_local = estado_jogo.get("eh_player1", None)
        if eh_player1_local is None:
            print("⚠️ ERRO: estado_jogo['eh_player1'] não definido.")
            return

        meu_caminho = "player1" if eh_player1_local else "player2"
        adversario = "player2" if eh_player1_local else "player1"
        novo_turno = adversario

        try:
            sala_ref.update({
                "extensao_ativa": True,
                f"{meu_caminho}.extensao": True,  # ✅ Agora o jogador também marca que aceitou
                f"{meu_caminho}.aguardando_extensao": False,
                f"{adversario}.aguardando_extensao": False,
                "turn": novo_turno
            })
        except Exception as ex:
            print(f"⚠️ Erro ao ativar extensão/turno: {ex}")

        dialog_extensao.open = False
        page.update()

    def recusar_extensao(e=None):
        """
        Jogador escolheu NÃO estender para 1000 km.
        Encerra corretamente a mão para AMBOS os jogadores.
        """
        try:
            meu_caminho = estado_jogo.get("meu_caminho")

            if not meu_caminho:
                snap = sala_ref.get().to_dict() or {}
                p1 = snap.get("player1", {})
                p2 = snap.get("player2", {})
                if p1.get("id") == jogador_id:
                    meu_caminho = "player1"
                elif p2.get("id") == jogador_id:
                    meu_caminho = "player2"
                else:
                    print("⚠️ recusar_extensao: não consegui determinar o caminho do jogador.")
                    return
                estado_jogo["meu_caminho"] = meu_caminho

            adversario = "player1" if meu_caminho == "player2" else "player2"

            print(f"🚫 {meu_caminho} recusou a extensão. Encerrando partida DEFINITIVAMENTE.")

            # 🔥 ENCERRA A MÃO PARA AMBOS
            sala_ref.update({
                f"{meu_caminho}.aguardando_extensao": False,
                f"{meu_caminho}.finalizar": True,
                f"{meu_caminho}.extensao": False,

                f"{adversario}.aguardando_extensao": False,
                f"{adversario}.finalizar": True,

                "game_status": "finished",
                "turn": None,
                "extensao_ativa": False
            })

            estado_jogo["ja_exibiu_dialogo_extensao"] = True

            async def fechar_dialogo_e_redirecionar():

                # Fecha o diálogo
                if hasattr(page, "dialog") and page.dialog:
                    page.dialog.open = False
                    page.update()
                    await asyncio.sleep(0.2)
                    page.dialog = None
                    page.update()

                # Evita duplo disparo
                page.on_keyboard_event = None

                # 🔥 Calcula o placar uma ÚNICA vez
                try:
                    calcular_e_enviar_placar_final(sala_ref, estado_jogo)
                except Exception as exc:
                    print(f"⚠️ Erro ao calcular placar em recusar_extensao: {exc}")

                estado_jogo["ja_exibiu_placar"] = True

                await asyncio.sleep(1.0)

                # Redireciona
                try:
                    page.go("/placar")
                except Exception as exc:
                    print(f"⚠️ Erro ao redirecionar para /placar: {exc}")

            page.run_task(fechar_dialogo_e_redirecionar)

        except Exception as exc:
            print(f"⚠️ Erro geral em recusar_extensao: {exc}")

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
            print("⏳ Clique ignorado — jogada anterior ainda em andamento.")
            return

        bloqueio_clique["ativo"] = True  # 🔒 Ativa bloqueio temporário

        try:
            # Sucesso pode ser True, "EXTENSAO_PENDENTE", ou a string de MOTIVO
            sucesso = jogar_carta(sala_ref, estado_jogo, carta)
            if sucesso is True:
                corrigir_mao_jogador(sala_ref, estado_jogo)
                return  # ✅ encerra fluxo corretamente

            elif sucesso == "EXTENSAO_PENDENTE":
                print("⏳ Extensão pendente. Aguardando decisão do jogador.")

                # 🛠️ Corrige a mão mesmo com extensão pendente
                corrigir_mao_jogador(sala_ref, estado_jogo)

                def recheck():
                    time.sleep(0.8)
                    snapshot = sala_ref.get()
                    on_snapshot([snapshot], None, None)

                threading.Thread(target=recheck).start()
                return  # ✅ encerra fluxo corretamente

            else:
                carta_para_descarte["valor"] = carta

                motivo = sucesso if isinstance(sucesso, str) else "motivo não especificado pela regra"
                carta_para_descarte["motivo"] = motivo

                confirm_dialog.content = ft.Text(
                    f"A carta '{carta['value']}' não pode ser jogada agora porque {motivo}.\n\n"
                    f"Deseja descartá-la?"
                )

                confirm_dialog.actions = [
                    ft.TextButton("Não", on_click=fechar_dialogo),
                    ft.ElevatedButton("Sim", on_click=confirmar_descarte, autofocus=True)
                ]

                page.dialog = confirm_dialog
                confirm_dialog.open = True
                page.update()

                return  # 🔥🔥🔥 ESSA LINHA É A MAIS IMPORTANTE 🔥🔥🔥

        finally:
            # 🔓 Libera o clique após pequeno intervalo (para evitar duplo toque)
            def liberar_bloqueio():
                time.sleep(0.6)
                bloqueio_clique["ativo"] = False

            threading.Thread(target=liberar_bloqueio).start()

    # 🔆 NOVO: função para atualizar o semáforo com base em status/limite (não mais no turno)
    def atualizar_semaforo(area: AreaDeJogoDoJogador, jogador_data: dict):
        """
        Regras:
        - Quando o status do jogador NÃO for 'Luz Verde' → vermelho
        - Quando o status for 'Luz Verde' e limite=False → verde
        - Quando o status for 'Luz Verde' e limite=True  → amarelo
        """
        status = jogador_data.get("status", "Luz Vermelha")
        limite_50 = jogador_data.get("limite", False)

        # Escolhe a imagem correta
        if status != "Luz Verde":
            img = "images/red_light.png"
        else:
            img = "images/yellow_light.png" if limite_50 else "images/green_light.png"

        # Garante que o controle existe
        if getattr(area, "traffic_light", None) and area.traffic_light.current:
            area.traffic_light.current.src = img
            try:
                area.traffic_light.current.update()
            except Exception:
                pass

    def on_snapshot(doc_snapshot, changes, read_time):
        if not doc_snapshot:
            return

        for doc in doc_snapshot:
            data = doc.to_dict()
            if not data:
                return

            # ---------------------------------------------------------
            # 1) REDIRECIONAMENTO RÁPIDO PARA PLACAR (se já terminou)
            # ---------------------------------------------------------
            if (
                    data.get("game_status") == "finished"
                    and not data.get("player1", {}).get("aguardando_extensao", False)
                    and not data.get("player2", {}).get("aguardando_extensao", False)
                    and data.get("placar_calculado", False)
            ):
                print("🏁 Partida encerrada — redirecionando para o placar.")
                try:
                    page.go("/placar")
                except Exception as exc:
                    print(f"⚠️ Erro ao ir para placar no snapshot: {exc}")
                return

            # ---------------------------------------------------------
            # 2) BLOQUEIO LOCAL TEMPORÁRIO (ex: enquanto um diálogo está aberto)
            # ---------------------------------------------------------
            if estado_jogo.get("bloquear_atualizacoes", False):
                return

            jogador_1 = data.get("player1", {}) or {}
            jogador_2 = data.get("player2", {}) or {}

            p1_id = jogador_1.get("id")
            p2_id = jogador_2.get("id")

            # ---------------------------------------------------------
            # 3) IDENTIFICAÇÃO DO JOGADOR
            # ---------------------------------------------------------
            if jogador_id == p1_id:
                eh_player1 = True
            elif jogador_id == p2_id:
                eh_player1 = False
            else:
                # auto-registro se ainda não estiver na sala
                if not p1_id:
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
                return

            # ---------------------------------------------------------
            # 4) ATUALIZAR REFERÊNCIAS DO JOGADOR (CRÍTICO)
            #    SEMPRE usar o estado mais recente do Firestore
            # ---------------------------------------------------------
            estado_jogo["eh_player1"] = eh_player1

            meu = jogador_1 if eh_player1 else jogador_2
            oponente = jogador_2 if eh_player1 else jogador_1

            estado_jogo["meu"] = meu
            estado_jogo["meu_caminho"] = "player1" if eh_player1 else "player2"

            turno_atual = data.get("turn", "") or ""
            estado_jogo["turno"] = turno_atual

            # ---------------------------------------------------------
            # 5) FAILSAFE DE TURNO (se algo ficar sem "player1"/"player2")
            # ---------------------------------------------------------
            if turno_atual not in ("player1", "player2"):
                novo_turno = "player1" if p1_id else "player2"
                try:
                    sala_ref.update({"turn": novo_turno})
                    estado_jogo["turno"] = novo_turno
                    turno_atual = novo_turno
                except Exception as e:
                    print(f"⚠️ Erro ao corrigir turno: {e}")

            # ---------------------------------------------------------
            # 6) STORAGE LOCAL
            # ---------------------------------------------------------
            try:
                page.client_storage.set("meu_caminho", estado_jogo["meu_caminho"])
                page.client_storage.set("eh_player1", eh_player1)
            except Exception:
                pass

            # ---------------------------------------------------------
            # 7) RESET UI QUANDO O DECK É CRIADO
            # ---------------------------------------------------------
            if (
                    data.get("game_status") == "started"
                    and "deck" in data
                    and not estado_jogo.get("resetei_para_nova_mao", False)
            ):
                print("🔄 Reset completo da UI para nova mão (gatilho: deck recriado).")
                estado_jogo["ja_exibiu_dialogo_extensao"] = False
                estado_jogo["ja_exibiu_placar"] = False
                estado_jogo["resetei_para_nova_mao"] = True

            if data.get("game_status") == "finished":
                estado_jogo["resetei_para_nova_mao"] = False

            # ---------------------------------------------------------
            # 8) SE O DECK SUMIU → CRIA NOVO
            # ---------------------------------------------------------
            if ("deck" not in data or not data["deck"]) and not data["baralho"]:
                print("🔄 Reset completo da UI para nova mão (deck removido ou vazio).")
                if p1_id and p2_id:
                    distribuir_cartas_internamente()
                return

            # ---------------------------------------------------------
            # 9) EXTENSÃO (mostrar diálogo quando EU estou aguardando)
            # ---------------------------------------------------------
            if (
                    meu.get("aguardando_extensao", False)
                    and not estado_jogo.get("ja_exibiu_dialogo_extensao", False)
            ):
                print("⏳ Extensão pendente — exibindo diálogo.")
                estado_jogo["ja_exibiu_dialogo_extensao"] = True
                mostrar_extensao_dialogo()

            # ---------------------------------------------------------
            # 10) CÁLCULO DE is_my_turn
            # ---------------------------------------------------------
            mao_atual = meu.get("hand", []) or []
            tem_cartas = len(mao_atual) > 0

            turno_meu = (
                    (eh_player1 and turno_atual == "player1") or
                    (not eh_player1 and turno_atual == "player2")
            )

            is_my_turn = turno_meu and tem_cartas

            # Se eu estou com diálogo de extensão aberto,
            # continuo “com a vez”, mas não deixo clicar outra carta.
            if meu.get("aguardando_extensao", False):
                is_my_turn = True

            # ---------------------------------------------------------
            # 11) ATUALIZAÇÕES DE UI (SEGURO)
            # ---------------------------------------------------------
            deck = data.get("deck", [])  # garante que deck existe

            # Nome do oponente
            if nome_oponente is not None and getattr(nome_oponente, "current", None):
                nome_oponente.current.value = oponente.get("nome", "Oponente")

            if progression_bars_area:
                progression_bars_area.atualizar_nomes(oponente.get("nome", "Oponente"))

            if area_oponente:
                area_oponente.update_nome_jogador(oponente.get("nome", "Oponente"))

            # Label “Cartas no deck”
            if nome_local is not None and getattr(nome_local, "current", None):
                nome_local.current.value = f"🃏 Cartas no deck: {len(deck)}"

            # Área do jogador local
            if area_jogador_local:
                area_jogador_local.atualizar_ui(
                    meu,
                    is_my_turn,
                    len(deck),
                    tentar_jogar_carta,
                )

            # Área do oponente
            if area_oponente:
                area_oponente.atualizar_ui(oponente)

            # 🔆 Semáforos — baseados SOMENTE no status + limite 50km
            if area_jogador_local:
                atualizar_semaforo(area_jogador_local, meu)
            if area_oponente:
                atualizar_semaforo(area_oponente, oponente)

            # Barras de progresso
            if callable(atualizar_barras):
                atualizar_barras(meu.get("distance", 0), oponente.get("distance", 0))

            # ---------------------------------------------------------
            # 12) PLACAR FINAL
            # ---------------------------------------------------------
            if (
                    data.get("game_status") == "finished"
                    and not jogador_1.get("aguardando_extensao", False)
                    and not jogador_2.get("aguardando_extensao", False)
            ):
                if not data.get("placar_calculado", False):
                    try:
                        # print("🧮 Calculando placar final...")

                        deck_local = data.get("deck", [])
                        mao1 = jogador_1.get("hand", []) or []
                        mao2 = jogador_2.get("hand", []) or []
                        fim_de_baralho = (not deck_local) and (len(mao1) == 0) and (len(mao2) == 0)

                        if fim_de_baralho:
                            # 🔥 Caso especial: fim de baralho
                            finalizar_mao_por_fim_de_baralho(sala_ref)
                        else:
                            # 🛣 Caso normal: 700 / 1000 / recusa de extensão
                            calcular_e_enviar_placar_final(sala_ref, estado_jogo, reescrever_placar=False)

                        sala_ref.update({"placar_calculado": True})
                        # print("✅ Placar calculado e salvo no Firestore.")
                        page.go("/placar")
                        return
                    except Exception as e:
                        print(f"⚠️ Erro ao calcular placar final: {e}")
                        return

                if not estado_jogo.get("ja_exibiu_placar", False):
                    estado_jogo["ja_exibiu_placar"] = True

                    def delayed():
                        import time
                        time.sleep(1)
                        try:
                            # print("➡️ Indo para o placar...")
                            page.go("/placar")
                        except Exception as e:
                            print(f"⚠️ Erro ao redirecionar: {e}")

                    import threading
                    threading.Thread(target=delayed, daemon=True).start()

            # ---------------------------------------------------------
            # 13) UPDATE FINAL
            # ---------------------------------------------------------
            try:
                page.update()
            except Exception:
                pass

    sala_ref.on_snapshot(on_snapshot)

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

    # 3. CHAME O MANIPULADOR MANUALMENTE UMA VEZ para aplicar a lógica
    # na inicialização, garantindo que a visibilidade seja ajustada
    # antes da renderização final. Isso garante a correção visual.
    _handle_resize(None)

    # 4. Retorna a view configurada
    return view


def calcular_e_enviar_placar_final(sala_ref, estado_jogo, reescrever_placar: bool = False):
    snapshot = sala_ref.get()
    sala_data = snapshot.to_dict() or {}

    meu_caminho = estado_jogo["meu_caminho"]
    oponente_caminho = "player2" if meu_caminho == "player1" else "player1"

    meu = sala_data.get(meu_caminho, {}) or {}
    op = sala_data.get(oponente_caminho, {}) or {}

    # Evita duplicatas, exceto quando queremos reescrever (fim de baralho)
    if meu.get("placar_registrado", False) and not reescrever_placar:
        # print("⚠️ Placar já foi registrado para este jogador. Ignorando duplicata.")
        return

    deck_vazio = not sala_data.get("deck")

    # ===============================
    # 🔢 Coleta de dados brutos
    # ===============================
    dist = meu.get("distance", 0)
    dist_op = op.get("distance", 0)

    ext = meu.get("extensao", False)
    ext_op = op.get("extensao", False)

    saf = meu.get("safeties", [])
    saf_op = op.get("safeties", [])

    resp = meu.get("safety_responses", 0)
    resp_op = op.get("safety_responses", 0)

    # ==========================================================
    # 🎯 1) Limite efetivo final da mão (700 ou 1000)
    # ==========================================================
    limite_efetivo = 1000 if ext or ext_op else 700

    # ==========================================================
    # 🎯 2) Verifica quem atingiu o limite final
    # ==========================================================
    atingiu_meu = (dist == limite_efetivo)
    atingiu_op = (dist_op == limite_efetivo)

    # ==========================================================
    # 🎯 3) Vencedor da mão
    # ==========================================================
    vencedor_meu = atingiu_meu and dist >= dist_op
    vencedor_op = atingiu_op and dist_op >= dist

    # ==========================================================
    # 🎯 4) Bônus percurso completo
    # ==========================================================
    bonus_pc_meu = 0
    bonus_pc_op = 0

    if vencedor_meu:
        bonus_pc_meu = 300 if limite_efetivo == 1000 else 200

    if vencedor_op:
        bonus_pc_op = 300 if limite_efetivo == 1000 else 200

    # ==========================================================
    # 🎯 5) Bônus fim do baralho (campo sempre presente!)
    # ==========================================================
    bonus_fb_meu = 0
    bonus_fb_op = 0

    if deck_vazio:
        if atingiu_meu:
            bonus_fb_meu = 500 if limite_efetivo == 700 else 400
        if atingiu_op:
            bonus_fb_op = 500 if limite_efetivo == 700 else 400

    # ==========================================================
    # 🎯 6) Placar MEU — SEMPRE COMPLETO!
    # ==========================================================
    placar_meu = {
        "distancia": dist,
        "segurancas": len(saf) * 100,
        "todas_segurancas": 400 if len(saf) == 4 else 0,
        "seguranca_em_resposta": resp * 300,
        "percurso_completo": bonus_pc_meu,
        "com_200": (
            300 if meu.get("com_200") == "N" and dist == 1000 else
            200 if meu.get("com_200") == "N" and dist == 700 else
            0
        ),
        "oponente_zero": (
            500 if dist == 1000 and dist_op == 0 else
            300 if dist == 700 and dist_op == 0 else
            0
        ),
        "bonus_extensao": 300 if ext else 0,
        "fim_do_baralho": bonus_fb_meu,  # <-- SEMPRE EXISTE
    }

    placar_meu["total_da_mao"] = sum(placar_meu.values())

    # ==========================================================
    # 🎯 7) Placar OPONENTE — SEMPRE COMPLETO!
    # ==========================================================
    placar_op = {
        "distancia": dist_op,
        "segurancas": len(saf_op) * 100,
        "todas_segurancas": 400 if len(saf_op) == 4 else 0,
        "seguranca_em_resposta": resp_op * 300,
        "percurso_completo": bonus_pc_op,
        "com_200": (
            300 if op.get("com_200") == "N" and dist_op == 1000 else
            200 if op.get("com_200") == "N" and dist_op == 700 else
            0
        ),
        "oponente_zero": (
            500 if dist_op == 1000 and dist == 0 else
            300 if dist_op == 700 and dist == 0 else
            0
        ),
        "bonus_extensao": 300 if ext_op else 0,
        "fim_do_baralho": bonus_fb_op,  # <-- SEMPRE EXISTE
    }

    placar_op["total_da_mao"] = sum(placar_op.values())

    # ==========================================================
    # 🎯 8) Total geral acumulado
    #     (se reescrever_placar=True, desconta a última mão antiga)
    # ==========================================================
    placar_anterior_meu = meu.get("placar", {}).get("atual_mao", {}) or {}
    placar_anterior_op = op.get("placar", {}).get("atual_mao", {}) or {}

    total_mao_anterior_meu = placar_anterior_meu.get("total_da_mao", 0)
    total_mao_anterior_op = placar_anterior_op.get("total_da_mao", 0)

    total_geral_atual_meu = meu.get("placar", {}).get("total_geral", 0)
    total_geral_atual_op = op.get("placar", {}).get("total_geral", 0)

    if reescrever_placar:
        base_meu = max(0, total_geral_atual_meu - total_mao_anterior_meu)
        base_op = max(0, total_geral_atual_op - total_mao_anterior_op)
    else:
        base_meu = total_geral_atual_meu
        base_op = total_geral_atual_op

    total_meu = base_meu + placar_meu["total_da_mao"]
    total_op = base_op + placar_op["total_da_mao"]

    # ==========================================================
    # 🎯 9) Atualiza Firestore
    # ==========================================================
    sala_ref.update({
        f"{meu_caminho}.placar.atual_mao": placar_meu,
        f"{meu_caminho}.placar.total_geral": total_meu,
        f"{meu_caminho}.placar_registrado": True,
        f"{meu_caminho}.placar_visto": True,

        f"{oponente_caminho}.placar.atual_mao": placar_op,
        f"{oponente_caminho}.placar.total_geral": total_op,
        f"{oponente_caminho}.placar_registrado": True,
    })


def finalizar_mao_por_fim_de_baralho(sala_ref):
    """
    Finaliza a mão quando o baralho acaba e ambos jogadores estão sem cartas,
    recalculando o placar usando a mesma lógica de 700/1000km,
    mas permitindo reescrever a última mão (caso outro fluxo já tenha gravado algo).
    """
    snapshot = sala_ref.get()
    sala_data = snapshot.to_dict() or {}

    player1 = sala_data.get("player1", {}) or {}
    player2 = sala_data.get("player2", {}) or {}
    deck = sala_data.get("deck", [])

    mao1 = player1.get("hand", []) or []
    mao2 = player2.get("hand", []) or []

    # Garante que é fim de baralho + mãos vazias
    if deck or mao1 or mao2:
        return

    # print("🛑 Fim de baralho detectado — finalizando mão por falta de cartas.")

    dist1 = player1.get("distance", 0)
    dist2 = player2.get("distance", 0)

    if dist1 > dist2:
        vencedor = "player1"
        perdedor = "player2"
    elif dist2 > dist1:
        vencedor = "player2"
        perdedor = "player1"
    else:
        vencedor = None
        perdedor = None

    updates = {}

    if vencedor:
        updates[f"{vencedor}.winner"] = True
        updates[f"{vencedor}.finalizar"] = True
        updates[f"{perdedor}.winner"] = False
        updates[f"{perdedor}.finalizar"] = False
    else:
        # Empate: ninguém vence, mas ambos finalizam a mão
        updates["player1.winner"] = False
        updates["player2.winner"] = False
        updates["player1.finalizar"] = True
        updates["player2.finalizar"] = True

    sala_ref.update(updates)

    if vencedor:
        estado_jogo = {"meu_caminho": vencedor}
    else:
        estado_jogo = {"meu_caminho": "player1"}

    # Recalcula o placar reescrevendo a mão anterior (se houver)
    calcular_e_enviar_placar_final(sala_ref, estado_jogo, reescrever_placar=True)


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
            print(f"⚠️ Erro ao fechar diálogo anterior: {e}")

    page.dialog = novo_dialogo
    novo_dialogo.open = True

    try:
        page.update()
        await asyncio.sleep(0.05)
        # print("✅ Diálogo aberto com sucesso:", getattr(novo_dialogo.title, "value", "Sem título"))
    except Exception as e:
        pass
        print(f"❌ Falha ao abrir diálogo: {e}")


async def fechar_dialogo_com_segurança(page):
    if getattr(page, "dialog", None):
        try:
            page.dialog.open = False
            page.update()
            await asyncio.sleep(0.05)
            page.dialog = None
        except Exception as e:
            pass
            print(f"⚠️ Erro ao fechar diálogo: {e}")
