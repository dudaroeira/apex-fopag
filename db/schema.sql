-- =====================================================================
-- apex-fopag — schema do banco no Supabase (Postgres)
-- Rodar este arquivo no SQL Editor do Supabase ANTES do seed.sql.
-- Idempotente: pode rodar de novo, recria tudo.
-- =====================================================================

-- Tudo no schema 'apex_fopag' para não poluir o public.
CREATE SCHEMA IF NOT EXISTS apex_fopag;
SET search_path = apex_fopag, public;

-- ---------------------------------------------------------------------
-- DIMENSÕES (cadastros) -----------------------------------------------
-- ---------------------------------------------------------------------

DROP TABLE IF EXISTS apex_fopag.eventos_folha   CASCADE;
DROP TABLE IF EXISTS apex_fopag.folha_mensal    CASCADE;
DROP TABLE IF EXISTS apex_fopag.ingestao_log    CASCADE;
DROP TABLE IF EXISTS apex_fopag.parametros      CASCADE;
DROP TABLE IF EXISTS apex_fopag.rubricas        CASCADE;
DROP TABLE IF EXISTS apex_fopag.cargos          CASCADE;
DROP TABLE IF EXISTS apex_fopag.departamentos   CASCADE;
DROP TABLE IF EXISTS apex_fopag.obras           CASCADE;
DROP TABLE IF EXISTS apex_fopag.empresas        CASCADE;

CREATE TABLE apex_fopag.empresas (
    cod_empresa     text PRIMARY KEY,
    razao_social    text NOT NULL,
    nome_curto      text NOT NULL,
    cnpj            text,
    grupo           text DEFAULT 'Grupo Apex',
    ativa           boolean DEFAULT true,
    criada_em       timestamptz DEFAULT now()
);

CREATE TABLE apex_fopag.obras (
    cod_obra                text PRIMARY KEY,
    nome_obra               text NOT NULL,
    cnpj_cno                text,
    empresa_responsavel     text REFERENCES apex_fopag.empresas(cod_empresa),
    apelido                 text,
    status                  text DEFAULT 'Em execução',
    data_inicio             date,
    data_fim_prevista       date,
    criada_em               timestamptz DEFAULT now()
);

CREATE TABLE apex_fopag.departamentos (
    cod_empresa         text REFERENCES apex_fopag.empresas(cod_empresa),
    cod_departamento    text NOT NULL,
    nome_departamento   text NOT NULL,
    tipo                text CHECK (tipo IN ('ADM','OPERACIONAL','GRUPO_ESPECIAL')) DEFAULT 'ADM',
    cod_obra_vinculada  text REFERENCES apex_fopag.obras(cod_obra),  -- ex.: APEX dep 28 → obra 204OB
    PRIMARY KEY (cod_empresa, cod_departamento)
);

CREATE TABLE apex_fopag.cargos (
    cod_cargo           text PRIMARY KEY,
    nome_cargo          text NOT NULL,
    nivel               text CHECK (nivel IN
        ('Aprendiz','Servente','Meio Oficial','Oficial','Especializado',
         'Apoio','Encarregado','Contramestre','Admin','Diretoria')),
    categoria           text CHECK (categoria IN ('Operacional','Administrativo')) DEFAULT 'Operacional',
    demanda_aprendiz    boolean DEFAULT false   -- conta na base da Lei do Aprendiz
);

CREATE TABLE apex_fopag.rubricas (
    cod_rubrica     text PRIMARY KEY,
    descricao       text NOT NULL,
    tipo            text CHECK (tipo IN ('PROVENTO','DESCONTO')) NOT NULL,
    grupo           text,
    incide_inss     boolean DEFAULT false,
    incide_fgts     boolean DEFAULT false,
    incide_irrf     boolean DEFAULT false
);

CREATE TABLE apex_fopag.parametros (
    parametro       text PRIMARY KEY,
    valor           numeric NOT NULL,
    unidade         text,
    comentario      text
);

-- ---------------------------------------------------------------------
-- FATOS (crescem todo mês) --------------------------------------------
-- ---------------------------------------------------------------------

CREATE TABLE apex_fopag.folha_mensal (
    id                  bigserial PRIMARY KEY,
    mes_ref             text NOT NULL,         -- 'AAAA-MM'
    cod_empresa         text NOT NULL REFERENCES apex_fopag.empresas(cod_empresa),
    matricula           text NOT NULL,
    nome                text,
    cpf                 text,
    pis                 text,
    nascimento          date,
    dt_admissao         date,
    dt_demissao         date,
    situacao            text,
    cod_departamento    text,
    cod_obra            text REFERENCES apex_fopag.obras(cod_obra),
    cod_cargo           text REFERENCES apex_fopag.cargos(cod_cargo),
    cod_funcao          text,
    salario_base        numeric(12,2),
    proventos_total     numeric(12,2),
    descontos_total     numeric(12,2),
    liquido             numeric(12,2),
    base_inss           numeric(12,2),
    base_fgts           numeric(12,2),
    fgts                numeric(12,2),
    base_irrf           numeric(12,2),
    dependentes_ir      integer,
    arquivo_origem      text,
    data_ingestao       timestamptz DEFAULT now(),
    UNIQUE (mes_ref, cod_empresa, matricula)
);
CREATE INDEX idx_folha_mes_ref      ON apex_fopag.folha_mensal(mes_ref);
CREATE INDEX idx_folha_empresa      ON apex_fopag.folha_mensal(cod_empresa);
CREATE INDEX idx_folha_obra         ON apex_fopag.folha_mensal(cod_obra);
CREATE INDEX idx_folha_situacao     ON apex_fopag.folha_mensal(situacao);

