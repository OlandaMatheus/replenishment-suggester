"""
Roda o processo completo: carga -> view de sugestão -> exportação.

    python scripts/gerar_bases.py   # opcional: regera as bases fictícias
    python scripts/rodar.py

Saídas:
    sugestor.duckdb              banco para consultas manuais (fica fora do git)
    data/saida/sugestoes.csv     resultado no formato de planilha (; e vírgula decimal)
    data/saida/sugestoes.js      mesma base, embutida para a página index.html
"""
import csv
import json
import os
from datetime import date
from decimal import Decimal
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "data" / "saida"


def main():
    SAIDA.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(RAIZ / "sugestor.duckdb"))

    # PONTO CRÍTICO: os caminhos do SQL são relativos à raiz do projeto
    os.chdir(RAIZ)
    for arquivo in ("01_carga.sql", "02_sugestao.sql"):
        con.execute((RAIZ / "sql" / arquivo).read_text(encoding="utf-8"))
        print(f"ok  {arquivo}")

    # Ordem de prioridade: compra primeiro, depois o que está mais atrasado
    consulta = """
        SELECT * FROM base_sugestao
        ORDER BY CASE sugestao WHEN 'Compra' THEN 1 WHEN 'Transferência' THEN 2
                               WHEN 'Com pedido de compra' THEN 3 WHEN 'Transferência com PC' THEN 4
                               ELSE 5 END,
                 dias_atraso DESC, falta DESC
    """
    rel = con.execute(consulta)
    colunas = [c[0] for c in rel.description]
    linhas = [dict(zip(colunas, l)) for l in rel.fetchall()]

    # CSV no padrão brasileiro, para abrir direto no Excel.
    # PONTO CRÍTICO: o COPY do DuckDB não escreve vírgula decimal (DECIMAL_SEPARATOR
    # só vale na leitura). Com ponto decimal, o Excel em pt-BR leria "12.000" como doze mil.
    def br(v):
        if v is None:
            return ""
        if isinstance(v, Decimal):
            s = f"{v:f}"
            if "." in s:  # só tira zeros da parte decimal ("20.000" -> "20", nunca "20" -> "2")
                s = s.rstrip("0").rstrip(".")
            return s.replace(".", ",")
        if isinstance(v, date):
            return v.strftime("%d/%m/%Y")
        return str(v)

    with open(SAIDA / "sugestoes.csv", "w", newline="", encoding="utf-8-sig") as f:  # BOM: acentos certos no Excel
        w = csv.writer(f, delimiter=";")
        w.writerow(colunas)
        w.writerows([[br(l[c]) for c in colunas] for l in linhas])

    def conv(v):  # DECIMAL e DATE não são serializáveis em JSON
        if isinstance(v, Decimal):
            return float(v)
        if isinstance(v, date):
            return v.isoformat()
        return v

    data_ref, fator = con.execute("SELECT data_ref, fator_compra FROM parametros").fetchone()
    base = {"data_referencia": data_ref.isoformat(), "fator_compra": float(fator),
            "itens": [{k: conv(v) for k, v in l.items()} for l in linhas]}
    (SAIDA / "sugestoes.js").write_text(
        "// Gerado por scripts/rodar.py. Não editar à mão.\nwindow.BASE_SUGESTOES = "
        + json.dumps(base, ensure_ascii=False, indent=1) + ";\n", encoding="utf-8")

    resumo = con.execute("SELECT sugestao, COUNT(*), SUM(falta) FROM base_sugestao GROUP BY 1 ORDER BY 2 DESC").fetchall()
    print(f"\n{len(linhas)} materiais com demanda")
    for s, n, f in resumo:
        print(f"  {s:<22} {n:>3} materiais   falta {float(f):>7.0f}")
    con.close()


if __name__ == "__main__":
    main()
