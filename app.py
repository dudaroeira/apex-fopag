"""apex-fopag — entrada do Streamlit.

A pagina inicial e o Home (resumo + upload). As demais visoes ficam em pages/.
Alimentacao por XLS analitico do escritorio (saida do sistema FOPAG).
"""
from __future__ import annotations

import os
import tempfile

import pandas as pd
import streamlit as st

from lib import db, kpis
from lib.parser_xls import parse_xls


st.set_page_config(
    page_title="Grupo Apex — Folha de Pagamento",
    page_icon="🏗️",
    layout="wide",
)


# ---------- Sidebar global ----------
st.sidebar.title("Grupo Apex — RH")
st.sidebar.caption("Painel de folha de pagamento")

meses = db.list_meses()
if meses:
    st.sidebar.selectbox(
        "Mês de referência",
        meses,
        key="mes_ref_global",
        help="O filtro afeta as visões nas outras páginas.",
    )
else:
    st.sidebar.info("Nenhum mês carregado ainda. Use a caixa de upload na home.")


# ---------- Header da Home ----------
st.title("🏗️ Grupo Apex — Painel de Folha")
st.write(
    "Visão consolidada das folhas mensais de **APEX Engenharia**, **JR6 Empreendimentos** "
    "e demais empresas/obras do grupo. Use o menu lateral para navegar pelas visões."
)


# ---------- Resumo Home ----------
mes = st.session_state.get("mes_ref_global")
col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("Resumo do mês")
    if not mes:
        st.info("Carregue um analítico para começar.")
    else:
        df = db.fetch_folha(mes_ref=mes)
        k = kpis.kpi_basico(df)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Headcount", k["headcount"])
        c2.metric("Ativos", k["ativos"])
        c3.metric("Inativos", k["inativos"],
                  f"{k['pct_inativos']*100:.1f}% do total",
                  delta_color="inverse")
        c4.metric("Folha bruta", f"R$ {k['proventos_total']:,.0f}".replace(",", "."))
        if not df.empty:
            por_emp = (df.groupby("cod_empresa")
                         .agg(headcount=("matricula", "count"),
                              proventos=("proventos_total", "sum"))
                         .reset_index())
            empresas = db.list_empresas()
            por_emp = por_emp.merge(
                empresas[["cod_empresa", "nome_curto"]], on="cod_empresa", how="left"
            )
            st.markdown("#### Por empresa")
            st.dataframe(
                por_emp[["nome_curto", "headcount", "proventos"]].rename(
                    columns={"nome_curto": "Empresa",
                             "headcount": "Headcount",
                             "proventos": "Proventos (R$)"}
                ).style.format({"Proventos (R$)": "R$ {:,.2f}"}),
                use_container_width=True, hide_index=True,
            )


with col_right:
    st.subheader("Carregar folha do mês")
    st.caption("Faça upload do XLS analítico (saída do sistema do escritório).")
    arquivo = st.file_uploader(
        "Arquivo analítico",
        type=["xls", "xlsx"],
        accept_multiple_files=False,
        label_visibility="collapsed",
    )
    if arquivo is not None:
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=os.path.splitext(arquivo.name)[1]
        ) as tmp:
            tmp.write(arquivo.getbuffer())
            tmp_path = tmp.name
        try:
            with st.spinner("Processando..."):
                parsed = parse_xls(tmp_path)
                parsed["arquivo_origem"] = arquivo.name

            st.success(
                f"Detectado: **{parsed['empresa'].get('razao_social', '?')}** · "
                f"mês **{parsed.get('mes_ref', '?')}** · "
                f"**{len(parsed['funcionarios'])}** funcionários."
            )
            if st.button("Gravar no banco", type="primary"):
                with st.spinner("Gravando no Supabase..."):
                    res = db.upsert_folha(parsed)
                st.success(
                    f"Inseridos {res['linhas_processadas']} funcionários e "
                    f"{res['eventos_inseridos']} eventos. Atualize a página para ver."
                )
        except Exception as exc:
            st.error(f"Erro processando arquivo: {exc}")
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


# ---------- Rodape ----------
st.divider()
st.caption(
    "Veja **Comparativo Mensal** para variações mês a mês e **Visão Obra** "
    "para análise consolidada de canteiros com pessoas de empresas diferentes "
    "(ex.: Obra 204 — JR6 no canteiro + supervisão APEX)."
)
