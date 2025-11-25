import flet as ft


class AreaDeProgressoComparativo(ft.Container):
    """
    Componente que exibe as barras de progresso comparativas (Jogador Local vs Oponente)
    e a régua de graduação (0km a 1000km), agora 100% responsivo no mobile.
    """

    def __init__(self, barra_jogador: ft.ProgressBar, barra_oponente: ft.ProgressBar,
                 graduacao_regua: ft.Control, nome_jogador: str, nome_oponente_ref: ft.Ref[ft.Text]):

        self.nome_oponente_ref = nome_oponente_ref

        super().__init__(
            expand=True,
            width=float("inf"),  # 🔥 Força a ocupar toda a largura disponível (inclusive celular)
            content=ft.Column(
                expand=True,
                width=float("inf"),
                spacing=8,
                controls=[
                    # ----------------------------
                    # Barra do Jogador Local
                    # ----------------------------
                    ft.Column(
                        expand=True,
                        width=float("inf"),
                        spacing=3,
                        controls=[
                            ft.Text(
                                value=nome_jogador,
                                color="#180F4A",
                                size=16,
                                weight=ft.FontWeight.W_500
                            ),
                            barra_jogador,
                        ],
                    ),

                    # ----------------------------
                    # Barra do Oponente
                    # ----------------------------
                    ft.Column(
                        expand=True,
                        width=float("inf"),
                        spacing=3,
                        controls=[
                            ft.Text(
                                ref=self.nome_oponente_ref,
                                value="Oponente",
                                color="#180F4A",
                                size=16,
                                weight=ft.FontWeight.W_500
                            ),
                            barra_oponente,
                        ],
                    ),

                    # ----------------------------
                    # Régua de Graduação (0–1000)
                    # Agora 100% responsiva
                    # ----------------------------
                    ft.Container(
                        expand=True,
                        width=float("inf"),
                        content=graduacao_regua
                    ),

                    ft.Container(height=6)
                ]
            )
        )

    def atualizar_nomes(self, nome_oponente: str):
        """Atualiza o nome do oponente no texto da barra de progresso."""
        if self.nome_oponente_ref.current is not None:
            self.nome_oponente_ref.current.value = nome_oponente
