from random import shuffle

# Quantidade oficial de cartas no Mille Bornes
CARD_DEFINITIONS = {
    "distancia": {
        "25 km": 10,
        "50 km": 10,
        "75 km": 10,
        "100 km": 13,
        "200 km": 2
    },
    "ataque": {
        "Pneu Furado": 2,
        "Sem Gasolina": 2,
        "Acidente": 2,
        "Limite 50 km": 3,
        "Luz Vermelha": 4
    },
    "defesa": {
        "Estepe": 6,
        "Gasolina": 6,
        "Conserto": 6,
        "Fim de Limite": 6,
        "Luz Verde": 14
    },
    "segurança": {
        "Tanque Extra": 1,
        "Pneu de Aço": 1,
        "Bom Motorista": 1,
        "Caminho Livre": 1
    }
}

def create_deck():
    """Cria um baralho embaralhado com a composição oficial do Mille Bornes."""
    deck = []
    for tipo, cartas in CARD_DEFINITIONS.items():
        for valor, quantidade in cartas.items():
            deck.extend([{"type": tipo, "value": valor} for _ in range(quantidade)])
    shuffle(deck)
    # print(f'deck: {deck}')
    return deck
