# firebase_helpers.py

import random
import time
from uuid import uuid4  # Adicionado para uso potencial em shuffle (se necessário)


def obter_nome_jogador(page):
    try:
        return page.client_storage.get("nome_jogador")
    except Exception as e:
        # print(f"⚠️ Erro ao obter nome do jogador: {e}")
        return


def obter_sala_jogador(page):
    try:
        return page.client_storage.get("sala_jogador")
    except Exception as e:
        # print(f"⚠️ Erro ao obter sala do jogador: {e}")
        return


def corrigir_mao_jogador(sala_ref, estado_jogo):
    try:
        snapshot_atual = sala_ref.get()
        sala_data = snapshot_atual.to_dict()
    except Exception as e:
        # print(f"❌ Erro ao acessar Firestore em corrigir_mao_jogador: {e}")
        return

    if not sala_data:
        return

    caminho = estado_jogo["meu_caminho"]
    jogador_data = sala_data.get(caminho)

    if not jogador_data:
        return

    mao_atual = jogador_data.get("hand", [])
    deck = sala_data.get("deck", [])

    cartas_faltando = 7 - len(mao_atual)
    if cartas_faltando <= 0 or not deck:
        # ⚠️ Verifica fim de jogo se não há cartas no deck nem nas mãos
        mao1 = len(sala_data.get("player1", {}).get("hand", []))
        mao2 = len(sala_data.get("player2", {}).get("hand", []))
        if not deck and mao1 == 0 and mao2 == 0 and not sala_data.get("game_status") == "finished":
            # 🏁 Acionando Fim de Jogo por Baralho Vazio
            finalizar_placar_mao(sala_ref, sala_data, mao_vazia=True)
            return

    if cartas_faltando > 0 and deck:
        # Puxa cartas do deck para completar a mão
        for _ in range(cartas_faltando):
            if deck:
                carta_puxada = deck.pop(0)
                mao_atual.append(carta_puxada)
            else:
                break

        updates = {
            f"{caminho}.hand": mao_atual,
            "deck": deck
        }
        sala_ref.update(updates)


def distribuir_cartas(sala_ref, deck):
    random.shuffle(deck)
    updates = {
        "deck": deck[14:],
        "player1.hand": deck[:7],
        "player2.hand": deck[7:14],
        "turn": "player1",
        "game_status": "started"
    }
    sala_ref.update(updates)


