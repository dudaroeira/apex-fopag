"""Visão consolidada de todas as empresas do Grupo Apex."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from lib import db, kpis

st.set_page_config(page_title="Visão Grupo", page_icon="📊", layout="wide")
st.title("📊 Visão Grupo — Consolidado")

mes = st.session_state.get("mes_ref_global") or (db.list_meses() or [None])[0]
if not mes:
    st.warning("Carregue um analítico na página inicial primeiro.")
    st.stop()

df = db.fetch_folha(mes_ref=mes)
cargos = db.fetch_cadastro("cargos")
empresas = db.list_empresas()

st.caption(f"Mês de referência: **{mes}**")

# ---- KPIs ----
k = kpis.kpi_basico(df)
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Headcount", k["headcount"])
c2.metric("Ativos", k["ativos"])
c3.metric("Inativos", k["inativos"], f"{k['pct_inativos']*100:.1f}%", delta_color="inverse")
c4.metric("Folha bruta", f"R$ {k['proventos_total']:,.0f}".replace(",", "."))
c5.metric("Salário base médio", f"R$ {k['salario_medio']:,.0f}".replace(",", "."))

st.divider()

# ---- Distribuição por empresa ----
col1, col2 = st.columns(2)
with col1:
    st.subheader("Headcount por empresa")
    por_emp = (df.merge(empresas[["cod_empresa", "nome_curto"]], on="cod_empresa", how="left")
                 .groupby("nome_curto").size().reset_index(name="quantidade"))
    if not por_emp.empty:
        fig = px.bar(por_emp, x="nome_curto", y="quantidade", text="quantidade",
                     labels={"nome_curto": "Empresa", "quantidade": "Pessoas"})
        fig.update_layout(showlegend=False, height=360)
        st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("Custo por empresa")
    custo_emp = (df.merge(empresas[["cod_empresa", "nome_curto"]], on="cod_empresa", how="left")
                   .groupby("nome_curto")["proventos_total"].sum().reset_index())
    if not custo_emp.empty:
        fig = px.pie(custo_emp, names="nome_curto", values="proventos_total", hole=0.5)
        fig.update_layout(height=360)
        st.plotly_chart(fig, use_container_width=True)

# ---- Pirâmide ----
st.subheader("Pirâmide por nível")
pir = kpis.piramide_por_nivel(df, cargos)
if not pir.empty:
    fig = px.bar(pir, x="quantidade", y="nivel", orientation="h", text="quantidade")
    fig.update_layout(yaxis={"categoryorder": "array", "categoryarray": pir["nivel"].tolist()[::-1]},
                      height=420)
    st.plotly_chart(fig, use_container_width=True)

# ---- Tabela detalhada ----
st.subheader("Detalhe")
mostra = df.merge(empresas[["cod_empresa", "nome_curto"]], on="cod_empresa", how="left")
mostra = mostra[["nome_curto", "matricula", "nome", "cod_cargo", "situacao",
                 "salario_base", "proventos_total", "liquido"]]
mostra.columns = ["Empresa", "Matrícula", "Nome", "Cargo", "Situação",
                  "Sal. base", "Proventos", "Líquido"]
st.dataframe(mostra, use_container_width=True, hide_index=True)
