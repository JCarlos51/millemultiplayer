import flet as ft


class AreaDeProgressoComparativo(ft.Column):
    """
    Componente que exibe as barras de progresso comparativas (Jogador Local vs Oponente)
    e a régua de graduação (0km a 1000km).
    """

    def __init__(self, barra_jogador: ft.ProgressBar, barra_oponente: ft.ProgressBar, graduacao_regua: ft.Control,
                 nome_jogador: str, nome_oponente_ref: ft.Ref[ft.Text]):
        # A referência para o Text do nome do oponente é armazenada para ser atualizada
        self.nome_oponente_ref = nome_oponente_ref

        # Inicializa o ft.Column, que é o controle raiz e encapsula o layout
        super().__init__(
            visible=True,
            spacing=0,
            controls=[
                ft.Container(height=10),  # Espaçamento

                # 1. Barra do Jogador Local
                ft.Column(
                    controls=[
                        ft.Text(
                            value=nome_jogador,  # Nome estático do jogador local
                            color="#180F4A",
                            size=16,
                            weight=ft.FontWeight.W_500
                        ),
                        barra_jogador,  # ft.ProgressBar passado como argumento
                    ],
                    expand=True
                ),

                ft.Container(height=0),

                # 2. Barra do Oponente
                ft.Column(
                    controls=[
                        ft.Text(
                            ref=self.nome_oponente_ref,  # Usa a Ref para atualização dinâmica
                            value="Oponente",
                            color="#180F4A",
                            size=16,
                            weight=ft.FontWeight.W_500
                        ),
                        barra_oponente,  # ft.ProgressBar passado como argumento
                    ],
                    expand=True
                ),

                # 3. Régua de Graduação
                graduacao_regua,
                ft.Container(height=15)
            ]
        )

    def atualizar_nomes(self, nome_oponente: str):
        """Atualiza o nome do oponente no texto da barra de progresso."""
        if self.nome_oponente_ref.current is not None:
            self.nome_oponente_ref.current.value = nome_oponente