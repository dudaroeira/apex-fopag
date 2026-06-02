"""apex-fopag — Home mobile-first.

Layout centrado, cards grandes, atalhos para Comparativo e Visão Obra.
Upload dos analíticos fica num expander (caso de uso mensal).
"""
from __future__ import annotations

import os
import tempfile

import pandas as pd
import streamlit as st

from lib import db
from lib import kpis_rh as krh
from lib.parser_xls import parse_xls

st.set_page_config(
    page_title="Grupo Apex — RH",
    page_icon="🏗️",
    layout="centered",
)

st.markdown(
    """
    <style>
      [data-testid="stMetricValue"] { font-size: 1.8rem; }
      [data-testid="stMetricLabel"] { font-size: 0.9rem; opacity: 0.75; }
      .small-cap { font-size: 0.85rem; opacity: 0.7; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.sidebar.title("Grupo Apex — RH")
meses = db.list_meses()
mes = None
if meses:
    mes = st.sidebar.selectbox("Mês de referência", meses, key="mes_ref_global")
else:
    st.sidebar.info("Sem dados ainda. Use Upload abaixo.")

st.sidebar.divider()
st.sidebar.caption("Navegue pelas telas no menu acima ⬆️")
st.sidebar.markdown(
    "📈 **Comparativo Mensal** — variações Δ%  \n"
    "🏗️ **Visão Obra** — consolidação por canteiro  \n"
    "🏢 **Visão Empresa** — APEX / JR6  \n"
    "👤 **Visão Funcionário** — histórico individual"
)

st.markdown("# 🏗️ Painel do Grupo Apex")

if not mes:
    st.info("Carregue um analítico para começar — use o **Upload** abaixo.")
else:
    with st.spinner("Carregando…"):
        df = db.fetch_folha(mes_ref=mes)
        cargos = db.fetch_cadastro("cargos")
        empresas = db.list_empresas()

    if df.empty:
        st.warning("Nenhum dado para o mês selecionado.")
    else:
        st.caption(f"Mês de referência: **{mes}**")

        c1, c2, c3 = st.columns(3)
        head = len(df)
        prov = float(pd.to_numeric(df["proventos_total"], errors="coerce").fillna(0).sum())
        enc = krh.custo_com_encargos(df)
        c1.metric("Headcount", head)
        c2.metric("Folha bruta", f"R$ {prov/1000:,.0f}k".replace(",", "."))
        c3.metric("Custo c/ encargos", f"R$ {enc/1000:,.0f}k".replace(",", "."))

        c1, c2, c3 = st.columns(3)
        pct_inat = krh.pct_inativos(df) * 100
        cm = krh.custo_medio(df)
        tempo = krh.tempo_de_casa_medio_anos(df)
        c1.metric("% Inativos", f"{pct_inat:.1f}%", delta_color="inverse")
        c2.metric("Custo médio/pessoa", f"R$ {cm:,.0f}".replace(",", "."))
        c3.metric("Tempo médio de casa", f"{tempo:.1f} anos")

        st.markdown("### Ir para")
        col1, col2 = st.columns(2)
        with col1:
            with st.container(border=True):
                st.markdown("📈 **Comparativo Mensal**")
                st.caption("Variações entre dois meses, alertas, movimentações")
                if st.button("Abrir Comparativo", use_container_width=True):
                    st.switch_page("pages/6_Comparativo_Mensal.py")
        with col2:
            with st.container(border=True):
                st.markdown("🏗️ **Visão Obra**")
                st.caption("Consolida pessoas de empresas diferentes na mesma obra")
                if st.button("Abrir Visão Obra", use_container_width=True):
                    st.switch_page("pages/3_Visao_Obra.py")

        st.markdown("### Por empresa")
        por_emp = (df.groupby("cod_empresa")
                     .agg(headcount=("matricula", "count"),
                          proventos=("proventos_total", "sum"))
                     .reset_index()
                     .merge(empresas[["cod_empresa", "nome_curto"]], on="cod_empresa", how="left"))
        for _, row in por_emp.iterrows():
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 1, 1])
                c1.markdown(f"**{row['nome_curto']}**")
                c2.metric("Headcount", int(row["headcount"]), label_visibility="collapsed", help="Headcount")
                c3.metric("Folha", f"R$ {row['proventos']/1000:,.0f}k".replace(",", "."),
                          label_visibility="collapsed", help="Folha bruta")

st.divider()

with st.expander("⬆️ Carregar folha do mês (XLS)", expanded=(not bool(mes))):
    st.caption("Selecione um ou vários XLS analíticos do sistema do escritório.")
    arquivos = st.file_uploader("Arquivos", type=["xls", "xlsx"],
                                 accept_multiple_files=True, label_visibility="collapsed")
    if arquivos:
        parseados = []
        erros = []
        with st.spinner(f"Processando {len(arquivos)} arquivo(s)..."):
            for arquivo in arquivos:
                with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(arquivo.name)[1]) as tmp:
                    tmp.write(arquivo.getbuffer())
                    tmp_path = tmp.name
                try:
                    parsed = parse_xls(tmp_path)
                    parsed["arquivo_origem"] = arquivo.name
                    parseados.append(parsed)
                except Exception as exc:
                    erros.append((arquivo.name, str(exc)))
                finally:
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass
        for p in parseados:
            st.success(
                f"📄 **{p.get('arquivo_origem')}** → "
                f"{p['empresa'].get('razao_social', '?')[:30]} · "
                f"mês **{p.get('mes_ref', '?')}** · "
                f"**{len(p['funcionarios'])}** funcionários"
            )
        for nome, msg in erros:
            st.error(f"❌ {nome}: {msg}")
        if parseados and st.button(f"Gravar {len(parseados)} arquivo(s) no banco",
                                    type="primary", use_container_width=True):
            ok, falha = 0, 0
            with st.spinner("Gravando no Supabase..."):
                for p in parseados:
                    try:
                        res = db.upsert_folha(p)
                        st.write(f"✅ {p['arquivo_origem']} — {res['linhas_processadas']} funcionários, {res['eventos_inseridos']} eventos")
                        ok += 1
                    except Exception as exc:
                        st.error(f"❌ {p['arquivo_origem']}: {exc}")
                        falha += 1
            if ok:
                st.success(f"{ok} arquivo(s) gravado(s). Atualize a página.")
            if falha:
                st.warning(f"{falha} arquivo(s) com erro.")
