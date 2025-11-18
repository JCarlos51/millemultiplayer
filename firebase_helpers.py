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
    """
    Aplica a jogada de uma carta (distância / ataque / defesa / segurança)
    e atualiza o Firestore.

    Inclui:
    - lógica de extensão em 700 km
    - limite de 50 km
    - verificação de seguranças
    """

    try:
        sala_data = sala_ref.get().to_dict() or {}
    except Exception as e:
        print(f"❌ Erro ao acessar Firestore em jogar_carta: {e}")
        return "erro ao acessar a sala"

    caminho = estado_jogo["meu_caminho"]
    meu = sala_data.get(caminho, {})

    if not meu:
        print("⚠️ jogar_carta: dados do jogador não encontrados.")
        return "dados do jogador não encontrados"

    # cópia da mão para remoção da carta
    nova_mao = meu.get("hand", []).copy()
    for i, c in enumerate(nova_mao):
        if c == carta:
            del nova_mao[i]
            break

    carta_str = carta["value"]

    # ⚠️ Usar o turno do Firestore, não só o estado local
    turno_atual = sala_data.get("turn") or estado_jogo.get("turno")
    if turno_atual not in ("player1", "player2"):
        # fallback defensivo
        turno_atual = "player1"

    proximo_turno = "player2" if turno_atual == "player1" else "player1"
    tipo = carta["type"]
    valor = carta["value"]

    # --- LÓGICA DE EXTENSÃO GLOBAL (FIX) ---
    oponente_path = "player2" if estado_jogo.get("eh_player1") else "player1"
    oponente = sala_data.get(oponente_path, {})

    meu_extensao = meu.get("extensao", False)
    oponente_extensao = oponente.get("extensao", False)
    # A extensão é ativada se EU ou o OPONENTE a ativamos.
    limite_700_removido = meu_extensao or oponente_extensao
    # ---------------------------------------

    updates = {
        f"{caminho}.hand": nova_mao,
        f"{caminho}.last_card_played": carta_str,
    }

    pass_turn = True

    # ============================================================
    # 1) CARTAS DE DISTÂNCIA
    # ============================================================
    if tipo == "distancia":
        # já está aguardando extensão → não pode jogar distância
        if meu.get("aguardando_extensao", False):
            print("⚠️ Jogada distância bloqueada — aguardando decisão de extensão.")
            return "você precisa escolher entre extensão ou descarte"

        if meu.get("status") != "Luz Verde":
            return "você não está com 'Luz Verde'"

        valor_int = int(valor.split()[0])
        distancia_atual = meu.get("distance", 0)

        # 2️⃣ Verificação de limite 50 km vem ANTES de somar a distância
        if meu.get("limite", False) and valor_int > 50:
            return "o limite de 50 km está Ativo"

        nova_distancia = distancia_atual + valor_int

        print(
            f"🧮 [DISTÂNCIA] {caminho}: {distancia_atual} + {valor_int} = {nova_distancia} "
            f"(limite_700_removido={limite_700_removido})"
        )

        # ✅ Marca flag de uso de 200km (somente se carta válida)
        if valor_int == 200:
            updates[f"{caminho}.com_200"] = "S"

        # 1️⃣ Atingiu exatamente 700km — aciona extensão
        if not limite_700_removido and nova_distancia == 700:
            print("⏳ EXTENSAO_PENDENTE: atingiu 700 km, aguardando decisão do jogador.")
            updates[f"{caminho}.aguardando_extensao"] = True
            updates[f"{caminho}.distance"] = nova_distancia
            # ⚠️ NÃO passa o turno aqui – o mesmo jogador decide extensão
            sala_ref.update(updates)
            return "EXTENSAO_PENDENTE"

        # 3️⃣ Bloqueio se passar de 700km sem extensão
        if not limite_700_removido and nova_distancia > 700:
            print("🚫 Tentativa de passar de 700km sem extensão.")
            return "você precisa de exatos 700 km para pedir extensão ou encerrar a partida"

        # 4️⃣ Bloqueio se passar de 1000km
        if nova_distancia > 1000:
            print("🚫 Tentativa de ultrapassar 1000 km.")
            return "você precisa de exatos 1000 km para encerrar a partida"

        # ✅ Atualiza distância
        updates[f"{caminho}.distance"] = nova_distancia

        # 🏁 Finaliza partida ao atingir 1000km
        if nova_distancia == 1000:
            print(f"🏁 {caminho} atingiu 1000 km — finalizando partida.")
            updates[f"{caminho}.winner"] = True
            updates[f"{caminho}.finalizar"] = True
            updates["game_status"] = "finished"

        pass_turn = True

    # ============================================================
    # 2) CARTAS DE ATAQUE
    # ============================================================
    elif tipo == "ataque":
        oponente_data = sala_data.get(oponente_path, {})

        segurancas_que_bloqueiam = {
            "Luz Vermelha": "Caminho Livre",
            "Limite 50 km": "Caminho Livre",
            "Acidente": "Bom Motorista",
            "Pneu Furado": "Pneu de Aço",
            "Sem Gasolina": "Tanque Extra",
        }

        nome_seguranca = segurancas_que_bloqueiam.get(valor)
        if nome_seguranca and nome_seguranca in oponente_data.get("safeties", []):
            return f"o oponente está protegido pela segurança '{nome_seguranca}'"

        oponente_status = oponente_data.get("status", "")
        oponente_limite = oponente_data.get("limite", False)

        if valor == "Limite 50 km":
            if oponente_limite:
                return "o oponente já está com o Limite 50 km Ativo"
            updates[f"{oponente_path}.limite"] = True
        else:
            if oponente_status != "Luz Verde":
                return "o oponente não está com 'Luz Verde'"
            updates[f"{oponente_path}.status"] = valor

        pass_turn = True

    # ============================================================
    # 3) CARTAS DE DEFESA
    # ============================================================
    elif tipo == "defesa":
        status = meu.get("status", "")
        limite = meu.get("limite", False)

        validacao_defesa = {
            "Luz Verde": "Luz Vermelha",
            "Conserto": "Acidente",
            "Estepe": "Pneu Furado",
            "Gasolina": "Sem Gasolina",
        }

        if valor == "Fim de Limite":
            if not limite:
                return "você não está com o Limite 50 km Ativo"
            updates[f"{caminho}.limite"] = False
        elif valor in validacao_defesa:
            status_requerido = validacao_defesa[valor]
            if status != status_requerido:
                return f"você está com '{status}' e não com '{status_requerido}'"
            updates[f"{caminho}.status"] = "Luz Verde"
        else:
            return "não foi possível determinar a regra de defesa"

        pass_turn = True

    # ============================================================
    # 4) CARTAS DE SEGURANÇA
    # ============================================================
    elif tipo == "segurança":
        segs = meu.get("safeties", [])
        if valor in segs:
            return "você já tem essa carta de segurança em jogo"

        segs.append(valor)
        updates[f"{caminho}.safeties"] = segs

        safety_responses = meu.get("safety_responses", 0)

        if valor == "Caminho Livre":
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

    # ============================================================
    # 5) PASSAR TURNO (casos normais)
    # ============================================================
    if pass_turn:
        updates["turn"] = proximo_turno

    sala_ref.update(updates)
    return True


