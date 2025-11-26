import flet as ft
from firebase_admin import firestore
import flet_audio as fta
from firebase_helpers import obter_nome_jogador, resetar_mao  # importar resetar_mao
import asyncio
from anim_manager import AnimationManager
from encerrar_view_atual import encerrar_view_atual  # Assuming this is correctly imported
from pages.jogo import create_deck, distribuir_cartas


def placar_view(page: ft.Page):
    # print("Placar View")
    # 🧼 Força a limpeza de diálogos antigos (fallback defensivo)
    if hasattr(page, "dialog"):
        page.dialog = None

    page.scroll = ft.ScrollMode.AUTO
    page.bgcolor = ft.LinearGradient(
        colors=[ft.Colors.GREY_300, ft.Colors.GREY_100],
        begin=ft.alignment.top_center,
        end=ft.alignment.bottom_center,
    )
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.vertical_alignment = ft.MainAxisAlignment.CENTER

    anim_manager = AnimationManager()
    audio_vitoria = fta.Audio(src="sounds/victory.mp3", autoplay=False, volume=1.0)
    page.overlay.append(audio_vitoria)

    nome_jogador = page.client_storage.get("nome_jogador")
    codigo_sala = page.client_storage.get("sala_jogador")

    # Garantir que jogador está corretamente identificado como player1 ou player2
    jogador_id = page.client_storage.get("jogador_id")
    codigo_sala = page.client_storage.get("sala_jogador")
    sala_ref = firestore.client().collection("salas").document(codigo_sala)
    dados = sala_ref.get().to_dict()

    if not dados:
        return ft.View(
            route="/placar",
            controls=[
                ft.Text("Erro: Sala não encontrada. Por favor, volte ao início.", size=20),
                ft.ElevatedButton("Voltar ao Início", on_click=lambda e: page.go("/")),
            ],
            scroll=ft.ScrollMode.AUTO
        )

    player1_id = dados.get("player1", {}).get("id")
    player2_id = dados.get("player2", {}).get("id")

    # Determinar corretamente quem é o jogador local
    eh_player1 = jogador_id == player1_id

    meu_path = "player1" if eh_player1 else "player2"
    oponente_path = "player2" if eh_player1 else "player1"

    jogador_venceu_ref = ft.Ref[ft.Text]()
    jogador_total_ref = ft.Ref[ft.Text]()
    computador_venceu_ref = ft.Ref[ft.Text]()
    computador_total_ref = ft.Ref[ft.Text]()

    meu = dados.get(meu_path, {})
    oponente = dados.get(oponente_path, {})

    placar_meu = meu.get("placar", {}).get("atual_mao", {})
    placar_oponente = oponente.get("placar", {}).get("atual_mao", {})

    geral_j = meu.get("placar", {}).get("total_geral", 0)
    geral_c = oponente.get("placar", {}).get("total_geral", 0)

    def get_val(p, key):
        return p.get(key, 0)

    # ✅ Fim da partida só se alguém passou de 5000 e não for empate
    fim_de_jogo = (geral_j >= 5000 or geral_c >= 5000) and (geral_j != geral_c)

    header_style = ft.TextStyle(size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
    line_style = ft.TextStyle(size=16, color=ft.Colors.BLACK, weight=ft.FontWeight.W_500)

    novo_total_j = geral_j
    jogador_total = ft.Text(
        str(novo_total_j),
        style=line_style,
        ref=jogador_total_ref,
        text_align=ft.TextAlign.CENTER,
        animate_scale=ft.Animation(500, ft.AnimationCurve.EASE_OUT),
        animate_opacity=ft.Animation(500, ft.AnimationCurve.EASE_OUT)
    )
    novo_total_c = geral_c
    computador_total = ft.Text(
        str(novo_total_c),
        style=line_style,
        ref=computador_total_ref,
        text_align=ft.TextAlign.CENTER,
        animate_scale=ft.Animation(500, ft.AnimationCurve.EASE_OUT),
        animate_opacity=ft.Animation(500, ft.AnimationCurve.EASE_OUT)
    )

    jogador_venceu = ft.Text(
        nome_jogador,
        style=header_style,
        ref=jogador_venceu_ref,
        text_align=ft.TextAlign.CENTER,
        animate_scale=ft.Animation(500, ft.AnimationCurve.EASE_OUT),
        animate_opacity=ft.Animation(500, ft.AnimationCurve.EASE_OUT)
    )
    computador_venceu = ft.Text(
        oponente.get("nome", "Oponente"),
        style=header_style,
        ref=computador_venceu_ref,
        text_align=ft.TextAlign.CENTER,
        animate_scale=ft.Animation(500, ft.AnimationCurve.EASE_OUT),
        animate_opacity=ft.Animation(500, ft.AnimationCurve.EASE_OUT)
    )

    # Determine o vencedor para a animação
    vencedor_nome_ref = jogador_venceu_ref
    vencedor_total_ref = jogador_total_ref
    perdedor_nome_ref = computador_venceu_ref
    perdedor_total_ref = computador_total_ref

    if geral_c > geral_j:
        vencedor_nome_ref = computador_venceu_ref
        vencedor_total_ref = computador_total_ref
        perdedor_nome_ref = jogador_venceu_ref
        perdedor_total_ref = jogador_total_ref

    # ✅ Define se o jogador local é o vencedor
    is_local_vencedor = (geral_j > geral_c and eh_player1) or (geral_c > geral_j and not eh_player1)

    def celula(conteudo, fundo, bordas, col):
        return ft.Container(
            content=conteudo,
            bgcolor=fundo,
            border=bordas,
            col=col,
            padding=0
        )

    def linha(label, val_j, val_c, index):
        is_total_geral = label.strip().lower() == "total geral"
        fundo = ft.Colors.BLUE_100 if is_total_geral else ft.Colors.GREY_100 if index % 2 == 0 else None

        return ft.ResponsiveRow(
            controls=[
                celula(
                    ft.Text(label, style=line_style, text_align=ft.TextAlign.CENTER),
                    fundo,
                    ft.border.only(
                        left=ft.BorderSide(1, ft.Colors.BLACK),
                        top=ft.BorderSide(1, ft.Colors.BLACK),
                        bottom=ft.BorderSide(1, ft.Colors.BLACK)
                    ),
                    {"xs": 12, "md": 6}
                ),
                celula(
                    val_j if isinstance(val_j, ft.Text) else ft.Text(str(val_j), style=line_style,
                                                                     text_align=ft.TextAlign.CENTER),
                    fundo,
                    ft.border.only(
                        top=ft.BorderSide(1, ft.Colors.BLACK),
                        bottom=ft.BorderSide(1, ft.Colors.BLACK)
                    ),
                    {"xs": 6, "md": 3}
                ),
                celula(
                    val_c if isinstance(val_c, ft.Text) else ft.Text(str(val_c), style=line_style,
                                                                     text_align=ft.TextAlign.CENTER),
                    fundo,
                    ft.border.only(
                        right=ft.BorderSide(1, ft.Colors.BLACK),
                        top=ft.BorderSide(1, ft.Colors.BLACK),
                        bottom=ft.BorderSide(1, ft.Colors.BLACK)
                    ),
                    {"xs": 6, "md": 3}
                ),
            ],
            spacing=0
        )

    # 🔢 Lê diretamente os valores calculados no Firestore (sem recalcular lógica)
    dist_j = get_val(placar_meu, "distancia")
    seg_j = get_val(placar_meu, "segurancas")
    seg4_j = get_val(placar_meu, "todas_segurancas")
    seg_resp_j = get_val(placar_meu, "seguranca_em_resposta")
    perc_comp_j = get_val(placar_meu, "percurso_completo")
    # com_200 já é um bônus numérico calculado pelo backend
    s200_j = get_val(placar_meu, "com_200")
    adv0_j = get_val(placar_meu, "oponente_zero")
    exts_j = get_val(placar_meu, "bonus_extensao")
    fim_cart_j = get_val(placar_meu, "fim_do_baralho")
    tot_mao_j = get_val(placar_meu, "total_da_mao")

    dist_c = get_val(placar_oponente, "distancia")
    seg_c = get_val(placar_oponente, "segurancas")
    seg4_c = get_val(placar_oponente, "todas_segurancas")
    seg_resp_c = get_val(placar_oponente, "seguranca_em_resposta")
    perc_comp_c = get_val(placar_oponente, "percurso_completo")
    s200_c = get_val(placar_oponente, "com_200")
    adv0_c = get_val(placar_oponente, "oponente_zero")
    exts_c = get_val(placar_oponente, "bonus_extensao")
    fim_cart_c = get_val(placar_oponente, "fim_do_baralho")
    tot_mao_c = get_val(placar_oponente, "total_da_mao")

    # Define o texto do botão com base na condição de fim de jogo
    texto_botao = "Novo jogo" if fim_de_jogo else "Nova mão"

    async def limpar_dados_pos_placar():
        # print("limpar_dados_placar")
        updates = {}

        # 🧹 Limpeza da mão atual (placar da mão anterior some, mas total_geral permanece)
        updates[f"{meu_path}.placar.atual_mao"] = firestore.DELETE_FIELD
        updates[f"{oponente_path}.placar.atual_mao"] = firestore.DELETE_FIELD
        updates[f"{meu_path}.placar_registrado"] = False
        updates[f"{oponente_path}.placar_registrado"] = False
        updates[f"{meu_path}.placar_visto"] = False
        updates[f"{oponente_path}.placar_visto"] = False

        # Se o jogo terminou (alguém chegou a 5000+), zera o total geral para um NOVO JOGO
        if fim_de_jogo:
            updates[f"{meu_path}.placar.total_geral"] = 0
            updates[f"{oponente_path}.placar.total_geral"] = 0

        # 🔄 Reset completo de estado de mesa para NOVA MÃO na mesma sala
        for path in [meu_path, oponente_path]:
            updates.update({
                f"{path}.distance": 0,  # <-- VOLTA PRA 0 Km
                f"{path}.status": "Luz Vermelha",  # <-- Recomeça parado
                f"{path}.limite": False,
                f"{path}.last_card_played": "Nenhuma",
                f"{path}.safeties": [],
                f"{path}.hand": [],
                f"{path}.extensao": False,
                f"{path}.aguardando_extensao": False,
                f"{path}.finalizar": False,
                f"{path}.com_200": "N",
                f"{path}.safety_responses": 0,  # <-- zera coup fourré da mão
            })

        # 🔁 Primeiro remove o deck sozinho
        sala_ref.update({"deck": firestore.DELETE_FIELD})

        # 🔁 Gatilhos de nova mão
        updates["deck"] = firestore.DELETE_FIELD  # força o jogo.py a criar novo baralho e redistribuir
        updates["game_status"] = "started"  # <-- o jogo.py procura exatamente isso
        updates["turn"] = "player1"
        updates["placar_calculado"] = False  # garante que a próxima mão volte a calcular normalmente
        updates["extensao_ativa"] = False
        updates["baralho"] = False

        # print("atualiza firestore")
        sala_ref.update(updates)

    async def voltar_jogo(e):
        try:
            if fim_de_jogo:
                # 1. Encerra som e animações antes de sair
                for item in page.overlay:
                    if isinstance(item, fta.Audio) and item.src.endswith("victory.mp3"):
                        item.pause()
                anim_manager.stop_animation()
                anim_manager.clear_animations()  # Limpa as animações registradas

                # 2. Encerra a view de forma segura
                encerrar_view_atual(page, anim_manager)

                # Reset da flag de animação de fim de jogo
                page.session.set("animacao_placar_executada", False)

            # 3. Limpa dados e prepara nova mão / novo jogo
            await limpar_dados_pos_placar()

            # 4. Pequeno delay extra de segurança (opcional)
            await asyncio.sleep(0.1)

            # 5. Agora sim, ir para o jogo
            page.go("/jogo")

        except Exception as err:
            print("Erro em voltar_jogo:", err)

    # Botão de jogar (Nova mão / Novo jogo)
    botao_jogar = ft.ElevatedButton(
        text=texto_botao,
        on_click=voltar_jogo,
        style=ft.ButtonStyle(padding=20)
    )

    custom_table = ft.Container(
        content=ft.Column([
            ft.ResponsiveRow(
                controls=[
                    celula(
                        ft.Text("Critério", style=header_style, text_align=ft.TextAlign.CENTER),
                        ft.Colors.BLUE,
                        ft.border.only(
                            left=ft.BorderSide(1, ft.Colors.BLACK),
                            top=ft.BorderSide(1, ft.Colors.BLACK),
                            bottom=ft.BorderSide(1, ft.Colors.BLACK)
                        ),
                        {"xs": 12, "md": 6}
                    ),
                    celula(
                        jogador_venceu,
                        ft.Colors.BLUE,
                        ft.border.only(
                            top=ft.BorderSide(1, ft.Colors.BLACK),
                            bottom=ft.BorderSide(1, ft.Colors.BLACK)
                        ),
                        {"xs": 6, "md": 3}
                    ),
                    celula(
                        computador_venceu,
                        ft.Colors.BLUE,
                        ft.border.only(
                            right=ft.BorderSide(1, ft.Colors.BLACK),
                            top=ft.BorderSide(1, ft.Colors.BLACK),
                            bottom=ft.BorderSide(1, ft.Colors.BLACK)
                        ),
                        {"xs": 6, "md": 3}
                    ),
                ],
                spacing=0
            ),
            linha("Pontos correspondentes à distância", dist_j, dist_c, 0),
            linha("Pontos por segurança jogada", seg_j, seg_c, 1),
            linha("Todas as quatro seguranças jogadas", seg4_j, seg4_c, 2),
            linha("Segurança jogada em resposta", seg_resp_j, seg_resp_c, 3),
            linha("Percurso completado", perc_comp_j, perc_comp_c, 4),
            linha("Percurso completado sem usar 200Km", s200_j, s200_c, 5),
            linha("Adversário não saiu do zero", adv0_j, adv0_c, 6),
            linha("Pontos por pedir a extensão", exts_j, exts_c, 7),
            linha("Percurso completado após final das cartas", fim_cart_j, fim_cart_c, 8),
            linha("Total da Mão", tot_mao_j, tot_mao_c, 9),
            linha("Total Geral", jogador_total, computador_total, 10),
        ],
            spacing=0
        ),
        bgcolor=ft.Colors.WHITE,
        border_radius=8,
        padding=12,
        shadow=ft.BoxShadow(
            spread_radius=1,
            blur_radius=10,
            color=ft.Colors.BLACK26,
            offset=ft.Offset(0, 4),
        )
    )

    container = ft.Container(
        content=ft.Column(
            controls=[
                ft.Image(src="images/trofeu.png", width=70),
                ft.Text("Placar Final", size=30, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE,
                        text_align=ft.TextAlign.CENTER),
                custom_table,
                botao_jogar
            ],
            spacing=25,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER
        ),
        padding=20,
        bgcolor=ft.Colors.WHITE,
        border_radius=8,
        shadow=ft.BoxShadow(
            spread_radius=1,
            blur_radius=10,
            color=ft.Colors.BLACK12,
            offset=ft.Offset(0, 4),
        )
    )

    def tocar_vitoria():
        for item in page.overlay:
            if isinstance(item, fta.Audio) and item.src.endswith("victory.mp3"):
                item.seek(0)
                item.play()
                break

    async def iniciar_animacao_vencedor():
        # Animação para o nome do vencedor
        if vencedor_nome_ref.current:
            anim_manager.add_animation(
                vencedor_nome_ref.current,
                target_scale=1.2,
                duration=500,
                curve=ft.AnimationCurve.EASE_OUT,
                repeat=True,
                auto_reverse=True
            )
            anim_manager.add_animation(
                vencedor_nome_ref.current,
                target_color=ft.Colors.RED,
                duration=500,
                curve=ft.AnimationCurve.EASE_OUT,
                repeat=True,
                auto_reverse=True
            )

        # Animação para o total geral do vencedor
        if vencedor_total_ref.current:
            anim_manager.add_animation(
                vencedor_total_ref.current,
                target_scale=1.2,
                duration=500,
                curve=ft.AnimationCurve.EASE_OUT,
                repeat=True,
                auto_reverse=True
            )
            anim_manager.add_animation(
                vencedor_total_ref.current,
                target_color=ft.Colors.RED,
                duration=500,
                curve=ft.AnimationCurve.EASE_OUT,
                repeat=True,
                auto_reverse=True
            )

        # Animação sutil para o perdedor
        if perdedor_nome_ref.current:
            anim_manager.add_animation(
                perdedor_nome_ref.current,
                target_opacity=0.6,
                duration=500,
                curve=ft.AnimationCurve.EASE_OUT,
            )
        if perdedor_total_ref.current:
            anim_manager.add_animation(
                perdedor_total_ref.current,
                target_opacity=0.6,
                duration=500,
                curve=ft.AnimationCurve.EASE_OUT,
            )

        page.update()
        anim_manager.start_animation(page)

    if fim_de_jogo:
        if not page.session.get("animacao_placar_executada_game_end"):

            page.session.set("animacao_placar_executada_game_end", True)

            async def iniciar_animacoes_seguras():
                await asyncio.sleep(0.5)

                def refs_prontos():
                    return (
                        vencedor_nome_ref.current
                        and vencedor_total_ref.current
                        and getattr(vencedor_nome_ref.current, "_Control__page", None)
                        and getattr(vencedor_total_ref.current, "_Control__page", None)
                    )

                max_tentativas = 80
                for _ in range(max_tentativas):
                    await asyncio.sleep(0.3)
                    page.update()

                    if refs_prontos():
                        tocar_vitoria()
                        await iniciar_animacao_vencedor()
                        return

            page.run_task(iniciar_animacoes_seguras)

    view = ft.View(
        route="/placar",
        controls=[
            ft.ResponsiveRow(
                controls=[ft.Container(content=container, col={"xs": 12, "md": 10, "lg": 8})],
                alignment=ft.MainAxisAlignment.CENTER
            )
        ],
        scroll=ft.ScrollMode.AUTO
    )

    return view
