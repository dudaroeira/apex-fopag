"""Visão Grupo — consolidação + KPIs ricos + top cargos por custo."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from lib import db
from lib import kpis_rh as krh

st.set_page_config(page_title="Visão Grupo", page_icon="📊", layout="centered")

st.markdown("# 📊 Visão Grupo")
mes = st.session_state.get("mes_ref_global") or (db.list_meses() or [None])[0]
if not mes:
    st.warning("Carregue um analítico no Home primeiro.")
    st.stop()

st.caption(f"Mês de referência: **{mes}**")

with st.spinner("Carregando…"):
    df = db.fetch_folha(mes_ref=mes)
    cargos = db.fetch_cadastro("cargos")
    empresas = db.list_empresas()

if df.empty:
    st.warning("Sem dados no período.")
    st.stop()

c1, c2, c3 = st.columns(3)
head = len(df)
prov = float(pd.to_numeric(df["proventos_total"], errors="coerce").fillna(0).sum())
enc = krh.custo_com_encargos(df)
c1.metric("Headcount", head)
c2.metric("Folha bruta", f"R$ {prov/1000:,.0f}k".replace(",", "."))
c3.metric("Custo c/ encargos", f"R$ {enc/1000:,.0f}k".replace(",", "."),
          help=f"Encargos: 33% obra, 30% admin. Total: R$ {enc:,.0f}".replace(",", "."))

c1, c2, c3 = st.columns(3)
pct_inat = krh.pct_inativos(df) * 100
cm = krh.custo_medio(df)
tempo = krh.tempo_de_casa_medio_anos(df)
c1.metric("% Inativos", f"{pct_inat:.1f}%", delta_color="inverse")
c2.metric("Custo médio", f"R$ {cm:,.0f}".replace(",", "."))
c3.metric("Tempo médio casa", f"{tempo:.1f} anos")

st.divider()

st.subheader("Composição da força de trabalho")
sit = krh.situacao_breakdown(df)
if not sit.empty:
    fig = px.pie(sit, names="situacao", values="quantidade", hole=0.55)
    fig.update_traces(textposition="outside", textinfo="label+value+percent")
    fig.update_layout(height=320, margin=dict(t=20, l=0, r=0, b=0), showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

st.divider()

st.subheader("Por empresa")
por_emp = (df.merge(empresas[["cod_empresa", "nome_curto"]], on="cod_empresa", how="left")
             .groupby("nome_curto")
             .agg(headcount=("matricula", "count"), folha_bruta=("proventos_total", "sum"))
             .reset_index())
por_emp["folha_bruta"] = por_emp["folha_bruta"].astype(float)
fig = px.bar(por_emp, x="nome_curto", y="headcount", text="headcount",
             labels={"nome_curto": "Empresa", "headcount": "Pessoas"})
fig.update_layout(height=300, showlegend=False, margin=dict(t=10, l=0, r=0, b=0))
st.plotly_chart(fig, use_container_width=True)

st.dataframe(
    por_emp.rename(columns={"nome_curto": "Empresa", "headcount": "Headcount",
                              "folha_bruta": "Folha bruta"}).style.format({"Folha bruta": "R$ {:,.0f}"}),
    use_container_width=True, hide_index=True,
)

st.divider()

st.subheader("Top cargos por custo")
top = krh.top_cargos_por_custo(df, cargos, n=10)
if not top.empty:
    fig = px.bar(top.sort_values("Folha bruta"), x="Folha bruta", y="Cargo",
                 orientation="h", text="Qtd.", labels={"Folha bruta": "Folha (R$)"})
    fig.update_layout(height=380, margin=dict(t=10, l=0, r=0, b=0))
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(top.style.format({"Folha bruta": "R$ {:,.0f}", "Sal. médio": "R$ {:,.0f}"}),
                 use_container_width=True, hide_index=True)

st.divider()

st.subheader("Pirâmide hierárquica")
pir = krh.piramide_hierarquica(df, cargos)
if not pir.empty:
    fig = px.bar(pir, x="quantidade", y="nivel", orientation="h", text="quantidade")
    fig.update_layout(yaxis={"categoryorder": "array", "categoryarray": pir["nivel"].tolist()[::-1]},
                      height=340, margin=dict(t=10, l=0, r=0, b=0))
    st.plotly_chart(fig, use_container_width=True)

col1, col2 = st.columns(2)
with col1:
    st.subheader("Tempo de casa")
    tc = krh.faixas_tempo_casa(df)
    if not tc.empty:
        fig = px.bar(tc, x="Quantidade", y="Faixa", orientation="h", text="Quantidade")
        fig.update_layout(height=260, margin=dict(t=10, l=0, r=0, b=0))
        st.plotly_chart(fig, use_container_width=True)
with col2:
    st.subheader("Faixa etária")
    fe = krh.faixas_etarias(df)
    if not fe.empty:
        fig = px.bar(fe, x="Quantidade", y="Faixa", orientation="h", text="Quantidade")
        fig.update_layout(height=260, margin=dict(t=10, l=0, r=0, b=0))
        st.plotly_chart(fig, use_container_width=True)