def descartar_carta(sala_ref, estado_jogo, carta):
    meu = estado_jogo["meu"]
    mao_atual = meu.get("hand", []).copy()

    # 🔎 Busca segura por valor + tipo (e não pelo objeto)
    index_carta = next(
        (i for i, c in enumerate(mao_atual)
         if c.get("value") == carta.get("value") and c.get("type") == carta.get("type")),
        None
    )

    if index_carta is None:
        print("⚠️ Carta não encontrada para descarte (valor/tipo).")
        return

    # Remove corretamente
    mao_atual.pop(index_carta)

    caminho = estado_jogo["meu_caminho"]
    turno_atual = estado_jogo["turno"]
    proximo_turno = "player2" if turno_atual == "player1" else "player1"

    updates = {
        f"{caminho}.hand": mao_atual,
        "turn": proximo_turno,
        f"{caminho}.last_card_played": f'{carta["value"]} (descarte)'
    }

    sala_ref.update(updates)

    # Garante mão com 6 cartas
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
    """
    Calcula o placar da mão CORRETAMENTE, sempre usando
    o jogador que finalizou a mão como referência (finalizar=True).
    """

    # -----------------------------
    # 1) Identificar quem finalizou
    # -----------------------------
    if sala_data["player1"].get("finalizar", False):
        meu_caminho = "player1"
        oponente_caminho = "player2"
    else:
        meu_caminho = "player2"
        oponente_caminho = "player1"

    meu = sala_data.get(meu_caminho, {})
    oponente = sala_data.get(oponente_caminho, {})

    distance = meu.get("distance", 0)
    distance_op = oponente.get("distance", 0)

    winner = meu.get("winner", False)
    winner_op = oponente.get("winner", False)

    # -----------------------------------
    # 2) Bônus de extensão e fim de baralho
    # -----------------------------------
    extensao = meu.get("extensao", False)
    extensao_op = oponente.get("extensao", False)

    bonus_fim_baralho = 0
    bonus_fim_baralho_op = 0

    if mao_vazia and not winner and not winner_op:

        mao_meu = len(meu.get("hand", []))
        mao_op = len(oponente.get("hand", []))

        if mao_meu == 0 and mao_op > 0:
            bonus_fim_baralho = 300
        elif mao_op == 0 and mao_meu > 0:
            bonus_fim_baralho_op = 300

    # -------------------------
    # 3) Bonus de seguranças
    # -------------------------
    num_segurancas = len(meu.get("safeties", []))
    num_segurancas_op = len(oponente.get("safeties", []))

    bonus_segurancas_meu = num_segurancas * 100
    bonus_segurancas_op = num_segurancas_op * 100

    bonus_todas_segurancas_meu = 1000 if num_segurancas == 4 else 0
    bonus_todas_segurancas_op = 1000 if num_segurancas_op == 4 else 0

    # -----------------------------
    # 4) Coup fourré (300 cada)
    # -----------------------------
    total_safety_responses_meu = meu.get("safety_responses", 0)
    total_safety_responses_op = oponente.get("safety_responses", 0)

    # -----------------------------
    # 6) Bônus de vitória
    # -----------------------------
    bonus_vitoria = 400 if winner else 0
    bonus_vitoria_op = 400 if winner_op else 0

    # -----------------------------
    # 7) Bônus de ZERO km
    # -----------------------------
    bonus_zero_meu = (
        500 if distance == 1000 and distance_op == 0 else
        300 if distance == 700 and meu.get("sem_extensao", "N") == "N" and distance_op == 0 else
        0
    )

    bonus_zero_op = (
        500 if distance_op == 1000 and distance == 0 else
        300 if distance_op == 700 and oponente.get("sem_extensao", "N") == "N" and distance == 0 else
        0
    )

    # -----------------------------
    # 8) BONUS EXTENSÃO (300)
    # -----------------------------
    bonus_ext_meu = 300 if extensao else 0
    bonus_ext_op = 300 if extensao_op else 0

    # -------------------------------------------------
    # 9) MONTAR OBJETO DE PLACAR (meu e oponente)
    # -------------------------------------------------
    placar_meu = {
        "distancia": distance,
        "bonus_vitoria": bonus_vitoria,
        "bonus_segurancas": bonus_segurancas_meu,
        "bonus_todas_segurancas": bonus_todas_segurancas_meu,
        "total_coup_fourre": total_safety_responses_meu * 300,
        "bonus_zero": bonus_zero_meu,
        "oponente_zero": bonus_zero_op,
        "bonus_extensao": bonus_ext_meu,
        "fim_do_baralho": bonus_fim_baralho,
    }

    placar_meu["total_da_mao"] = sum(placar_meu.values())

    placar_op = {
        "distancia": distance_op,
        "bonus_vitoria": bonus_vitoria_op,
        "bonus_segurancas": bonus_segurancas_op,
        "bonus_todas_segurancas": bonus_todas_segurancas_op,
        "total_coup_fourre": total_safety_responses_op * 300,
        "bonus_zero": bonus_zero_op,
        "oponente_zero": bonus_zero_meu,
        "bonus_extensao": bonus_ext_op,
        "fim_do_baralho": bonus_fim_baralho_op,
    }

    placar_op["total_da_mao"] = sum(placar_op.values())

    # -----------------------------------------
    # 10) Atualizar total geral acumulado
    # -----------------------------------------
    total_geral_meu = meu.get("placar", {}).get("total_geral", 0) + placar_meu["total_da_mao"]
    total_geral_op = oponente.get("placar", {}).get("total_geral", 0) + placar_op["total_da_mao"]

    # -----------------------------------------
    # 11) Salvar no Firestore
    # -----------------------------------------
    updates = {
        f"{meu_caminho}.placar.atual_mao": placar_meu,
        f"{meu_caminho}.placar.total_geral": total_geral_meu,
        f"{meu_caminho}.placar_registrado": True,
        f"{meu_caminho}.placar_visto": False,

        f"{oponente_caminho}.placar.atual_mao": placar_op,
        f"{oponente_caminho}.placar.total_geral": total_geral_op,
        f"{oponente_caminho}.placar_registrado": True,
        f"{oponente_caminho}.placar_visto": False,

        "game_status": "finished",
    }

    sala_ref.update(updates)


