# jogo

import os
import json
import flet as ft
from player_area_component import AreaDeJogoDoJogador
from progression_area_component import AreaDeProgressoComparativo  # Importação da nova classe
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
        color=ft.Colors.RED_500,
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

    # O bloco de código original de `progression_bars_area = ft.Column(...)` foi substituído acima

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
        """
        Jogador escolheu NÃO estender para 1000 km.
        Marca a mão como finalizada e dispara o cálculo do placar.
        """
        try:
            # 1) Garante que sabemos se somos player1 ou player2
            meu_caminho = estado_jogo.get("meu_caminho")
            if not meu_caminho:
                # Fallback seguro: lê direto do Firestore
                snap = sala_ref.get().to_dict() or {}
                p1 = snap.get("player1", {})
                p2 = snap.get("player2", {})

                if p1.get("id") == jogador_id:
                    meu_caminho = "player1"
                elif p2.get("id") == jogador_id:
                    meu_caminho = "player2"
                else:
                    print("⚠️ recusar_extensao: não consegui determinar o caminho do jogador.")
                    return  # sem isso não dá pra atualizar corretamente

                estado_jogo["meu_caminho"] = meu_caminho

            # 2) Atualiza o Firestore marcando fim da mão
            updates = {
                f"{meu_caminho}.aguardando_extensao": False,
                f"{meu_caminho}.finalizar": True,
                "game_status": "finished",
            }

            sala_ref.update(updates)

            # Evita mostrar o diálogo de novo nessa mesma mão
            estado_jogo["ja_exibiu_dialogo_extensao"] = True

            # 3) Fecha o diálogo e vai para o placar
            async def fechar_dialogo_e_redirecionar():
                # Fecha o diálogo se ainda estiver aberto
                if hasattr(page, "dialog") and page.dialog:
                    page.dialog.open = False
                    page.update()
                    await asyncio.sleep(0.2)
                    page.dialog = None
                    page.update()

                # Remove event handler de teclado, se você estiver usando
                page.on_keyboard_event = None

                # Calcula/atualiza o placar com segurança
                try:
                    calcular_e_enviar_placar_final(sala_ref, estado_jogo)
                except Exception as exc:
                    print(f"⚠️ Erro ao calcular placar em recusar_extensao: {exc}")

                estado_jogo["ja_exibiu_placar"] = True

                # Dá um pequeno tempo pro Firestore sincronizar
                await asyncio.sleep(1.2)
                try:
                    page.go("/placar")
                except Exception as exc:
                    print(f"⚠️ Erro ao redirecionar para /placar em recusar_extensao: {exc}")

            # Flet executa essa coroutine em background
            page.run_task(fechar_dialogo_e_redirecionar)

        except Exception as exc:
            # Qualquer erro que impeça o update vai aparecer no console
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

            # 🧩 Ignora se o bloqueio estiver ativo (ex: recusar extensão)
            if estado_jogo.get("bloquear_atualizacoes", False):
                return

            jogador_1 = data.get("player1", {})
            jogador_2 = data.get("player2", {})

            p1_id = jogador_1.get("id")
            p2_id = jogador_2.get("id")

            # 🧭 Redefine caminho automaticamente (robusto)
            if not estado_jogo.get("meu_caminho") or estado_jogo["meu_caminho"] not in ("player1", "player2"):
                if jogador_id == p1_id:
                    estado_jogo["meu_caminho"] = "player1"
                elif jogador_id == p2_id:
                    estado_jogo["meu_caminho"] = "player2"
                else:
                    estado_jogo["meu_caminho"] = None

            # 🧹 RESET DE ESTADO LOCAL QUANDO UMA NOVA MÃO COMEÇA
            if (
                    data.get("game_status") == "started"
                    and jogador_1.get("distance", 0) == 0
                    and jogador_2.get("distance", 0) == 0
                    and not jogador_1.get("aguardando_extensao", False)
                    and not jogador_2.get("aguardando_extensao", False)
                    and not jogador_1.get("finalizar", False)
                    and not jogador_2.get("finalizar", False)
            ):
                estado_jogo["ja_exibiu_dialogo_extensao"] = False
                estado_jogo["ja_exibiu_placar"] = False

                # 🧭 CORREÇÃO FINAL: reseta placar_calculado apenas em nova mão real
                if "placar_calculado" not in data:
                    sala_ref.update({"placar_calculado": False})
                elif data.get("placar_calculado") is True:
                    try:
                        sala_ref.update({"placar_calculado": False})
                        # print("🔄 Reset automático de placar_calculado para nova mão.")
                    except Exception as e:
                        # print(f"⚠️ Falha ao resetar placar_calculado: {e}")
                        pass

            # ✅ Auto-registro se jogador não estiver na sala
            if jogador_id != p1_id and jogador_id != p2_id:
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

            # ✅ Identifica o jogador
            eh_player1 = p1_id == jogador_id
            estado_jogo["eh_player1"] = eh_player1
            turno_atual = data.get("turn", "")
            estado_jogo["turno"] = turno_atual
            estado_jogo["meu"] = jogador_1 if eh_player1 else jogador_2
            estado_jogo["meu_caminho"] = "player1" if eh_player1 else "player2"

            # 🚨 FAILSAFE DE TURNO
            if turno_atual not in ("player1", "player2"):
                novo_turno = "player1" if p1_id else "player2"
                try:
                    sala_ref.update({"turn": novo_turno})
                    turno_atual = novo_turno
                    estado_jogo["turno"] = novo_turno
                except Exception:
                    pass

            # ✅ Armazena no client_storage
            try:
                page.client_storage.set("meu_caminho", estado_jogo["meu_caminho"])
                page.client_storage.set("eh_player1", eh_player1)
            except Exception:
                pass

            meu = estado_jogo["meu"]
            oponente = jogador_2 if eh_player1 else jogador_1

            # ✅ Criação automática do deck
            if "deck" not in data:
                if p1_id and p2_id:
                    distribuir_cartas_internamente()
                return

            # ✅ Verifica se precisa mostrar extensão
            if (
                    meu.get("distance", 0) == 700
                    and meu.get("aguardando_extensao", False)
                    and not estado_jogo.get("ja_exibiu_dialogo_extensao", False)
            ):
                estado_jogo["ja_exibiu_dialogo_extensao"] = True
                mostrar_extensao_dialogo()

            # 🎨 --- Atualização de UI com Componentes Refatorados ---

            meu_data = jogador_1 if eh_player1 else jogador_2
            oponente_data = jogador_2 if eh_player1 else jogador_1
            deck = data.get("deck", [])

            is_my_turn = (
                    (eh_player1 and turno_atual == "player1") or
                    (not eh_player1 and turno_atual == "player2")
            )

            # 1. Atualização do Nome do Oponente
            if nome_oponente.current is not None:
                nome_oponente.current.value = oponente_data.get("nome", "Oponente")

            # Atualiza o nome do oponente na área da barra de progresso (agora gerenciada pelo componente)
            progression_bars_area.atualizar_nomes(oponente_data.get("nome", "Oponente"))

            # 2. Atualização da Contagem de Cartas no Deck
            nome_local.current.value = f"🃏 Cartas no deck: {len(deck)}"

            # 3. Atualiza a UI do **Jogador Local** (Mão, Distância, Status, etc.)
            area_jogador_local.atualizar_ui(
                meu_data,
                is_my_turn,
                len(deck),
                tentar_jogar_carta  # Passa o callback para os botões da mão
            )

            # 4. Atualiza a UI do **Oponente** (Distância, Status, Segurança, etc.)
            area_oponente.atualizar_ui(
                oponente_data
            )

            # 5. Atualiza a barra de progresso (Função auxiliar que usa as refs globais do Flet)
            atualizar_barras(meu_data.get("distance", 0), oponente_data.get("distance", 0))

            # 6. Atualiza o semáforo de turno (Acessando as Refs dentro dos novos componentes)
            if is_my_turn:
                area_jogador_local.traffic_light.current.src = "images/green_light.png"
                area_oponente.traffic_light.current.src = "images/red_light.png"
            else:
                area_jogador_local.traffic_light.current.src = "images/red_light.png"
                area_oponente.traffic_light.current.src = "images/green_light.png"

            # 7. CORREÇÃO: força finalização se alguém recusou extensão
            try:
                for key in ["player1", "player2"]:
                    jogador = data.get(key, {})
                    if jogador.get("aguardando_extensao") and not jogador.get("extensao"):
                        # print(f"🏁 {jogador.get('nome', key)} recusou a extensão. Encerrando partida.")
                        sala_ref.update({
                            "game_status": "finished",
                            f"{key}.aguardando_extensao": False,
                            f"{key}.finalizar": True,
                        })
            except Exception as e:
                # print(f"⚠️ Erro ao verificar recusa de extensão: {e}")
                pass

            # 8. Finaliza jogo e abre placar
            if data.get("game_status") == "finished" and not estado_jogo.get("ja_exibiu_placar", False):
                snapshot_atual = sala_ref.get().to_dict()
                if not snapshot_atual.get("placar_calculado"):
                    import time
                    time.sleep(0.8)
                    calcular_e_enviar_placar_final(sala_ref, estado_jogo)
                    sala_ref.update({"placar_calculado": True})

                estado_jogo["ja_exibiu_placar"] = True

                def delayed_redirect():
                    import time
                    time.sleep(1.5)
                    try:
                        page.go("/placar")
                    except Exception:
                        pass

                import threading
                threading.Thread(target=delayed_redirect).start()

            # 9. Atualiza página de forma segura
            try:
                if hasattr(page, "update") and callable(page.update):
                    page.update()
            except Exception:
                pass

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

    # 3. CHAME O MANIPULADOR MANUALMENTE UMA VEZ para aplicar a lógica
    # na inicialização, garantindo que a visibilidade seja ajustada
    # antes da renderização final. Isso garante a correção visual.
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
        # 👇 Jogador local
        f"{meu_caminho}.placar.atual_mao": placar_mao,
        f"{meu_caminho}.placar.total_geral": novo_total_meu,
        f"{meu_caminho}.placar_registrado": True,
        f"{meu_caminho}.placar_visto": True,  # ✅ Marca que o jogador viu o placar

        # 👇 Oponente – também recebe a mão e é marcado como já registrado
        f"{oponente_caminho}.placar.atual_mao": placar_oponente,
        f"{oponente_caminho}.placar.total_geral": novo_total_oponente,
        f"{oponente_caminho}.placar_registrado": True,
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