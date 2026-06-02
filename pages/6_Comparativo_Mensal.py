"""Comparativo entre dois meses — admissões, demissões, variação de custo."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from lib import db, kpis

st.set_page_config(page_title="Comparativo Mensal", page_icon="📈", layout="wide")
st.title("📈 Comparativo Mensal")
st.caption("Quem entrou, quem saiu, variação de custo entre dois meses.")

meses = db.list_meses()
if len(meses) < 2:
    st.info("Carregue pelo menos 2 meses na base para comparar.")
    st.stop()

col1, col2 = st.columns(2)
mes_curr = col1.selectbox("Mês atual", meses, index=0)
mes_prev = col2.selectbox("Mês anterior", meses, index=1)

df_c = db.fetch_folha(mes_ref=mes_curr)
df_p = db.fetch_folha(mes_ref=mes_prev)

k_c = kpis.kpi_basico(df_c)
k_p = kpis.kpi_basico(df_p)

st.subheader("Variações")
c1, c2, c3 = st.columns(3)
c1.metric("Headcount", k_c["headcount"], k_c["headcount"] - k_p["headcount"])
c2.metric("Folha bruta",
          f"R$ {k_c['proventos_total']:,.0f}".replace(",", "."),
          f"R$ {k_c['proventos_total'] - k_p['proventos_total']:+,.0f}".replace(",", "."))
c3.metric("Inativos", k_c["inativos"], k_c["inativos"] - k_p["inativos"], delta_color="inverse")

st.divider()

mov = kpis.comparativo_mensal(df_c, df_p)
if not mov.empty:
    st.subheader(f"Admissões e demissões entre {mes_prev} e {mes_curr}")
    empresas = db.list_empresas()
    mov = mov.merge(empresas[["cod_empresa", "nome_curto"]], on="cod_empresa", how="left")
    mostra = mov[["movimento", "nome_curto", "matricula", "nome", "cod_cargo",
                  "salario_base", "data_evento"]]
    mostra.columns = ["Movimento", "Empresa", "Matrícula", "Nome", "Cargo",
                      "Sal. base", "Data"]
    st.dataframe(mostra, use_container_width=True, hide_index=True)
else:
    st.info("Sem movimentações no período.")