def resetar_partida(sala_ref):
    """
    Reseta completamente a sala para uma nova partida do zero.
    Zera totais gerais e remove todos os estados prévios.
    """
    updates = {
        # Zera placar
        "player1.placar": {"total_geral": 0, "atual_mao": {}},
        "player2.placar": {"total_geral": 0, "atual_mao": {}},
        "player1.placar_registrado": False,
        "player2.placar_registrado": False,

        # Reset flags gerais
        "player1.finalizar": False,
        "player2.finalizar": False,
        "player1.winner": False,
        "player2.winner": False,
        "player1.extensao": False,
        "player2.extensao": False,
        "player1.aguardando_extensao": False,
        "player2.aguardando_extensao": False,

        # Estado base
        "player1.status": "Luz Verde",
        "player2.status": "Luz Verde",
        "player1.limite": False,
        "player2.limite": False,
        "player1.distance": 0,
        "player2.distance": 0,

        # Cartas e mesa
        "player1.hand": [],
        "player2.hand": [],
        "player1.safeties": [],
        "player2.safeties": [],
        "player1.safety_responses": 0,
        "player2.safety_responses": 0,

        # Novo deck será criado pelo distribuir_cartas()
        "deck": [],

        # Estado geral do jogo
        "turn": None,
        "game_status": "waiting_start",

        "player1.placar_visto": True,
        "player2.placar_visto": True,
    }

    sala_ref.update(updates)


