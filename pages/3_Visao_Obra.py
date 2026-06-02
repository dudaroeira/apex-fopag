"""Visão consolidada por OBRA — junta funcionários de qualquer empresa
alocados na mesma obra. Caso clássico: Obra 204 (JR6 no canteiro +
supervisão APEX via departamento 28)."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from lib import db, kpis

st.set_page_config(page_title="Visão Obra", page_icon="🏗️", layout="wide")
st.title("🏗️ Visão Obra")
st.caption(
    "Consolida funcionários de todas as empresas alocados na mesma obra. "
    "A vinculação 'departamento APEX → obra' é definida em Cadastros > Departamentos."
)

mes = st.session_state.get("mes_ref_global") or (db.list_meses() or [None])[0]
if not mes:
    st.warning("Carregue um analítico na página inicial primeiro.")
    st.stop()

obras = db.list_obras()
empresas = db.list_empresas()
cargos = db.fetch_cadastro("cargos")

if obras.empty:
    st.warning("Nenhuma obra cadastrada.")
    st.stop()

obra_sel = st.selectbox(
    "Obra",
    obras["cod_obra"],
    format_func=lambda c: obras.set_index("cod_obra").loc[c, "apelido"]
                          or obras.set_index("cod_obra").loc[c, "nome_obra"],
)
df = db.fetch_folha_obra(mes_ref=mes, cod_obra=obra_sel)

k = kpis.kpi_basico(df) if not df.empty else kpis.kpi_basico(pd.DataFrame(
    columns=["situacao", "proventos_total", "liquido", "salario_base"]
))
c1, c2, c3, c4 = st.columns(4)
c1.metric("Headcount na obra", k["headcount"])
c2.metric("Ativos", k["ativos"])
c3.metric("Inativos", k["inativos"], f"{k['pct_inativos']*100:.1f}%", delta_color="inverse")
c4.metric("Folha bruta", f"R$ {k['proventos_total']:,.0f}".replace(",", "."))

st.divider()

col1, col2 = st.columns(2)
with col1:
    st.subheader("Composição por empresa nesta obra")
    if not df.empty:
        por_emp = (df.merge(empresas[["cod_empresa", "nome_curto"]],
                            on="cod_empresa", how="left")
                     .groupby("nome_curto").size().reset_index(name="qtd"))
        fig = px.bar(por_emp, x="nome_curto", y="qtd", text="qtd",
                     labels={"nome_curto": "Empresa", "qtd": "Pessoas"})
        fig.update_layout(height=360, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("Distribuição por cargo")
    if not df.empty:
        por_cargo = (df.merge(cargos[["cod_cargo", "nome_cargo"]],
                              on="cod_cargo", how="left")
                       .groupby("nome_cargo").size().reset_index(name="qtd")
                       .sort_values("qtd"))
        fig = px.bar(por_cargo, y="nome_cargo", x="qtd", orientation="h", text="qtd")
        fig.update_layout(height=360)
        st.plotly_chart(fig, use_container_width=True)

# Pirâmide
st.subheader("Pirâmide hierárquica")
pir = kpis.piramide_por_nivel(df, cargos)
if not pir.empty:
    fig = px.bar(pir, x="quantidade", y="nivel", orientation="h", text="quantidade")
    fig.update_layout(yaxis={"categoryorder": "array",
                              "categoryarray": pir["nivel"].tolist()[::-1]}, height=420)
    st.plotly_chart(fig, use_container_width=True)

# Pessoas
st.subheader("Pessoas alocadas")
if not df.empty:
    mostra = df.merge(empresas[["cod_empresa", "nome_curto"]], on="cod_empresa", how="left") \
               .merge(cargos[["cod_cargo", "nome_cargo", "nivel"]], on="cod_cargo", how="left")
    cols = ["nome_curto", "matricula", "nome", "nome_cargo", "nivel", "situacao",
            "salario_base", "proventos_total"]
    cols = [c for c in cols if c in mostra.columns]
    mostra = mostra[cols].rename(columns={
        "nome_curto": "Empresa", "matricula": "Matrícula", "nome": "Nome",
        "nome_cargo": "Cargo", "nivel": "Nível", "situacao": "Situação",
        "salario_base": "Sal. base", "proventos_total": "Proventos",
    })
    st.dataframe(mostra, use_container_width=True, hide_index=True)
