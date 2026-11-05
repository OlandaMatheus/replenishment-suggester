"""
Gera as bases fictícias do replenishment-suggester, no formato típico de extração de ERP.

Saídas em data/entrada/:
    materiais.csv        cadastro de materiais
    estoque.csv          estoque livre por centro (CD01 = Depósito Central, FL01 = Filial)
    pedidos_compra.csv   pedidos de compra em aberto por centro
    carteira.csv         itens de pedido de venda em aberto na filial (a demanda)
    faturamento.csv      quantidade faturada por mês, últimos 12 meses

Formato "de ERP", de propósito:
    - separador ";" e vírgula decimal ("1.234,000")
    - datas "dd.mm.aaaa"
    - códigos de material com zeros à esquerda (18 posições)
    - alguns itens da carteira exportados em duplicidade (tratado no SQL)

PONTO CRÍTICO: semente e data de referência fixas. Rodar de novo gera exatamente
a mesma base, então os números da página e do README sempre batem.
"""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

SEMENTE = 42
DATA_REF = date(2026, 11, 4)
SAIDA = Path(__file__).resolve().parent.parent / "data" / "entrada"

random.seed(SEMENTE)

# ---------------------------------------------------------------------------
# Formatação no padrão de extração
# ---------------------------------------------------------------------------
def num_br(v, casas=3):
    """1234.5 -> '1.234,500' (milhar com ponto, decimal com vírgula)."""
    s = f"{v:,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")

def data_br(d):
    return d.strftime("%d.%m.%Y")

def cod_material(n):
    return str(n).zfill(18)