CREATE TABLE apex_fopag.eventos_folha (
    id              bigserial PRIMARY KEY,
    mes_ref         text NOT NULL,
    cod_empresa     text NOT NULL,
    matricula       text NOT NULL,
    tipo            text CHECK (tipo IN ('PROVENTO','DESCONTO')),
    cod_rubrica     text,
    descricao       text,
    quantidade      numeric(12,4),
    valor           numeric(12,2),
    FOREIGN KEY (mes_ref, cod_empresa, matricula)
        REFERENCES apex_fopag.folha_mensal(mes_ref, cod_empresa, matricula) ON DELETE CASCADE
);
CREATE INDEX idx_eventos_chave ON apex_fopag.eventos_folha(mes_ref, cod_empresa, matricula);
CREATE INDEX idx_eventos_rubrica ON apex_fopag.eventos_folha(cod_rubrica);

CREATE TABLE apex_fopag.ingestao_log (
    id                  bigserial PRIMARY KEY,
    data_ingestao       timestamptz DEFAULT now(),
    arquivo             text,
    cod_empresa         text,
    mes_ref             text,
    linhas_inseridas    integer DEFAULT 0,
    linhas_atualizadas  integer DEFAULT 0,
    status              text,
    observacao          text
);

-- ---------------------------------------------------------------------
-- VIEWS (consumidas pelo dashboard) -----------------------------------
-- ---------------------------------------------------------------------

-- Visão "Obra consolidada": junta funcionários de qualquer empresa
-- cuja cod_obra (na folha_mensal) ou cuja departamento.cod_obra_vinculada
-- aponte para a obra em questão.
CREATE OR REPLACE VIEW apex_fopag.v_folha_por_obra AS
SELECT
    f.id, f.mes_ref, f.cod_empresa,
    COALESCE(
        f.cod_obra,
        d.cod_obra_vinculada
    ) AS cod_obra_efetivo,
    f.matricula, f.nome, f.cpf, f.situacao,
    f.cod_cargo, f.cod_departamento,
    f.salario_base, f.proventos_total, f.liquido, f.dt_admissao, f.dt_demissao
FROM apex_fopag.folha_mensal f
LEFT JOIN apex_fopag.departamentos d
       ON d.cod_empresa = f.cod_empresa AND d.cod_departamento = f.cod_departamento;

-- KPIs por mês × empresa (alimenta a Visao_Grupo e Visao_Empresa)
CREATE OR REPLACE VIEW apex_fopag.v_kpi_mes_empresa AS
SELECT
    mes_ref,
    cod_empresa,
    COUNT(*)                                                           AS headcount_total,
    COUNT(*) FILTER (WHERE situacao = 'Ativo')                         AS ativos,
    COUNT(*) FILTER (WHERE situacao IN ('Doente','Licenciado','Em'))   AS inativos,
    SUM(proventos_total)                                               AS proventos,
    SUM(liquido)                                                       AS liquido,
    SUM(fgts)                                                          AS fgts,
    AVG(salario_base) FILTER (WHERE salario_base > 0)                  AS salario_base_medio,
    COUNT(*) FILTER (WHERE dt_admissao::text LIKE mes_ref || '%')      AS admissoes_mes,
    COUNT(*) FILTER (WHERE dt_demissao::text LIKE mes_ref || '%')      AS demissoes_mes
FROM apex_fopag.folha_mensal
GROUP BY mes_ref, cod_empresa;

-- KPIs por obra (já consolidando empresas)
CREATE OR REPLACE VIEW apex_fopag.v_kpi_mes_obra AS
SELECT
    mes_ref,
    cod_obra_efetivo AS cod_obra,
    COUNT(*)                                                           AS headcount_total,
    COUNT(*) FILTER (WHERE situacao = 'Ativo')                         AS ativos,
    COUNT(*) FILTER (WHERE situacao IN ('Doente','Licenciado','Em'))   AS inativos,
    SUM(proventos_total)                                               AS proventos,
    AVG(salario_base) FILTER (WHERE salario_base > 0)                  AS salario_base_medio
FROM apex_fopag.v_folha_por_obra
WHERE cod_obra_efetivo IS NOT NULL
GROUP BY mes_ref, cod_obra_efetivo;

-- ---------------------------------------------------------------------
-- RLS (row level security) — sócios só leem -----------------------------
-- ---------------------------------------------------------------------

ALTER TABLE apex_fopag.empresas       ENABLE ROW LEVEL SECURITY;
ALTER TABLE apex_fopag.obras          ENABLE ROW LEVEL SECURITY;
ALTER TABLE apex_fopag.departamentos  ENABLE ROW LEVEL SECURITY;
ALTER TABLE apex_fopag.cargos         ENABLE ROW LEVEL SECURITY;
ALTER TABLE apex_fopag.rubricas       ENABLE ROW LEVEL SECURITY;
ALTER TABLE apex_fopag.parametros     ENABLE ROW LEVEL SECURITY;
ALTER TABLE apex_fopag.folha_mensal   ENABLE ROW LEVEL SECURITY;
ALTER TABLE apex_fopag.eventos_folha  ENABLE ROW LEVEL SECURITY;
ALTER TABLE apex_fopag.ingestao_log   ENABLE ROW LEVEL SECURITY;

-- Política: service_role pode tudo (o app usa service_role nas secrets).
-- anon e authenticated não vêm nada (acesso só pelo app).
-- Se no futuro for usar Supabase Auth pros sócios, ajustar aqui.

GRANT USAGE ON SCHEMA apex_fopag TO postgres, service_role;
GRANT ALL   ON ALL TABLES IN SCHEMA apex_fopag TO postgres, service_role;
GRANT ALL   ON ALL SEQUENCES IN SCHEMA apex_fopag TO postgres, service_role;
