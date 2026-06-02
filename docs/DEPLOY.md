# Deploy — apex-fopag

Passo a passo do que precisa acontecer entre o repo local e o app no ar para os socios.

## Visao geral

```
local (este repo)  ->  GitHub privado  ->  Streamlit Community Cloud  ->  socios via link
                                       \-> Supabase (Postgres + storage)
```

Tres servicos, todos no nivel gratuito: GitHub, Streamlit Cloud, Supabase.

## 1. GitHub — criar repo privado

1. Em `github.com/new`, criar repositorio:
   - Nome: `apex-fopag`
   - Visibilidade: **Private**
   - NAO inicializar com README (o repo local ja tem um).
2. Subir o conteudo da pasta `apex-fopag/` para o repo.
   - Pode usar `git push` da linha de comando se preferir, ou
   - via interface web: "uploading an existing file" e arrastar os arquivos.

## 2. Supabase — criar schema e seed

1. No projeto Supabase (ja conectado): SQL Editor.
2. Cole e execute `db/schema.sql` (cria as tabelas, views e RLS no schema `apex_fopag`).
3. Cole e execute `db/seed.sql` (popula empresas, obras, departamentos, cargos, rubricas, parametros).
4. Em "Settings -> API", copie:
   - `Project URL` (vai ser o `SUPABASE_URL`)
   - `service_role key` (vai ser o `SUPABASE_KEY`) — eh a chave que ignora RLS, perfeita pro app que roda server-side.
5. Em "Authentication -> Settings", confirme que esta usando RLS (default) — o `service_role` ignora RLS automaticamente.

## 3. Streamlit Community Cloud — deploy

1. Em `share.streamlit.io`, login com a conta GitHub.
2. "New app":
   - Repository: `<seu-usuario>/apex-fopag`
   - Branch: `main`
   - Main file path: `app.py`
   - App URL: escolha algo como `apex-fopag.streamlit.app`
3. Antes do deploy, em "Advanced settings -> Secrets", cole:
   ```toml
   SUPABASE_URL = "https://xxxxxxxxxxxx.supabase.co"
   SUPABASE_KEY = "eyJ..."  # service_role key
   ADMIN_EMAILS = ["dudaroeira@gmail.com"]
   ```
4. Click "Deploy". A primeira build leva ~3-5min.
5. Quando estiver verde, abra o link do app.

## 4. Compartilhar com os socios

Streamlit Community Cloud free aceita apps privados com lista de e-mails.

1. No painel do app (`share.streamlit.io`), abra "Settings -> Sharing".
2. Em "Who can view this app", selecione "Specific people".
3. Adicione os e-mails dos socios.
4. Eles recebem o link e logam com o e-mail correspondente.

## 5. Carregando a primeira folha

1. Abra o app no navegador.
2. Tela inicial -> "Carregar folha do mes".
3. Upload do `.xls` analitico do mes.
4. Aparece resumo: empresa, mes detectado, numero de funcionarios.
5. Click "Gravar no banco".
6. As paginas da esquerda (Visao Grupo, Visao Empresa, Visao Obra, etc.) ja mostram os dados.

## 6. Adicionando obra ou empresa novas

Sem mexer em codigo. Duas opcoes:

**a)** No Supabase Table Editor:
- `apex_fopag.empresas` -> inserir nova empresa.
- `apex_fopag.obras` -> inserir nova obra (lembrar de informar `empresa_responsavel`).
- `apex_fopag.departamentos` -> se for obra de outra empresa do grupo (caso Obra 204), criar o departamento espelho na empresa que aloca pessoal la, com `cod_obra_vinculada` apontando pra obra.

**b)** Editar `db/seed.sql` no repo e rodar de novo (idempotente).

## 7. Atualizando o app

Push pro repo -> Streamlit Cloud redeploya automaticamente em ~2min.

## 8. Recuperando do pior

- Quem apagar dados sem querer: Supabase guarda backups automaticos por 7 dias (plano Free).
- Quem subir codigo quebrado: `git revert` + push.
- Quem perder o `service_role key`: gerar nova em "Settings -> API -> Reset", atualizar secret no Streamlit Cloud.

## 9. Custos

Tudo no Free Tier:
- GitHub repo privado: gratis (Free plan ilimitado para repos privados).
- Supabase: gratis ate 500MB storage + 50k usuarios autenticados/mes. Sobra muito.
- Streamlit Community Cloud: gratis para apps publicos ou privados com sharing por e-mail.