def jogar_carta(sala_ref, estado_jogo, carta):
    caminho = estado_jogo["meu_caminho"]
    sala_data = sala_ref.get().to_dict()
    meu = sala_data.get(caminho, {})
    nova_mao = meu.get("hand", []).copy()
    for i, c in enumerate(nova_mao):
        if c == carta:
            del nova_mao[i]
            break

    carta_str = carta['value']
    turno_atual = estado_jogo["turno"]
    proximo_turno = "player2" if turno_atual == "player1" else "player1"
    tipo = carta["type"]
    valor = carta["value"]

    # --- LÓGICA DE EXTENSÃO GLOBAL (FIX) ---
    oponente_path = "player2" if estado_jogo["eh_player1"] else "player1"
    oponente = sala_data.get(oponente_path, {})

    meu_extensao = meu.get("extensao", False)
    oponente_extensao = oponente.get("extensao", False)
    # A extensão é ativada se EU ou o OPONENTE a ativamos.
    limite_700_removido = meu_extensao or oponente_extensao
    # ---------------------------------------

    updates = {
        f"{caminho}.hand": nova_mao,
        f"{caminho}.last_card_played": carta_str
    }

    pass_turn = True

    if tipo == "distancia":
        if meu.get("aguardando_extensao", False):
            # print("⚠️ Jogada bloqueada — aguardando extensão.")
            return "você precisa escolher entre extensão ou descarte"

        if meu.get("status") != "Luz Verde":
            # 📝 MOTIVO: Não está com Luz Verde
            return "você não está com 'Luz Verde'"

        valor_int = int(valor.split()[0])
        distancia_atual = meu.get("distance", 0)
        nova_distancia = distancia_atual + valor_int

        # ✅ Marca flag de uso de 200km (somente se carta válida, não descarte)
        if valor_int == 200:
            updates[f"{caminho}.com_200"] = "S"

        # 1️⃣ Atingiu exatamente 700km — aciona extensão
        if not limite_700_removido and nova_distancia == 700:
            # print("🧪 Atingiu exatamente 700km. Ativando aguardando_extensao.")
            updates[f"{caminho}.aguardando_extensao"] = True
            updates[f"{caminho}.distance"] = nova_distancia
            sala_ref.update(updates)
            return "EXTENSAO_PENDENTE"

        # 2️⃣ Verificação de limite 50 km
        if meu.get("limite", False) and valor_int > 50:
            return "o limite de 50 km está Ativo"

        # 3️⃣ Bloqueio se passar de 700km sem extensão
        if not limite_700_removido and nova_distancia > 700:
            # print("🚫 Tentativa de passar de 700km sem extensão. Jogada bloqueada.")
            return "você precisa de exatos 700 km para pedir extensão ou encerrar a partida"

        # 4️⃣ Bloqueio se passar de 1000km
        if nova_distancia > 1000:
            return "você precisa de exatos 1000 km para encerrar a partida"

        # ✅ Atualiza distância
        updates[f"{caminho}.distance"] = nova_distancia

        # 🏁 Finaliza partida ao atingir 1000km
        if nova_distancia == 1000:
            updates[f"{caminho}.winner"] = True
            updates[f"{caminho}.finalizar"] = True
            updates["game_status"] = "finished"

        pass_turn = True

    elif tipo == "ataque":
        oponente_path = "player2" if estado_jogo["eh_player1"] else "player1"
        oponente_data = sala_data.get(oponente_path, {})

        segurancas_que_bloqueiam = {
            "Luz Vermelha": "Caminho Livre",
            "Limite 50 km": "Caminho Livre",
            "Acidente": "Bom Motorista",
            "Pneu Furado": "Pneu de Aço",
            "Sem Gasolina": "Tanque Extra"
        }

        nome_seguranca = segurancas_que_bloqueiam.get(valor)
        if nome_seguranca and nome_seguranca in oponente_data.get("safeties", []):
            # 📝 MOTIVO: Oponente está protegido
            return f"o oponente está protegido pela segurança '{nome_seguranca}'"

        oponente_status = oponente_data.get("status", "")
        oponente_limite = oponente_data.get("limite", False)

        if valor == "Limite 50 km":
            if oponente_limite:
                # 📝 MOTIVO: Limite 50 km já ativo no oponente
                return "o oponente já está com o Limite 50 km Ativo"
            updates[f"{oponente_path}.limite"] = True
        else:
            if oponente_status != "Luz Verde":
                # 📝 MOTIVO: Oponente não está com Luz Verde (exceto Limite 50 km)
                return "o oponente não está com 'Luz Verde'"
            updates[f"{oponente_path}.status"] = valor

        pass_turn = True

    elif tipo == "defesa":
        status = meu.get("status", "")
        limite = meu.get("limite", False)

        # Mapeamento do status atacado para a carta de defesa
        validacao_defesa = {
            "Luz Verde": "Luz Vermelha",
            "Conserto": "Acidente",
            "Estepe": "Pneu Furado",
            "Gasolina": "Sem Gasolina"
        }

        if valor == "Fim de Limite":
            if not limite:
                # 📝 MOTIVO: Limite 50 km não está ativo
                return "você não está com o Limite 50 km Ativo"
            updates[f"{caminho}.limite"] = False
        elif valor in validacao_defesa:
            status_requerido = validacao_defesa[valor]
            if status != status_requerido:
                # 📝 MOTIVO: Defesa errada para o status atual
                return f"você está com '{status}' e não com '{status_requerido}'"
            updates[f"{caminho}.status"] = "Luz Verde"
        else:
            # 📝 MOTIVO: Carta de defesa desconhecida ou erro
            return "não foi possível determinar a regra de defesa"

        pass_turn = True

    elif tipo == "segurança":
        segs = meu.get("safeties", [])
        if valor in segs:
            # 📝 MOTIVO: Segurança já jogada
            return "você já tem essa carta de segurança em jogo"
        segs.append(valor)
        updates[f"{caminho}.safeties"] = segs

        # 🧠 Se a segurança resolver um ataque ativo, desativa-o e conta o coup fourré
        safety_responses = meu.get("safety_responses", 0)

        if valor == "Caminho Livre":
            #if meu.get("limite") or meu.get("status") == "Luz Vermelha":
                #updates[f"{caminho}.limite"] = False
                #updates[f"{caminho}.status"] = "Luz Verde"
                #safety_responses += 1
            if meu.get("limite"):
                updates[f"{caminho}.limite"] = False
            if meu.get("status") == "Luz Vermelha":
                updates[f"{caminho}.status"] = "Luz Verde"
            safety_responses += 1
        elif valor == "Bom Motorista":
            if meu.get("status") == "Acidente":
                updates[f"{caminho}.status"] = "Luz Verde"
                safety_responses += 1
        elif valor == "Pneu de Aço":
            if meu.get("status") == "Pneu Furado":
                updates[f"{caminho}.status"] = "Luz Verde"
                safety_responses += 1
        elif valor == "Tanque Extra":
            if meu.get("status") == "Sem Gasolina":
                updates[f"{caminho}.status"] = "Luz Verde"
                safety_responses += 1

        updates[f"{caminho}.safety_responses"] = safety_responses

    pass_turn = True

    if pass_turn:
        updates["turn"] = proximo_turno

    sala_ref.update(updates)
    time.sleep(0.5)
    return True


