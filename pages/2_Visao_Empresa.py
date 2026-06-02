"""Visão por empresa — APEX, JR6 ou nova empresa cadastrada."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from lib import db, kpis

st.set_page_config(page_title="Visão Empresa", page_icon="🏢", layout="wide")
st.title("🏢 Visão Empresa")

mes = st.session_state.get("mes_ref_global") or (db.list_meses() or [None])[0]
if not mes:
    st.warning("Carregue um analítico na página inicial primeiro.")
    st.stop()

empresas = db.list_empresas()
cargos = db.fetch_cadastro("cargos")
departamentos = db.fetch_cadastro("departamentos")

if empresas.empty:
    st.warning("Cadastros de empresa vazios.")
    st.stop()

emp_sel = st.selectbox(
    "Empresa",
    empresas["cod_empresa"],
    format_func=lambda c: empresas.set_index("cod_empresa").loc[c, "nome_curto"],
)
df = db.fetch_folha(mes_ref=mes, cod_empresa=emp_sel)

k = kpis.kpi_basico(df)
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Headcount", k["headcount"])
c2.metric("Ativos", k["ativos"])
c3.metric("Inativos", k["inativos"], f"{k['pct_inativos']*100:.1f}%", delta_color="inverse")
c4.metric("Folha bruta", f"R$ {k['proventos_total']:,.0f}".replace(",", "."))
c5.metric("Salário base médio", f"R$ {k['salario_medio']:,.0f}".replace(",", "."))

st.divider()

col1, col2 = st.columns(2)
with col1:
    st.subheader("Headcount por departamento")
    if not df.empty:
        deps_emp = departamentos[departamentos["cod_empresa"] == emp_sel]
        por_dep = (df.merge(
            deps_emp[["cod_departamento", "nome_departamento"]],
            on="cod_departamento", how="left",
        ).groupby("nome_departamento", dropna=False).size().reset_index(name="quantidade"))
        por_dep["nome_departamento"] = por_dep["nome_departamento"].fillna("(sem departamento)")
        fig = px.bar(por_dep.sort_values("quantidade"), y="nome_departamento",
                     x="quantidade", orientation="h", text="quantidade")
        fig.update_layout(height=420)
        st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("Situação")
    if not df.empty:
        sit = df["situacao"].value_counts().reset_index()
        sit.columns = ["situacao", "qtd"]
        fig = px.pie(sit, names="situacao", values="qtd", hole=0.5)
        fig.update_layout(height=420)
        st.plotly_chart(fig, use_container_width=True)

st.subheader("Funcionários")
mostra = df.merge(cargos[["cod_cargo", "nome_cargo", "nivel"]], on="cod_cargo", how="left")
cols = ["matricula", "nome", "nome_cargo", "nivel", "situacao", "cod_departamento",
        "salario_base", "proventos_total", "liquido"]
cols = [c for c in cols if c in mostra.columns]
mostra = mostra[cols].rename(columns={
    "matricula": "Matrícula", "nome": "Nome", "nome_cargo": "Cargo",
    "nivel": "Nível", "situacao": "Situação", "cod_departamento": "Depto",
    "salario_base": "Sal. base", "proventos_total": "Proventos", "liquido": "Líquido",
})
st.dataframe(mostra, use_container_width=True, hide_index=True)
