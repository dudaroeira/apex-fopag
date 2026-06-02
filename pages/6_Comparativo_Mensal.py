"""Comparativo Mensal — tela flagship.

Estrutura mobile-friendly: 1 coluna no celular, 2-3 no desktop.
Sequência: seletor → cards de variação → alertas → movimentação → evolução → detalhe.
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from lib import db
from lib import kpis_rh as krh

st.set_page_config(page_title="Comparativo Mensal", page_icon="📈", layout="centered")

st.markdown("# 📈 Comparativo Mensal")
st.caption("Variações entre dois meses, com alertas, movimentações e evolução.")

meses = db.list_meses()
if len(meses) < 1:
    st.warning("Carregue ao menos um mês no Home pra começar.")
    st.stop()

col_a, col_b = st.columns(2)
mes_curr = col_a.selectbox("Mês atual", meses, index=0)
mes_prev_default = 1 if len(meses) >= 2 else 0
mes_prev = col_b.selectbox("Mês de comparação", meses, index=mes_prev_default)

if mes_curr == mes_prev:
    st.info("Selecione dois meses diferentes para comparar.")
    st.stop()

with st.spinner("Carregando…"):
    df_c = db.fetch_folha(mes_ref=mes_curr)
    df_p = db.fetch_folha(mes_ref=mes_prev)
    cargos = db.fetch_cadastro("cargos")
    empresas = db.list_empresas()
    obras = db.list_obras()
    parametros = db.fetch_cadastro("parametros")

st.divider()

st.subheader("Variações entre os meses")
metricas = krh.comparativo_metricas(df_c, df_p, cargos)
for i in range(0, len(metricas), 2):
    cols = st.columns(2)
    for j, m in enumerate(metricas[i:i+2]):
        with cols[j]:
            valor_str = krh.fmt_valor(m["atual"], m["fmt"])
            delta_str = krh.fmt_delta(m["delta"], m["fmt"]) if m["delta"] != 0 else ""
            color = "off"
            if m["good_direction"] == "down":
                color = "inverse"
            elif m["good_direction"] == "up":
                color = "normal"
            st.metric(m["label"], valor_str,
                      delta=delta_str if delta_str else None,
                      delta_color=color,
                      help=f"Mês anterior: {krh.fmt_valor(m['anterior'], m['fmt'])}")

st.divider()

alertas = krh.alertas(df_c, df_p, cargos, parametros)
if alertas:
    st.subheader("⚠️ Alertas")
    for a in alertas:
        emoji = "🔴" if a["nivel"] == "vermelho" else "🟡"
        with st.container(border=True):
            st.markdown(f"{emoji} **{a['titulo']}**")
            st.write(a["msg"])

st.subheader("Movimentações")
mov = krh.movimentacoes(df_c, df_p)
adm, dem = mov["admissoes"], mov["demissoes"]
t1, t2 = st.tabs([f"➕ Admissões ({len(adm)})", f"➖ Demissões ({len(dem)})"])
with t1:
    if adm.empty:
        st.info("Nenhuma admissão no período.")
    else:
        a = adm.merge(empresas[["cod_empresa", "nome_curto"]], on="cod_empresa", how="left")
        a = a.merge(cargos[["cod_cargo", "nome_cargo"]], on="cod_cargo", how="left")
        a = a[["nome_curto", "matricula", "nome", "nome_cargo", "salario_base", "dt_admissao"]]
        a.columns = ["Empresa", "Matrícula", "Nome", "Cargo", "Sal. base", "Admissão"]
        st.dataframe(a, use_container_width=True, hide_index=True)
with t2:
    if dem.empty:
        st.info("Nenhuma demissão no período.")
    else:
        d = dem.merge(empresas[["cod_empresa", "nome_curto"]], on="cod_empresa", how="left")
        d = d.merge(cargos[["cod_cargo", "nome_cargo"]], on="cod_cargo", how="left")
        d = d[["nome_curto", "matricula", "nome", "nome_cargo", "salario_base", "dt_demissao"]]
        d.columns = ["Empresa", "Matrícula", "Nome", "Cargo", "Sal. base", "Demissão"]
        st.dataframe(d, use_container_width=True, hide_index=True)

st.divider()

st.subheader("Evolução histórica")
if len(meses) >= 2:
    serie = []
    for m in sorted(meses):
        dm = db.fetch_folha(mes_ref=m)
        if dm.empty:
            continue
        serie.append({
            "mes_ref": m,
            "Headcount": len(dm),
            "Folha bruta (R$ mil)": float(pd.to_numeric(dm["proventos_total"], errors="coerce").fillna(0).sum() / 1000),
            "% Inativos": krh.pct_inativos(dm) * 100,
            "Custo c/ encargos (R$ mil)": krh.custo_com_encargos(dm) / 1000,
        })
    ev = pd.DataFrame(serie)
    if not ev.empty:
        tab1, tab2, tab3 = st.tabs(["Headcount", "Folha", "% Inativos"])
        with tab1:
            fig = px.line(ev, x="mes_ref", y="Headcount", markers=True)
            fig.update_layout(height=300, margin=dict(t=10, l=0, r=0, b=0))
            st.plotly_chart(fig, use_container_width=True)
        with tab2:
            fig = px.line(ev, x="mes_ref", y=["Folha bruta (R$ mil)", "Custo c/ encargos (R$ mil)"], markers=True)
            fig.update_layout(height=300, margin=dict(t=10, l=0, r=0, b=0), legend=dict(orientation="h", y=-0.2))
            st.plotly_chart(fig, use_container_width=True)
        with tab3:
            fig = px.line(ev, x="mes_ref", y="% Inativos", markers=True)
            fig.update_layout(height=300, margin=dict(t=10, l=0, r=0, b=0))
            st.plotly_chart(fig, use_container_width=True)

st.divider()
st.subheader("Por empresa")

def _agg(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    return (df.groupby("cod_empresa")
              .agg(hc=("matricula", "count"), folha=("proventos_total", "sum"))
              .reset_index())

g_c = _agg(df_c).rename(columns={"hc": "HC atual", "folha": "Folha atual"})
g_p = _agg(df_p).rename(columns={"hc": "HC anterior", "folha": "Folha anterior"})
if not g_c.empty:
    g = g_c.merge(g_p, on="cod_empresa", how="outer").fillna(0)
    g = g.merge(empresas[["cod_empresa", "nome_curto"]], on="cod_empresa", how="left")
    g["Δ HC"] = g["HC atual"] - g["HC anterior"]
    g["Δ Folha %"] = (g["Folha atual"] - g["Folha anterior"]) / g["Folha anterior"].replace(0, pd.NA)
    g = g[["nome_curto", "HC atual", "Δ HC", "Folha atual", "Δ Folha %"]]
    g.columns = ["Empresa", "Headcount", "Δ HC", "Folha", "Δ %"]
    st.dataframe(g.style.format({"Folha": "R$ {:,.0f}", "Δ %": "{:+.1%}", "Δ HC": "{:+.0f}"}),
                 use_container_width=True, hide_index=True)

st.subheader("Por obra")
df_co = db.fetch_folha_obra(mes_ref=mes_curr)
df_po = db.fetch_folha_obra(mes_ref=mes_prev)

def _aggo(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    return (df.groupby("cod_obra_efetivo")
              .agg(hc=("matricula", "count"), folha=("proventos_total", "sum"))
              .reset_index()
              .rename(columns={"cod_obra_efetivo": "cod_obra"}))

go_c = _aggo(df_co).rename(columns={"hc": "HC atual", "folha": "Folha atual"})
go_p = _aggo(df_po).rename(columns={"hc": "HC anterior", "folha": "Folha anterior"})
if not go_c.empty:
    go = go_c.merge(go_p, on="cod_obra", how="outer").fillna(0)
    go = go.merge(obras[["cod_obra", "apelido"]], on="cod_obra", how="left")
    go["apelido"] = go["apelido"].fillna(go["cod_obra"])
    go["Δ HC"] = go["HC atual"] - go["HC anterior"]
    go["Δ Folha %"] = (go["Folha atual"] - go["Folha anterior"]) / go["Folha anterior"].replace(0, pd.NA)
    go = go[["apelido", "HC atual", "Δ HC", "Folha atual", "Δ Folha %"]]
    go.columns = ["Obra", "Headcount", "Δ HC", "Folha", "Δ %"]
    st.dataframe(go.style.format({"Folha": "R$ {:,.0f}", "Δ %": "{:+.1%}", "Δ HC": "{:+.0f}"}),
                 use_container_width=True, hide_index=True)

st.divider()
st.caption("**Como ler**: cards verdes = direção desejável, vermelhos = atenção. " "Alertas usam metas configuradas em `apex_fopag.parametros`.")