def resetar_mao(sala_ref):
    """
    Limpa estados da mão anterior para começar outra sem perder o placar acumulado.
    """
    updates = {
        # Estado de jogo
        "game_status": "playing",
        "placar_calculado": False,
        "turn": "player1",   # jogador 1 SEMPRE começa a nova mão (regra do Mille Bornes)

        # Flags gerais
        "extensao_ativa": False,

        # Jogador 1
        "player1.finalizar": False,
        "player1.extensao": False,
        "player1.aguardando_extensao": False,
        "player1.status": "Luz Verde",
        "player1.limite": False,
        "player1.distance": 0,
        "player1.hand": [],
        "player1.safeties": [],
        "player1.safety_responses": 0,
        "player1.last_card_played": None,
        "player1.com_200": "N",
        "player1.placar_registrado": False,
        "player1.placar_visto": False,

        # Placar da mão (zerado)
        "player1.placar.atual_mao": {
            "distancia": 0,
            "segurancas": 0,
            "todas_segurancas": 0,
            "seguranca_em_resposta": 0,
            "percurso_completo": 0,
            "com_200": 0,
            "oponente_zero": 0,
            "bonus_extensao": 0,
            "fim_do_baralho": 0,
            "total_da_mao": 0,
        },

        # Jogador 2
        "player2.finalizar": False,
        "player2.extensao": False,
        "player2.aguardando_extensao": False,
        "player2.status": "Luz Verde",
        "player2.limite": False,
        "player2.distance": 0,
        "player2.hand": [],
        "player2.safeties": [],
        "player2.safety_responses": 0,
        "player2.last_card_played": None,
        "player2.com_200": "N",
        "player2.placar_registrado": False,
        "player2.placar_visto": False,

        "player2.placar.atual_mao": {
            "distancia": 0,
            "segurancas": 0,
            "todas_segurancas": 0,
            "seguranca_em_resposta": 0,
            "percurso_completo": 0,
            "com_200": 0,
            "oponente_zero": 0,
            "bonus_extensao": 0,
            "fim_do_baralho": 0,
            "total_da_mao": 0,
        },

        # Novo deck deve ser sobrescrito depois pelo jogo.py
        "deck": [],
    }

    sala_ref.update(updates)
