import flet as ft


# A classe agora herda diretamente de ft.Column, evitando o erro do UserControl.
class AreaDeJogoDoJogador(ft.Column):
    def __init__(self, nome_jogador: str, eh_local: bool):
        # 1. Inicializa o ft.Column (sem argumentos de layout de container)
        super().__init__(
            spacing=5  # Espaçamento dos itens da coluna (propriedade válida de ft.Column)
        )

        self.nome_jogador = nome_jogador
        self.eh_local = eh_local

        # 2. Refs para a UI
        self.distance_txt = ft.Ref[ft.Text]()
        self.status_txt = ft.Ref[ft.Text]()
        self.limit_txt = ft.Ref[ft.Text]()
        self.last_card_txt = ft.Ref[ft.Text]()
        self.safeties_txt = ft.Ref[ft.Text]()
        self.traffic_light = ft.Ref[ft.Image]()
        self.turno_info = ft.Ref[ft.Text]()

        if self.eh_local:
            self.hand_column = ft.Ref[ft.Row]()

        # 3. Define a lista de controles da Coluna
        self.controls = [
            ft.Row(
                controls=[
                    ft.Text(
                        value=self.nome_jogador,
                        size=20,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.BLUE_500
                    ),
                    *(
                        [
                            ft.Text(ref=self.turno_info, size=16, weight=ft.FontWeight.W_500,
                                    color=ft.Colors.GREY_600),
                            ft.Image(
                                ref=self.traffic_light,
                                src="images/red_light.png",
                                width=22
                            )
                        ]
                        if self.eh_local else
                        [
                            ft.Image(
                                ref=self.traffic_light,
                                src="images/red_light.png",
                                width=22
                            )
                        ]
                    )
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            ),

            ft.Divider(height=1, thickness=2, color=ft.Colors.BLUE_500),

            # LINHA 1: Distância | Situação | Limite
            ft.ResponsiveRow(
                controls=[
                    ft.Column(
                        col={"xs": 12},
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Text("Distância:", color="#180F4A", size=16, weight=ft.FontWeight.W_500),
                                    ft.Text(ref=self.distance_txt, value="0 Km", color=ft.Colors.GREY_500,
                                            size=16, weight=ft.FontWeight.W_500),
                                    ft.VerticalDivider(width=1, thickness=1, color=ft.Colors.GREY_400),
                                    ft.Text("Situação:", color="#180F4A", size=16, weight=ft.FontWeight.W_500),
                                    ft.Text(ref=self.status_txt, value="Luz Vermelha", color=ft.Colors.RED,
                                            size=16, weight=ft.FontWeight.W_500),
                                    ft.VerticalDivider(width=1, thickness=1, color=ft.Colors.GREY_400),
                                    ft.Text("Limite 50 km:", color="#180F4A", size=16,
                                            weight=ft.FontWeight.W_500),
                                    ft.Text(ref=self.limit_txt, value="Inativo", color=ft.Colors.GREY_500,
                                            size=16, weight=ft.FontWeight.W_500),
                                ],
                                spacing=5, run_spacing=5, wrap=True,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER
                            )
                        ]
                    )
                ], run_spacing={"xs": 5}),

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
                                    ft.Text(ref=self.last_card_txt, value="Nenhuma", color=ft.Colors.GREY_500,
                                            size=16, weight=ft.FontWeight.W_500),
                                ],
                                spacing=5, wrap=True
                            )
                        ]
                    ),
                ], run_spacing={"xs": 5}),

            # LINHA 3: Segurança
            ft.ResponsiveRow(
                controls=[
                    ft.Column(
                        col={"xs": 12},
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Text("Segurança:", color="#180F4A", size=16, weight=ft.FontWeight.W_500),
                                    ft.Text(ref=self.safeties_txt, value="Nenhuma", color=ft.Colors.GREY_500,
                                            size=16, weight=ft.FontWeight.W_500),
                                ],
                                spacing=5, wrap=True
                            )
                        ]
                    ),
                ], run_spacing={"xs": 5}),

            *(
                [
                    ft.Divider(height=1, thickness=1, color=ft.Colors.BLUE_500),
                    ft.Text(
                        value="Mão do jogador:",
                        color="#180F4A",
                        size=16,
                        weight=ft.FontWeight.W_500
                    ),
                    ft.Container(
                        expand=True,
                        content=ft.Row(
                            ref=self.hand_column,
                            spacing=5,
                            run_spacing=2,
                            wrap=True,
                            alignment=ft.MainAxisAlignment.START
                        ),
                    ),
                ] if self.eh_local else []
            )
        ]

        # 4. Envolve a Coluna (self) em um Container e o adiciona à lista de controles do próprio objeto.
        # Isso simula o comportamento do UserControl que retorna um Container, mas o objeto é o Column.
        self.container = ft.Container(
            expand=True,
            padding=10,
            bgcolor="#ffffff",
            border_radius=10,
            border=ft.border.all(width=1, color=ft.Colors.GREY_200),
            shadow=ft.BoxShadow(blur_radius=4, color=ft.Colors.BLACK12),
            content=self  # O conteúdo do Container é a própria Coluna (self)
        )

    # Método build() não é necessário ao herdar de ft.Column/ft.Container,
    # mas precisamos de um método para ser usado no lugar do controle principal.
    def get_container(self):
        """Retorna o Container que envolve a coluna para ser adicionado ao layout principal."""
        return self.container

    # O método atualizar_ui permanece
    def atualizar_ui(self, jogador_data: dict, is_my_turn: bool = False, deck_size: int = 0,
                     tentar_jogar_carta_callback=None):
        # --- UI Comum ---
        self.distance_txt.current.value = f'{jogador_data.get("distance", 0)} Km'
        self.distance_txt.current.color = ft.Colors.BLUE if jogador_data.get("distance", 0) > 0 else ft.Colors.GREY_500

        self.status_txt.current.value = jogador_data.get("status", "Luz Vermelha")
        self.status_txt.current.color = ft.Colors.GREEN if jogador_data.get("status") == "Luz Verde" else ft.Colors.RED

        self.limit_txt.current.value = "Ativo" if jogador_data.get("limite") else "Inativo"
        self.limit_txt.current.color = ft.Colors.AMBER_700 if jogador_data.get("limite") else ft.Colors.GREY_500

        self.last_card_txt.current.value = jogador_data.get("last_card_played", "Nenhuma")
        self.last_card_txt.current.color = ft.Colors.BLUE if jogador_data.get(
            "last_card_played") != "Nenhuma" else ft.Colors.GREY_500

        self.safeties_txt.current.value = ' | '.join(jogador_data.get("safeties", [])) or "Nenhuma"
        self.safeties_txt.current.color = ft.Colors.ORANGE if jogador_data.get("safeties") else ft.Colors.GREY_500

        # --- UI Específica para Jogador Local ---
        if self.eh_local:
            self.turno_info.current.value = "✅ Sua vez!" if is_my_turn else "⏳ Aguardando o outro jogador..."

            # 🃏 Mão do jogador
            self.hand_column.current.controls.clear()
            for carta_item in jogador_data.get("hand", []):
                tipo = carta_item.get("type")
                icone = "❓"
                cor = ft.Colors.BLACK
                if tipo == "ataque":
                    icone, cor = "⚠️", ft.Colors.RED
                elif tipo == "defesa":
                    icone, cor = "🛡️", ft.Colors.GREEN
                elif tipo == "segurança":
                    icone, cor = "⭐", ft.Colors.ORANGE
                elif tipo == "distancia":
                    icone, cor = "🚗", ft.Colors.BLUE

                self.hand_column.current.controls.append(
                    ft.ElevatedButton(
                        text=f"{icone} {carta_item['value']}",
                        on_click=(lambda e, c=carta_item: tentar_jogar_carta_callback(c)) if is_my_turn else None,
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