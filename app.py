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
    st.caption("Faça upload de um ou vários XLS analíticos (do escritório).")
    arquivos = st.file_uploader(
        "Arquivos analíticos",
        type=["xls", "xlsx"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )
    if arquivos:
        parseados = []
        erros = []
        with st.spinner(f"Processando {len(arquivos)} arquivo(s)..."):
            for arquivo in arquivos:
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=os.path.splitext(arquivo.name)[1]
                ) as tmp:
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

        for parsed in parseados:
            st.success(
                f"📄 **{parsed.get('arquivo_origem')}** → "
                f"{parsed['empresa'].get('razao_social', '?')[:30]} · "
                f"mês **{parsed.get('mes_ref', '?')}** · "
                f"**{len(parsed['funcionarios'])}** funcionários"
            )
        for nome, msg in erros:
            st.error(f"❌ {nome}: {msg}")

        if parseados and st.button(
            f"Gravar {len(parseados)} arquivo(s) no banco", type="primary"
        ):
            ok = 0
            falha = 0
            with st.spinner("Gravando no Supabase..."):
                for parsed in parseados:
                    try:
                        res = db.upsert_folha(parsed)
                        st.write(
                            f"✅ {parsed['arquivo_origem']} — "
                            f"{res['linhas_processadas']} funcionários, "
                            f"{res['eventos_inseridos']} eventos"
                        )
                        ok += 1
                    except Exception as exc:
                        st.error(f"❌ {parsed['arquivo_origem']}: {exc}")
                        falha += 1
            if ok:
                st.success(f"{ok} arquivo(s) gravado(s). Atualize a página para ver.")
            if falha:
                st.warning(f"{falha} arquivo(s) com erro — veja acima.")


# ---------- Rodape ----------
st.divider()
st.caption(
    "Veja **Comparativo Mensal** para variações mês a mês e **Visão Obra** "
    "para análise consolidada de canteiros com pessoas de empresas diferentes "
    "(ex.: Obra 204 — JR6 no canteiro + supervisão APEX)."
)
