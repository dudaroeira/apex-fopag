"""Histórico de um funcionário ao longo dos meses."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from lib import db, kpis

st.set_page_config(page_title="Visão Funcionário", page_icon="👤", layout="wide")
st.title("👤 Visão Funcionário")
st.caption("Histórico individual: evolução salarial, mudanças de obra/cargo, situação.")

empresas = db.list_empresas()
if empresas.empty:
    st.warning("Nenhum dado carregado.")
    st.stop()

emp_sel = st.selectbox(
    "Empresa",
    empresas["cod_empresa"],
    format_func=lambda c: empresas.set_index("cod_empresa").loc[c, "nome_curto"],
)
df_emp = db.fetch_folha(cod_empresa=emp_sel)

if df_emp.empty:
    st.info("Sem dados para essa empresa.")
    st.stop()

pessoas = df_emp[["matricula", "nome"]].drop_duplicates().sort_values("nome")
busca = st.text_input("Buscar por nome ou matrícula", "")
if busca:
    mask = (pessoas["nome"].str.contains(busca, case=False, na=False) |
            pessoas["matricula"].astype(str).str.contains(busca, case=False, na=False))
    pessoas = pessoas[mask]

if pessoas.empty:
    st.info("Nenhum funcionário encontrado.")
    st.stop()

sel = st.selectbox(
    "Funcionário",
    pessoas["matricula"],
    format_func=lambda m: f"{m} — {pessoas.set_index('matricula').loc[m, 'nome']}",
)

hist = df_emp[df_emp["matricula"] == sel].sort_values("mes_ref")
if hist.empty:
    st.stop()

ult = hist.iloc[-1]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Situação atual", ult.get("situacao", "—"))
c2.metric("Admissão", str(ult.get("dt_admissao", "—")))
c3.metric("Salário base", f"R$ {(ult.get('salario_base') or 0):,.2f}".replace(",", "."))
c4.metric("Líquido último mês", f"R$ {(ult.get('liquido') or 0):,.2f}".replace(",", "."))

st.divider()

# Evolução salarial
st.subheader("Evolução salarial")
ev = hist[["mes_ref", "salario_base", "proventos_total", "liquido"]].set_index("mes_ref")
st.line_chart(ev, height=300)

st.subheader("Histórico")
cols = ["mes_ref", "situacao", "cod_obra", "cod_departamento", "cod_cargo",
        "salario_base", "proventos_total", "descontos_total", "liquido"]
cols = [c for c in cols if c in hist.columns]
st.dataframe(hist[cols].rename(columns={
    "mes_ref": "Mês", "situacao": "Situação", "cod_obra": "Obra",
    "cod_departamento": "Depto", "cod_cargo": "Cargo",
    "salario_base": "Sal. base", "proventos_total": "Proventos",
    "descontos_total": "Descontos", "liquido": "Líquido",
}), use_container_width=True, hide_index=True)
