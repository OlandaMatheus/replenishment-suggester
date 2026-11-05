-- =============================================================================
-- 01_carga.sql
-- Lê os CSVs de extração e grava tabelas já tipadas e padronizadas.
--
-- Tudo é lido como texto (all_varchar) e convertido aqui, de forma explícita:
--   - códigos de material sem zeros à esquerda (chave de cruzamento entre bases)
--   - números "1.234,500" -> DECIMAL
--   - datas "dd.mm.aaaa" -> DATE
-- PONTO CRÍTICO: deixar o DuckDB adivinhar os tipos leria "000000000000830148"
-- como número (perde os zeros, e códigos longos podem estourar) e "10,000" como texto.
-- =============================================================================

-- Converte texto numérico pt-BR em DECIMAL: tira o ponto de milhar e troca a vírgula
CREATE OR REPLACE MACRO num_br(t) AS
    CAST(REPLACE(REPLACE(TRIM(t), '.', ''), ',', '.') AS DECIMAL(15, 3));

-- Remove zeros à esquerda; código só de zeros vira '0' em vez de texto vazio
CREATE OR REPLACE MACRO cod(t) AS
    COALESCE(NULLIF(LTRIM(TRIM(t), '0'), ''), '0');

CREATE OR REPLACE TABLE materiais AS
SELECT cod(Material)   AS material,
       Descricao       AS descricao,
       Unidade         AS unidade,
       Categoria       AS categoria
FROM read_csv('data/entrada/materiais.csv', delim = ';', header = true, all_varchar = true);

CREATE OR REPLACE TABLE estoque AS
SELECT Centro                AS centro,
       cod(Material)         AS material,
       num_br(Estoque_Livre) AS estoque_livre
FROM read_csv('data/entrada/estoque.csv', delim = ';', header = true, all_varchar = true);

CREATE OR REPLACE TABLE pedidos_compra AS
SELECT Pedido                                AS pedido,
       Item                                  AS item,
       Centro                                AS centro,
       cod(Material)                         AS material,
       num_br(Qtd_Pendente)                  AS qtd_pendente,
       strptime(Data_Remessa, '%d.%m.%Y')::DATE AS data_remessa
FROM read_csv('data/entrada/pedidos_compra.csv', delim = ';', header = true, all_varchar = true);

-- Carteira: a extração às vezes traz o mesmo item de pedido duas vezes.
-- QUALIFY mantém uma linha por (ordem, item); sem isso a demanda sairia inflada.
CREATE OR REPLACE TABLE carteira AS
SELECT Ordem_Venda                              AS ordem_venda,
       Item                                     AS item,
       Cliente                                  AS cliente,
       cod(Material)                            AS material,
       num_br(Qtd_Pendente)                     AS qtd_pendente,
       strptime(Data_Pedido, '%d.%m.%Y')::DATE  AS data_pedido,
       strptime(Data_Remessa, '%d.%m.%Y')::DATE AS data_remessa
FROM read_csv('data/entrada/carteira.csv', delim = ';', header = true, all_varchar = true)
QUALIFY ROW_NUMBER() OVER (PARTITION BY Ordem_Venda, Item ORDER BY Data_Pedido) = 1;

CREATE OR REPLACE TABLE faturamento AS
SELECT Centro                                     AS centro,
       cod(Material)                              AS material,
       strptime(Mes || '01', '%Y%m%d')::DATE      AS mes,
       num_br(Qtd_Faturada)                       AS qtd_faturada
FROM read_csv('data/entrada/faturamento.csv', delim = ';', header = true, all_varchar = true);
