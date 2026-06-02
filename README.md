# apex-fopag

Painel mensal de folha de pagamento do Grupo Apex (APEX Engenharia + JR6 Empreendimentos + futuras empresas/obras).

## O que faz

Lê os relatórios analíticos da folha de cada empresa (PDF ou XLS do sistema do escritório, usuário "DEUSI"), normaliza, grava no Supabase, e mostra dashboards interativos por:

- **Grupo** — visão consolidada de todas as empresas
- **Empresa** — APEX, JR6 etc.
- **Obra** — junta funcionários de todas as empresas alocados na mesma obra (essencial pra Obra 204, que tem JR6 no canteiro + APEX na supervisão)
- **Departamento** — pros departamentos administrativos
- **Funcionário** — histórico individual
- **Comparativo Mensal** — variações mês a mês, admissões, demissões, alertas

## Stack

- **Streamlit** — app web (hospedado em Streamlit Community Cloud)
- **Supabase** — banco Postgres + storage dos arquivos originais
- **Python** — parser (pdfplumber + xlrd)
- **GitHub** — código versionado (repo privado)

## Setup

Veja `docs/DEPLOY.md` para o passo a passo completo. Resumo:

1. Criar projeto no Supabase (já feito).
2. Rodar `db/schema.sql` e `db/seed.sql` no SQL Editor do Supabase.
3. Fork/clone deste repo (privado).
4. Em `share.streamlit.io`, criar app apontando para o `app.py`.
5. Em "Settings → Secrets", colar:
   ```toml
   SUPABASE_URL = "https://xxx.supabase.co"
   SUPABASE_KEY = "service_role_key_aqui"
   ```
6. Em "Settings → Sharing", adicionar e-mails dos sócios.

## Como usar (mensalmente)

1. Abrir o app web (link Streamlit).
2. Tela "Carregar Folha" — fazer upload do `.xls` ou `.pdf` analítico do mês.
3. O app parseia, valida contra os cadastros, e grava no Supabase.
4. Navegar pelas visões.

## Como adicionar nova obra / empresa

Sem mexer em código. Tela "Cadastros" do app permite:

- Adicionar empresa (`cod_empresa`, `razao_social`, `cnpj`).
- Adicionar obra (`cod_obra`, `nome_obra`, `empresa_responsavel`).
- Adicionar departamento, cargo, rubrica.

Ou direto pelo Supabase Table Editor.

## Estrutura do repo

```
apex-fopag/
├── app.py                       # entrada do Streamlit (tela de Upload + Home)
├── pages/                       # subpáginas do Streamlit
│   ├── 1_Visao_Grupo.py
│   ├── 2_Visao_Empresa.py
│   ├── 3_Visao_Obra.py
│   ├── 4_Visao_Departamento.py
│   ├── 5_Visao_Funcionario.py
│   └── 6_Comparativo_Mensal.py
├── lib/
│   ├── db.py                    # client Supabase + queries
│   ├── parser_xls.py            # parser .xls analítico
│   ├── parser_pdf.py            # parser .pdf analítico
│   ├── normalizar.py            # padronização de dados
│   └── kpis.py                  # cálculos de KPIs
├── db/
│   ├── schema.sql               # criação das tabelas
│   └── seed.sql                 # cadastros iniciais
├── docs/
│   ├── ARQUITETURA.md
│   ├── DICIONARIO_DADOS.md
│   └── DEPLOY.md
├── .streamlit/
│   ├── config.toml
│   └── secrets.toml.example
├── requirements.txt
├── .gitignore
└── README.md
```

## Privacidade / LGPD

Os analíticos contêm CPF e PIS. Por isso:

- Repo é **privado** no GitHub.
- Arquivos de exemplo com CPF estão no `.gitignore` (`/uploads/`, `*.pdf`, `*.xls`).
- O Supabase é o único lugar onde CPF/PIS persistem. RLS (Row Level Security) restringe acesso ao service_role.
- Os dashboards mascaram CPF (mostram só os 3 primeiros dígitos) para qualquer usuário que não seja Admin.

## Licença

Uso interno do Grupo Apex.
