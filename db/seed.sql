-- =====================================================================
-- apex-fopag — seed dos cadastros iniciais
-- Rodar DEPOIS do schema.sql. Idempotente (usa ON CONFLICT DO NOTHING).
-- =====================================================================

SET search_path = apex_fopag, public;

-- Empresas
INSERT INTO empresas (cod_empresa, razao_social, nome_curto, cnpj) VALUES
('1',  'APEX ENGENHARIA COMERCIO E INDUSTRIA LTDA', 'APEX', '00.472.399/0001-03'),
('52', 'JR6 EMPREENDIMENTOS IMOBILIARIOS LTDA',     'JR6',  '38.412.080/0001-65')
ON CONFLICT (cod_empresa) DO NOTHING;

-- Obras
INSERT INTO obras (cod_obra, nome_obra, cnpj_cno, empresa_responsavel, apelido, status) VALUES
('1AD',    'ADMINISTRACAO APEX ENGENHARIA',  NULL,                  '1',  'Adm APEX',  'Ativo'),
('204OB',  'OBRA SQNW 104 BLOCO F',          '90.020.519-20/75',    '52', 'Obra 204',  'Em execução'),
('JAX28',  'JAX 28',                          NULL,                  '1',  'JAX 28',    'Em execução'),
('OBRA99', 'OBRA 99',                         NULL,                  '1',  'Obra 99',   'Em execução'),
('REPARO', 'REPARO',                          NULL,                  '1',  'Reparo',    'Ativo')
ON CONFLICT (cod_obra) DO NOTHING;

-- Departamentos APEX
-- O cod_obra_vinculada é o que faz a "magia" da Visao_Obra:
-- APEX dep 28 conta na Obra 204OB; APEX dep 16 conta na JAX28; etc.
INSERT INTO departamentos (cod_empresa, cod_departamento, nome_departamento, tipo, cod_obra_vinculada) VALUES
('1','02','FINANCEIRO - ADM',           'ADM',             NULL),
('1','03','JURIDICO - ADM',             'ADM',             NULL),
('1','04','RECURSOS HUMANOS - ADM',     'ADM',             NULL),
('1','08','CONTABILIDADE - ADM',        'ADM',             NULL),
('1','09','COMPRAS - ADM',              'ADM',             NULL),
('1','11','ALMOXARIFADO CENTRAL - ADM', 'ADM',             NULL),
('1','12','RECEPÇÃO - ADM',             'ADM',             NULL),
('1','13','SERVIÇOS GERAIS - ADM',      'ADM',             NULL),
('1','15','PROJETOS/QUALIDADE - ADM',   'ADM',             NULL),
('1','16','JAX 28',                     'OPERACIONAL',     'JAX28'),
('1','17','SECRETARIA DE VENDAS - ADM', 'ADM',             NULL),
('1','19','ATENDIMENTO AO CLIENTE - ADM','ADM',            NULL),
('1','21','REPARO',                     'OPERACIONAL',     'REPARO'),
('1','22','OBRA 99',                    'OPERACIONAL',     'OBRA99'),
('1','25','AFASTADOS',                  'GRUPO_ESPECIAL',  NULL),
('1','27','DIRETORIA',                  'ADM',             NULL),
('1','28','OBRA 204 - JR6',             'OPERACIONAL',     '204OB')
ON CONFLICT (cod_empresa, cod_departamento) DO NOTHING;

-- Cargos
INSERT INTO cargos (cod_cargo, nome_cargo, nivel, categoria, demanda_aprendiz) VALUES
('21',  'PEDREIRO',                    'Oficial',       'Operacional', true),
('22',  'SERVENTE',                    'Servente',      'Operacional', false),
('23',  'LADRILHEIRO',                 'Oficial',       'Operacional', true),
('24',  'ELETRICISTA',                 'Oficial',       'Operacional', true),
('25',  'BOMBEIRO HIDRAULICO',         'Oficial',       'Operacional', true),
('28',  'CARPINTEIRO',                 'Oficial',       'Operacional', true),
('36',  'SINALEIRO',                   'Especializado', 'Operacional', true),
('42',  'OPERADOR DE CREMALHEIRA',     'Especializado', 'Operacional', true),
('43',  'GUARDIAO DE OBRAS',           'Apoio',         'Operacional', false),
('45',  'OPERADOR DE GRUA NIVEL II',   'Especializado', 'Operacional', true),
('65',  'APRENDIZ',                    'Aprendiz',      'Operacional', false),
('84',  'AUXILIAR ALMOXARIFE I',       'Apoio',         'Operacional', false),
('133', 'MEIO OFICIAL DE CARPINTEIRO', 'Meio Oficial',  'Operacional', true)
ON CONFLICT (cod_cargo) DO NOTHING;

-- Rubricas
INSERT INTO rubricas (cod_rubrica, descricao, tipo, grupo, incide_inss, incide_fgts, incide_irrf) VALUES
('100', 'Dia de Salário para Férias','PROVENTO','Férias',     true, true, true),
('101', 'Salário Base',              'PROVENTO','Salário',    true, true, true),
('132', 'Trienio 20%',               'PROVENTO','Adicional',  true, true, true),
('170', 'Gozo de Licença',           'DESCONTO','Outro',      false, false, false),
('906', 'Ajuste Atual Prov.',        'PROVENTO','Ajuste',     true, true, true),
('917', 'Ajuste Anterior Desc.',     'DESCONTO','Ajuste',     false, false, false),
('935', 'INSS',                      'DESCONTO','INSS',       false, false, false),
('1000','Refeição',                  'DESCONTO','Benefício',  false, false, false),
('1002','Vale Transporte',           'PROVENTO','Benefício',  false, false, false)
ON CONFLICT (cod_rubrica) DO NOTHING;

-- Parâmetros
INSERT INTO parametros (parametro, valor, unidade, comentario) VALUES
('encargos_obra_pct',      0.33, '%', 'INSS patronal + RAT + FGTS + FAP + SECONCI + 13/férias provisionado'),
('encargos_admin_pct',     0.30, '%', 'Encargos sobre folha administrativa'),
('provisao_13_ferias_pct', 0.17, '%', '13º + 1/3 férias provisionado'),
('meta_aprendiz_min_pct',  0.05, '%', 'Lei do Aprendiz — piso legal'),
('meta_aprendiz_max_pct',  0.15, '%', 'Lei do Aprendiz — teto legal'),
('meta_inativos_max_pct',  0.15, '%', 'Acima disso, dashboard sinaliza alerta vermelho'),
('meta_turnover_max_pct',  0.05, '%', 'Turnover mensal de referência')
ON CONFLICT (parametro) DO NOTHING;
