"""Visão por departamento — útil para a APEX (vários departamentos administrativos)."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from lib import db, kpis

st.set_page_config(page_title="Visão Departamento", page_icon="📋", layout="wide")
st.title("📋 Visão Departamento")

mes = st.session_state.get("mes_ref_global") or (db.list_meses() or [None])[0]
if not mes:
    st.warning("Carregue um analítico na página inicial primeiro.")
    st.stop()

empresas = db.list_empresas()
deps = db.fetch_cadastro("departamentos")
cargos = db.fetch_cadastro("cargos")

emp_sel = st.selectbox(
    "Empresa",
    empresas["cod_empresa"],
    format_func=lambda c: empresas.set_index("cod_empresa").loc[c, "nome_curto"],
)
deps_emp = deps[deps["cod_empresa"] == emp_sel]
if deps_emp.empty:
    st.info("Esta empresa não usa departamentos (cadastros vazios).")
    st.stop()

dep_sel = st.selectbox(
    "Departamento",
    deps_emp["cod_departamento"],
    format_func=lambda c: deps_emp.set_index("cod_departamento").loc[c, "nome_departamento"],
)
df = db.fetch_folha(mes_ref=mes, cod_empresa=emp_sel)
df = df[df["cod_departamento"] == dep_sel] if not df.empty else df

k = kpis.kpi_basico(df)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Pessoas no depto", k["headcount"])
c2.metric("Ativos", k["ativos"])
c3.metric("Inativos", k["inativos"], f"{k['pct_inativos']*100:.1f}%", delta_color="inverse")
c4.metric("Folha bruta", f"R$ {k['proventos_total']:,.0f}".replace(",", "."))

st.divider()

if not df.empty:
    mostra = df.merge(cargos[["cod_cargo", "nome_cargo", "nivel"]], on="cod_cargo", how="left")
    cols = ["matricula", "nome", "nome_cargo", "nivel", "situacao",
            "dt_admissao", "salario_base", "proventos_total"]
    cols = [c for c in cols if c in mostra.columns]
    mostra = mostra[cols].rename(columns={
        "matricula": "Matrícula", "nome": "Nome", "nome_cargo": "Cargo",
        "nivel": "Nível", "situacao": "Situação", "dt_admissao": "Admissão",
        "salario_base": "Sal. base", "proventos_total": "Proventos",
    })
    st.dataframe(mostra, use_container_width=True, hide_index=True)