def gravar(nome, cabecalho, linhas):
    SAIDA.mkdir(parents=True, exist_ok=True)
    with open(SAIDA / nome, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(cabecalho)
        w.writerows(linhas)
    print(f"{nome:<20} {len(linhas):>4} linhas")

# ---------------------------------------------------------------------------
# Cadastro de materiais (distribuidora fictícia de informática e eletrônicos)
# Unidades misturadas de propósito (UN, CX, RL): os totais da página não podem somar quantidades.
# ---------------------------------------------------------------------------
# Produto completo por linha (nome + especificação já casados), para não gerar combinações sem sentido
CATALOGO = {
    "Periféricos": ("UN", ["Mouse sem fio básico", "Mouse sem fio ergonômico", "Mouse óptico USB", "Teclado USB ABNT2",
                           "Teclado sem fio compacto", "Kit teclado e mouse sem fio", "Headset USB com microfone",
                           "Webcam Full HD", "Mousepad com apoio de punho", "Suporte para notebook"]),
    "Armazenamento": ("UN", ["SSD SATA 240 GB", "SSD SATA 480 GB", "SSD NVMe 512 GB", "SSD NVMe 1 TB",
                             "Pen drive 32 GB", "Pen drive 64 GB", "Pen drive 128 GB", "HD externo 1 TB",
                             "HD externo 2 TB", "Cartão microSD 64 GB"]),
    "Redes": ("RL", ["Cabo de rede Cat5e azul 305 m", "Cabo de rede Cat5e cinza 305 m", "Cabo de rede Cat6 azul 305 m",
                     "Cabo de rede Cat6 cinza 305 m", "Cabo de rede Cat6 externo 305 m", "Cabo coaxial RG6 100 m"]),
    "Redes e conectividade": ("UN", ["Roteador Wi-Fi dual band", "Switch 8 portas gigabit", "Switch 16 portas gigabit",
                                     "Repetidor Wi-Fi", "Adaptador Wi-Fi USB", "Conector RJ45 Cat6 (pacote 100)"]),
    "Energia": ("UN", ["Nobreak 600 VA", "Nobreak 1200 VA", "Filtro de linha 5 tomadas", "Filtro de linha 8 tomadas",
                       "Fonte para notebook 65 W", "Fonte para notebook 90 W", "Estabilizador 500 VA", "Carregador USB-C 20 W"]),
    "Impressão": ("CX", ["Papel A4 75 g (caixa 10 resmas)", "Toner preto alto rendimento", "Toner preto padrão",
                         "Cartucho de tinta preto", "Cartucho de tinta colorido", "Etiqueta adesiva A4 (caixa 100 folhas)",
                         "Papel fotográfico A4 (caixa 50 folhas)", "Fita para impressora térmica"]),
    "Cabos e adaptadores": ("UN", ["Cabo HDMI 1,8 m", "Cabo HDMI 3 m", "Cabo USB-C 1 m", "Cabo USB-C para Lightning 1 m",
                                   "Adaptador USB-C para HDMI", "Adaptador HDMI para VGA", "Hub USB 4 portas",
                                   "Hub USB-C 7 em 1", "Extensor USB 3 m", "Cabo DisplayPort 2 m"]),
}

materiais = []
n = 830_000
for categoria, (unidade, produtos) in CATALOGO.items():
    for descricao in produtos:
        n += random.randint(3, 40)
        materiais.append({"codigo": cod_material(n), "descricao": descricao,
                          "unidade": unidade, "categoria": categoria})

gravar("materiais.csv", ["Material", "Descricao", "Unidade", "Categoria"],
       [[m["codigo"], m["descricao"], m["unidade"], m["categoria"]] for m in materiais])

# ---------------------------------------------------------------------------
# Cenários: cada material com demanda recebe um cenário planejado, e o estoque
# e os pedidos de compra são montados para que a regra do SQL caia nele.
# Assim a demo mostra os 5 tipos de sugestão com proporções realistas.
# ---------------------------------------------------------------------------
CENARIOS = [  # (cenário, peso)
    ("estoque_filial", 30),   # filial tem estoque para tudo
    ("pc_cd", 12),            # falta na filial, CD tem PC que cobre
    ("pc_filial", 16),        # falta na filial, a própria filial tem PC
    ("estoque_cd", 14),       # falta na filial, CD tem estoque (sem PC)
    ("compra", 13),           # ninguém cobre
    ("parcial", 6),           # cobertura parcial em todos: também vira compra
]
com_demanda = random.sample(materiais, k=int(len(materiais) * 0.8))
nomes_c, pesos_c = zip(*CENARIOS)

CLIENTES = ["Colégio Monte Sião", "Clínica Bem Viver", "Escritório Lima & Prado", "Faculdade Horizonte",
            "Coworking Ponto Zero", "Prefeitura de Vila Nova", "Hotel Recanto Azul", "Laboratório Alfa Vida",
            "Imobiliária Casa Certa", "Agência Pixel Norte", "Cartório 2º Ofício", "Livraria Página Um"]

carteira, estoque, pedidos, faturamento = [], [], [], []
ordem, pedido_compra = 80_310_000, 4_700_520_000

for m in materiais:
    cod = m["codigo"]
    tem_demanda = m in com_demanda
    cenario = random.choices(nomes_c, pesos_c)[0] if tem_demanda else None

    # --- Demanda: 1 a 4 itens de pedido de venda em aberto na filial ---
    demanda = 0
    if tem_demanda:
        for _ in range(random.randint(1, 4)):
            ordem += random.randint(1, 9)
            qtd = random.choice([1, 2, 3, 5, 6, 10, 12, 20, 30])
            demanda += qtd
            # Prazo de entrega prometido: a maioria ainda no futuro, uma parte já vencida
            dt_ped = DATA_REF - timedelta(days=random.randint(1, 35))
            dt_rem = dt_ped + timedelta(days=random.choice([15, 20, 30, 30, 45, 60]))
            linha = [str(ordem), "10", random.choice(CLIENTES), cod, num_br(qtd), m["unidade"],
                     data_br(dt_ped), data_br(dt_rem)]
            carteira.append(linha)
            # ~6% dos itens saem duplicados na extração (o SQL consolida)
            if random.random() < 0.06:
                carteira.append(list(linha))

    # --- Estoque e PCs conforme o cenário ---
    est_fil, est_cd, pc_fil, pc_cd = 0, 0, 0, 0
    if not tem_demanda:
        est_fil = random.choice([0, 0, 5, 10, 30])
        est_cd = random.choice([0, 20, 50, 100])
    elif cenario == "estoque_filial":
        est_fil = demanda + random.randint(0, 30)
        est_cd = random.choice([0, 20, 60])
    else:
        est_fil = random.randint(0, max(demanda // 2, 0))   # filial não cobre
        falta = demanda - est_fil
        if cenario == "pc_cd":
            pc_cd = falta + random.randint(0, 20)
            pc_fil = random.choice([0, 0, falta // 3])
        elif cenario == "pc_filial":
            pc_fil = falta + random.randint(0, 15)
        elif cenario == "estoque_cd":
            est_cd = falta + random.randint(0, 40)
        elif cenario == "parcial":
            est_cd = falta // 3
            pc_fil = falta // 4
            pc_cd = falta // 4
        # "compra": nada cobre

    for centro, qtd in (("FL01", est_fil), ("CD01", est_cd)):
        if qtd:
            estoque.append([centro, cod, num_br(qtd), m["unidade"]])

    for centro, qtd in (("FL01", pc_fil), ("CD01", pc_cd)):
        if qtd:
            pedido_compra += random.randint(1, 15)
            remessa = DATA_REF + timedelta(days=random.randint(3, 40))
            pedidos.append([str(pedido_compra), "10", centro, cod, num_br(qtd), m["unidade"], data_br(remessa)])

    # --- Faturamento dos últimos 12 meses na filial (base da quantidade de compra) ---
    giro = random.choice([0, 2, 5, 8, 15, 30, 60]) if tem_demanda else random.choice([0, 0, 3, 10])
    for k in range(1, 13):
        mes = (DATA_REF.replace(day=1) - timedelta(days=1 + 31 * (k - 1))).replace(day=1)
        qtd = max(0, round(random.gauss(giro, giro * 0.35)))
        if qtd:
            faturamento.append(["FL01", cod, mes.strftime("%Y%m"), num_br(qtd)])

random.shuffle(carteira)
gravar("carteira.csv", ["Ordem_Venda", "Item", "Cliente", "Material", "Qtd_Pendente", "Unidade",
                        "Data_Pedido", "Data_Remessa"], carteira)
gravar("estoque.csv", ["Centro", "Material", "Estoque_Livre", "Unidade"], estoque)
gravar("pedidos_compra.csv", ["Pedido", "Item", "Centro", "Material", "Qtd_Pendente", "Unidade",
                              "Data_Remessa"], pedidos)
gravar("faturamento.csv", ["Centro", "Material", "Mes", "Qtd_Faturada"], faturamento)
print(f"Data de referência: {DATA_REF:%d/%m/%Y}")
