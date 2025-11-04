import flet as ft

def ajuda_view(page: ft.Page):
    page.title = "Mille Bornes"
    page.bgcolor = "#F5F5F5"
    page.scroll = ft.ScrollMode.AUTO
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.vertical_alignment = ft.MainAxisAlignment.START

    title_style = ft.TextStyle(size=30, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
    text_style = ft.TextStyle(size=16, color=ft.Colors.BLACK)
    section_style = ft.TextStyle(size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_400)

    title = ft.Container(
        content=ft.Text("Regras do Jogo Mille Bornes", style=title_style),
        bgcolor=ft.Colors.BLUE_500,
        padding=10,
        border_radius=5,
        alignment=ft.alignment.center,
        margin=ft.margin.only(top=20, bottom=20)
    )

    content_column = ft.Column(
        controls=[
            ft.Text("\nCapítulo I - Objetivo", style=section_style),
            ft.Divider(height=5, color=ft.Colors.BLUE_500),
            ft.Text(
                "O objetivo do jogo é ser o primeiro a alcançar o total de 5000 pontos em várias rodadas do jogo.\n"
                "Para isso, os jogadores tentarão completar viagens de exatamente 700Km ou 1000km em cada rodada.\n",
                style=text_style
            ),
            ft.Text("Capítulo II - Cartas", style=section_style),
            ft.Divider(height=5, color=ft.Colors.BLUE_500),
            ft.Text("O baralho é composto de 100 cartas, descritas abaixo:", style=text_style),
            ft.Text(
                "• Cartas de Distância: 25, 50, 75, 100 ou 200km.\n"
                "• Cartas de Azar: Luz Vermelha, Limite 50Km, Sem Gasolina, Pneu Furado, Acidente.\n"
                "• Cartas de Remédio: Gasolina, Estepe, Conserto, Fim de Limite, Luz Verde.\n"
                "• Cartas de Segurança: Caminho Livre, Tanque Extra, Pneu de Aço, Bom Motorista.\n",
                style=text_style
            ),
            ft.Text("Capítulo III - O Jogo", style=section_style),
            ft.Divider(height=5, color=ft.Colors.BLUE_500),
            ft.Text(
                "O primeiro a jogar poderá fazer uma das seguintes jogadas:\n"
                "• Jogar uma Luz Verde para iniciar a viagem.\n"
                "• Jogar uma carta de segurança.\n"
                "• Jogar um Limite 50Km contra o adversário.\n"
                "• Descartar uma carta inválida (não útil no momento).\n",
                style=text_style
            ),
            ft.Text("Capítulo IV - O Placar", style=section_style),
            ft.Divider(height=5, color=ft.Colors.BLUE_500),
            ft.Text(
                "O placar é totalizado ao final de cada rodada, conforme os seguintes critérios:\n"
                "• Total de pontos correspondentes à distância percorrida.\n"
                "• 100 pontos por cada carta de segurança jogada.\n"
                "• 400 pontos por todas cartas de segurança jogadas.\n"
                "• 300 pontos por cada carta de segurança jogada em defesa.\n"
                "• 300/400 pontos pelo percurso completado 700km/1000km.\n"
                "• 200/300 pontos por completar o percurso 700km/1000km sem usar a carta de 200km.\n"
                "• 300/500 pontos por completar o percurso 700km/1000km e o adversário não sair do zero.\n"
                "• 300 pontos por pedir extensão até 1000km.\n"
                "• 500/400 pontos pelo percurso completado 700km/1000km após o final do baralho.\n",
                style=text_style
            ),
            ft.Text("Capítulo V - Vencedor", style=section_style),
            ft.Divider(height=5, color=ft.Colors.BLUE_500),
            ft.Text(
                "O vencedor sera o primeiro a alcançar 5000 pontos, ou o jogador com mais pontos caso ambos ultrapassem 5000 pontos.\n",
                style=text_style
            ),
            ft.Text("Capítulo VI - Extensão", style=section_style),
            ft.Divider(height=5, color=ft.Colors.BLUE_500),
            ft.Text(
                "O jogador que alcançar 700km pode optar por continuar a viagem até 1000km.\n",
                style=text_style
            ),
            ft.Text("Capítulo VII - Dicas", style=section_style),
            ft.Divider(height=5, color=ft.Colors.BLUE_500),
            ft.Text(
                "• Guarde cartas de segurança para responder aos ataques e ganhar bônus.\n"
                "• Descarte cartas que não têm valor para você no momento.\n"
                "• Tente lembrar as cartas que já foram jogadas.\n"
                "• Seja rápido: você tem 30 segundos para jogar, caso contrário você perderá 25Km da distância percorrida.",
                style=text_style
            ),
            ft.Text("\nAgradecimentos", style=section_style),
            ft.Divider(height=5, color=ft.Colors.BLUE_500),
            ft.Text(
                "• Prof. Dalton Peixoto.\n"
                "• Prof. João Lira.\n"
                "• Prof. Dimitri Teixeira",
                style=text_style
            )
        ],
        spacing=15
    )

    container_responsive = ft.Container(
        content=content_column,
        bgcolor="#FFFFFF",
        border_radius=10,
        padding=20,
        expand=True
    )

    responsive_area = ft.ResponsiveRow(
        controls=[
            ft.Container(
                content=container_responsive,
                col={"xs": 12, "md": 8, "lg": 6}
            )
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        run_spacing=20
    )

    voltar_button = ft.ElevatedButton(
        text="Voltar",
        on_click=lambda _: page.go("/"),
        color=ft.Colors.WHITE,
        bgcolor=ft.Colors.BLUE_700,
        style=ft.ButtonStyle(overlay_color=ft.Colors.BLUE_400),
    )

    # FOOTER
    footer = ft.Container(
        content=ft.Column(
            controls=[
                ft.Text("Mille Bornes", size=16, weight=ft.FontWeight.W_400, color=ft.Colors.WHITE,
                        font_family='Lobster', text_align=ft.TextAlign.CENTER),
                ft.Text("© Todos os direitos reservados.", color="white", size=12, text_align=ft.TextAlign.CENTER)
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=2,
        ),
        bgcolor="#004C99",
        padding=ft.padding.symmetric(vertical=10),
        border_radius=10,
        margin=ft.margin.only(top=30),
        border=ft.border.all(width=2, color=ft.Colors.RED),
        alignment=ft.alignment.center
    )

    return ft.View(
        "/ajuda",
        controls=[
            title,
            responsive_area,
            ft.Row([voltar_button], alignment=ft.MainAxisAlignment.CENTER),
            footer
        ],
        scroll=ft.ScrollMode.AUTO
    )