def descartar_carta(sala_ref, estado_jogo, carta):
    meu = estado_jogo["meu"]
    nova_mao = meu.get("hand", []).copy()
    try:
        # Encontra a carta com base no objeto completo (incluindo 'type')
        index_carta = nova_mao.index(carta)
        # A carta é simplesmente removida da mão e do jogo (descarte permanente).
        nova_mao.pop(index_carta)

    except ValueError:
        # print("⚠️ Carta não encontrada na mão para descarte.")
        return

    caminho = estado_jogo["meu_caminho"]
    turno_atual = estado_jogo["turno"]
    proximo_turno = "player2" if turno_atual == "player1" else "player1"

    updates = {
        f"{caminho}.hand": nova_mao,
        # O deck não é atualizado, pois cartas descartadas não voltam
        "turn": proximo_turno,
        f"{caminho}.last_card_played": f' {carta["value"]} (descarte)'
    }
    sala_ref.update(updates)
    corrigir_mao_jogador(sala_ref, estado_jogo)


def comprar_carta_do_deck(sala_ref, estado_jogo):
    meu = estado_jogo["meu"]
    caminho = estado_jogo["meu_caminho"]
    turno_atual = estado_jogo["turno"]
    proximo_turno = "player2" if turno_atual == "player1" else "player1"

    sala_data = sala_ref.get().to_dict()
    deck = sala_data.get("deck", [])

    if not deck:
        # ⚠️ Fim de jogo se todos sem cartas
        mao1 = len(sala_data.get("player1", {}).get("hand", []))
        mao2 = len(sala_data.get("player2", {}).get("hand", []))
        if mao1 == 0 and mao2 == 0 and not sala_data.get("game_status") == "finished":
            finalizar_placar_mao(sala_ref, sala_data, mao_vazia=True)
            return

    if deck:
        carta_comprada = deck.pop(0)
        mao_atual = meu.get("hand", [])
        mao_atual.append(carta_comprada)

        updates = {
            f"{caminho}.hand": mao_atual,
            "deck": deck,
            f"{caminho}.last_card_played": f' {carta_comprada["value"]} (compra)'
        }
        sala_ref.update(updates)


