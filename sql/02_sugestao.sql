-- =============================================================================
-- 02_sugestao.sql
-- Para cada material com demanda em aberto na filial (FL01), decide de onde
-- deve vir o atendimento e quanto comprar quando ninguém cobre.
--
-- Cascata de decisão (a ordem importa: a primeira regra verdadeira vence)
--   1. Com estoque            estoque da filial cobre a demanda
--   2. Transferência com PC   o Depósito Central (CD01) tem PC que cobre a falta
--   3. Com pedido de compra   a própria filial tem PC que cobre a falta
--   4. Transferência          o CD01 tem estoque que cobre a falta (sem PC)
--   5. Compra                 nenhuma das anteriores
--
-- Por que o PC do CD vem antes do PC da filial: o CD compra em volume e já
-- abastece a filial na rota normal; usar o PC dele evita duas compras do mesmo item.
-- =============================================================================

-- Parâmetros gravados em tabela (e não em SET VARIABLE): variável vale só na sessão,
-- e a view quebraria ao reabrir o banco para uma consulta manual.
--   data_ref      data de corte da extração. Não usar CURRENT_DATE: o resultado tem
--                 que bater com a base, mesmo se o processo rodar de novo outro dia.
--   fator_compra  política de compra: 30% do faturamento de 12 meses (~3,6 meses de giro)
CREATE OR REPLACE TABLE parametros AS
SELECT DATE '2026-11-04' AS data_ref, 0.30::DECIMAL(5, 2) AS fator_compra;

CREATE OR REPLACE VIEW base_sugestao AS
WITH
par AS (SELECT * FROM parametros),
demanda AS (
    SELECT material,
           SUM(qtd_pendente)         AS demanda,
           COUNT(*)                  AS itens_ov,
           COUNT(DISTINCT cliente)   AS clientes,
           MIN(data_remessa)         AS remessa_mais_antiga
    FROM carteira
    GROUP BY material
),
-- PIVOT manual de estoque e PCs por centro: uma linha por material
estoque_centro AS (
    SELECT material,
           SUM(estoque_livre) FILTER (WHERE centro = 'FL01') AS est_filial,
           SUM(estoque_livre) FILTER (WHERE centro = 'CD01') AS est_cd
    FROM estoque
    GROUP BY material
),
pc_centro AS (
    SELECT material,
           SUM(qtd_pendente) FILTER (WHERE centro = 'FL01') AS pc_filial,
           SUM(qtd_pendente) FILTER (WHERE centro = 'CD01') AS pc_cd,
           MIN(data_remessa) FILTER (WHERE centro = 'FL01') AS remessa_pc_filial,
           MIN(data_remessa) FILTER (WHERE centro = 'CD01') AS remessa_pc_cd
    FROM pedidos_compra
    GROUP BY material
),
giro AS (
    -- 12 meses fechados antes do mês da data de corte (o mês corrente ainda está aberto)
    SELECT f.material, SUM(f.qtd_faturada) AS fat_12m
    FROM faturamento f, par
    WHERE f.centro = 'FL01'
      AND f.mes >= date_trunc('month', par.data_ref) - INTERVAL 12 MONTH
      AND f.mes <  date_trunc('month', par.data_ref)
    GROUP BY f.material
),
consolidado AS (
    -- LEFT JOIN a partir da demanda: material sem estoque/PC/giro entra com zero
    SELECT d.*,
           m.descricao, m.unidade, m.categoria,
           COALESCE(e.est_filial, 0) AS est_filial,
           COALESCE(e.est_cd, 0)     AS est_cd,
           COALESCE(p.pc_filial, 0)  AS pc_filial,
           COALESCE(p.pc_cd, 0)      AS pc_cd,
           p.remessa_pc_filial, p.remessa_pc_cd,
           COALESCE(g.fat_12m, 0)    AS fat_12m,
           GREATEST(d.demanda - COALESCE(e.est_filial, 0), 0) AS falta
    FROM demanda d
    LEFT JOIN materiais      m USING (material)
    LEFT JOIN estoque_centro e USING (material)
    LEFT JOIN pc_centro      p USING (material)
    LEFT JOIN giro           g USING (material)
),
classificado AS (
    SELECT *,
           CASE
               WHEN falta = 0        THEN 'Com estoque'
               WHEN pc_cd     >= falta THEN 'Transferência com PC'
               WHEN pc_filial >= falta THEN 'Com pedido de compra'
               WHEN est_cd    >= falta THEN 'Transferência'
               ELSE 'Compra'
           END AS sugestao
    FROM consolidado
)
SELECT
    material, descricao, categoria, unidade,
    sugestao,
    demanda, est_filial, falta,
    est_cd, pc_filial, pc_cd,
    itens_ov, clientes, remessa_mais_antiga,
    -- Atraso: remessa prometida ao cliente já passou da data de corte
    GREATEST(par.data_ref - remessa_mais_antiga, 0) AS dias_atraso,
    -- Previsão de chegada só faz sentido para os tipos que dependem de PC
    CASE sugestao
        WHEN 'Transferência com PC' THEN remessa_pc_cd
        WHEN 'Com pedido de compra' THEN remessa_pc_filial
    END AS previsao_pc,
    fat_12m,
    -- Compra: política de giro, mas nunca menos do que a falta da carteira.
    -- CEIL porque não se compra fração de peça.
    CASE WHEN sugestao = 'Compra'
         THEN GREATEST(falta, CEIL(fat_12m * par.fator_compra))
    END AS qtd_compra
FROM classificado, par;