def finalizar_placar_mao(sala_ref, sala_data, mao_vazia=False):
    # 📝 Esta função é a lógica que calcula o placar no final de uma MÃO (partida)

    # Assumindo que o jogo é entre player1 e player2
    meu_caminho = "player1"
    oponente_caminho = "player2"

    meu = sala_data.get(meu_caminho, {})
    oponente = sala_data.get(oponente_caminho, {})

    distance = meu.get("distance", 0)
    distance_op = oponente.get("distance", 0)

    # Verifica se houve vencedor por 1000km
    winner = meu.get("winner", False)
    winner_op = oponente.get("winner", False)

    # 1. Bônus de extensão
    # Obtendo o status de extensão do jogador.
    extensao = meu.get("extensao", False)
    extensao_op = oponente.get("extensao", False)

    # 2. Bônus por baralho vazio
    bonus_fim_baralho = 0
    if mao_vazia and not winner and not winner_op:
        # O bônus é para quem tiver a menor mão no final
        mao_count = len(meu.get("hand", []))
        mao_count_op = len(oponente.get("hand", []))

        if mao_count == 0 and mao_count_op > 0:
            bonus_fim_baralho = 300
        elif mao_count_op == 0 and mao_count > 0:
            bonus_fim_baralho = 0  # O bônus vai para o oponente
        elif mao_count == 0 and mao_count_op == 0:
            # Se ambos zeraram a mão no final, o bônus é zero (ou para quem zerou primeiro, o que é mais complexo)
            # Manter em zero por simplificação da regra não especificada
            bonus_fim_baralho = 0
        else:
            bonus_fim_baralho = 0

    bonus_fim_baralho_op = 0
    if mao_vazia and not winner and not winner_op:
        mao_count = len(meu.get("hand", []))
        mao_count_op = len(oponente.get("hand", []))

        if mao_count_op == 0 and mao_count > 0:
            bonus_fim_baralho_op = 300
        else:
            bonus_fim_baralho_op = 0

    # 3. Pontuação de Segurança
    # Bônus de 100 pontos por cada segurança jogada
    num_segurancas = len(meu.get("safeties", []))
    num_segurancas_op = len(oponente.get("safeties", []))

    bonus_segurancas_meu = num_segurancas * 100
    bonus_segurancas_op = num_segurancas_op * 100

    # Bônus de 1000 pontos por ter as 4 seguranças
    bonus_todas_segurancas_meu = 1000 if num_segurancas == 4 else 0
    bonus_todas_segurancas_op = 1000 if num_segurancas_op == 4 else 0

    # 4. Total de Coups Fourrés (300 pontos por cada resposta)
    total_safety_responses_meu = meu.get("safety_responses", 0)
    total_safety_responses_op = oponente.get("safety_responses", 0)

    # 5. Distância é o ponto mais básico

    # 6. Bônus de Vitória (1000km)
    bonus_vitoria = 400 if winner else 0
    bonus_vitoria_op = 400 if winner_op else 0

    # 7. Bônus de Zero (Oponente sem cartas/zero distance)

    placar_mao = {
        "distancia": distance,
        "bonus_vitoria": bonus_vitoria,
        "bonus_segurancas": bonus_segurancas_meu,  # 100pts por segurança
        "bonus_todas_segurancas": bonus_todas_segurancas_meu,  # 1000pts por 4 seguranças
        "total_coup_fourre": total_safety_responses_meu * 300,
        "bonus_zero": (
            500 if distance == 1000 and distance_op == 0 else
            300 if distance == 700 and meu.get("sem_extensao", "N") == "N" and distance_op == 0 else
            0
        ),
        "oponente_zero": (
            500 if distance_op == 1000 and distance == 0 else
            300 if distance_op == 700 and oponente.get("sem_extensao", "N") == "N" and distance == 0 else
            0
        ),
        "bonus_extensao": 300 if extensao else 0,
        "fim_do_baralho": bonus_fim_baralho,
    }

    # Bônus de 700km e Zero
    if meu.get("sem_extensao", "N") == "S" and distance == 700:
        # Se 700km foi alcançado sem extensão, o bônus de 300km não se aplica
        placar_mao["bonus_zero"] = 0
        placar_mao["bonus_extensao"] = 0

    # A soma é corrigida para somar todos os bônus
    placar_mao["total_da_mao"] = sum(placar_mao.values()) - (
        500 if meu.get("sem_extensao", "N") == "S" and distance == 700 else 0)

    placar_oponente = {
        "distancia": distance_op,
        "bonus_vitoria": bonus_vitoria_op,
        "bonus_segurancas": bonus_segurancas_op,  # 100pts por segurança
        "bonus_todas_segurancas": bonus_todas_segurancas_op,  # 1000pts por 4 seguranças
        "total_coup_fourre": total_safety_responses_op * 300,
        "bonus_zero": (
            500 if distance_op == 1000 and distance == 0 else
            300 if distance_op == 700 and oponente.get("sem_extensao", "N") == "N" and distance == 0 else
            0
        ),
        "oponente_zero": (
            500 if distance == 1000 and distance_op == 0 else
            300 if distance == 700 and meu.get("sem_extensao", "N") == "N" and distance_op == 0 else
            0
        ),
        "bonus_extensao": 300 if extensao_op else 0,
        "fim_do_baralho": bonus_fim_baralho_op,
    }

    if oponente.get("sem_extensao", "N") == "S" and distance_op == 700:
        placar_oponente["bonus_zero"] = 0
        placar_oponente["bonus_extensao"] = 0

    placar_oponente["total_da_mao"] = sum(placar_oponente.values()) - (
        500 if oponente.get("sem_extensao", "N") == "S" and distance_op == 700 else 0)

    # 🧮 Soma do total geral
    novo_total_meu = meu.get("placar", {}).get("total_geral", 0) + placar_mao["total_da_mao"]
    novo_total_oponente = oponente.get("placar", {}).get("total_geral", 0) + placar_oponente["total_da_mao"]

    # 📝 Atualizar Firestore
    updates = {
        f"{meu_caminho}.placar.atual_mao": placar_mao,
        f"{meu_caminho}.placar.total_geral": novo_total_meu,
        f"{meu_caminho}.placar_registrado": True,
        f"{meu_caminho}.placar_visto": False,
        f"{oponente_caminho}.placar.atual_mao": placar_oponente,
        f"{oponente_caminho}.placar.total_geral": novo_total_oponente,
        f"{oponente_caminho}.placar_registrado": True,
        f"{oponente_caminho}.placar_visto": False,
        "game_status": "finished"  # Finaliza a MÃO
    }
    sala_ref.update(updates)