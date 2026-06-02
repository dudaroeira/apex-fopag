"""Client Supabase + funções de ingestão e leitura.

Todas as queries do app passam por aqui. Cacheamos com @st.cache_data
quando faz sentido para reduzir round-trips.
"""
from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any

import pandas as pd
import streamlit as st
from supabase import Client, create_client

SCHEMA = "apex_fopag"


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner=False)
def get_client() -> Client:
    url = st.secrets.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY") or os.environ.get("SUPABASE_KEY")
    if not url or not key:
        st.error(
            "Credenciais Supabase não configuradas. "
            "Adicione SUPABASE_URL e SUPABASE_KEY em .streamlit/secrets.toml "
            "ou em Streamlit Cloud → Settings → Secrets."
        )
        st.stop()
    return create_client(url, key)


def _tbl(name: str):
    return get_client().schema(SCHEMA).table(name)


# ---------------------------------------------------------------------------
# Leitura — usada pelos dashboards
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300, show_spinner=False)
def fetch_folha(mes_ref: str | None = None,
                cod_empresa: str | None = None,
                cod_obra: str | None = None) -> pd.DataFrame:
    q = _tbl("folha_mensal").select("*")
    if mes_ref:
        q = q.eq("mes_ref", mes_ref)
    if cod_empresa:
        q = q.eq("cod_empresa", cod_empresa)
    if cod_obra:
        q = q.eq("cod_obra", cod_obra)
    res = q.execute()
    return pd.DataFrame(res.data or [])


@st.cache_data(ttl=300, show_spinner=False)
def fetch_folha_obra(mes_ref: str | None = None,
                     cod_obra: str | None = None) -> pd.DataFrame:
    """Folha consolidada por OBRA — junta funcionários de empresas diferentes."""
    q = _tbl("v_folha_por_obra").select("*")
    if mes_ref:
        q = q.eq("mes_ref", mes_ref)
    if cod_obra:
        q = q.eq("cod_obra_efetivo", cod_obra)
    res = q.execute()
    return pd.DataFrame(res.data or [])


@st.cache_data(ttl=300, show_spinner=False)
def fetch_kpi_empresa(mes_ref: str | None = None) -> pd.DataFrame:
    q = _tbl("v_kpi_mes_empresa").select("*")
    if mes_ref:
        q = q.eq("mes_ref", mes_ref)
    return pd.DataFrame(q.execute().data or [])


@st.cache_data(ttl=300, show_spinner=False)
def fetch_kpi_obra(mes_ref: str | None = None) -> pd.DataFrame:
    q = _tbl("v_kpi_mes_obra").select("*")
    if mes_ref:
        q = q.eq("mes_ref", mes_ref)
    return pd.DataFrame(q.execute().data or [])


@st.cache_data(ttl=600, show_spinner=False)
def fetch_cadastro(tabela: str) -> pd.DataFrame:
    res = _tbl(tabela).select("*").execute()
    return pd.DataFrame(res.data or [])


@st.cache_data(ttl=600, show_spinner=False)
def list_meses() -> list[str]:
    res = _tbl("folha_mensal").select("mes_ref").execute()
    df = pd.DataFrame(res.data or [])
    if df.empty:
        return []
    return sorted(df["mes_ref"].dropna().unique().tolist(), reverse=True)


@st.cache_data(ttl=600, show_spinner=False)
def list_empresas() -> pd.DataFrame:
    return fetch_cadastro("empresas")


@st.cache_data(ttl=600, show_spinner=False)
def list_obras() -> pd.DataFrame:
    return fetch_cadastro("obras")


# ---------------------------------------------------------------------------
# Ingestão
# ---------------------------------------------------------------------------

def _to_jsonable(v: Any) -> Any:
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if pd.isna(v) if isinstance(v, float) else False:
        return None
    return v


def _garantir_cadastros(parsed: dict[str, Any], schema_client) -> None:
    """Insere cargos, obras e departamentos novos antes de gravar a folha.

    Necessário porque o sistema do escritório usa códigos que podem ainda
    não estar cadastrados (ex.: cargo novo, departamento criado depois do
    seed inicial). Sem isso, os FOREIGN KEYs em folha_mensal estouram.
    """
    cod_empresa = (parsed.get("empresa") or {}).get("cod_empresa")
    cargos_novos: dict[str, str] = {}
    obras_novas: set[str] = set()
    deps_novos: dict[str, str] = {}

    for f in parsed.get("funcionarios", []):
        cod = f.get("cod_cargo")
        if cod and cod not in cargos_novos:
            cargos_novos[cod] = f.get("nome_cargo") or cod
        cod_obra = f.get("cod_obra")
        if cod_obra:
            obras_novas.add(cod_obra)
        cod_dep = f.get("cod_departamento")
        if cod_dep and cod_dep not in deps_novos:
            deps_novos[cod_dep] = f.get("nome_departamento") or cod_dep

    if cargos_novos:
        rows = [
            {"cod_cargo": c, "nome_cargo": n, "nivel": "Oficial",
             "categoria": "Operacional", "demanda_aprendiz": False}
            for c, n in cargos_novos.items()
        ]
        schema_client.table("cargos").upsert(
            rows, on_conflict="cod_cargo", ignore_duplicates=True
        ).execute()

    if obras_novas:
        rows = [
            {"cod_obra": c, "nome_obra": c, "empresa_responsavel": cod_empresa,
             "status": "Em execução"}
            for c in obras_novas
        ]
        schema_client.table("obras").upsert(
            rows, on_conflict="cod_obra", ignore_duplicates=True
        ).execute()

    if deps_novos and cod_empresa:
        rows = [
            {"cod_empresa": cod_empresa, "cod_departamento": c,
             "nome_departamento": n, "tipo": "ADM"}
            for c, n in deps_novos.items()
        ]
        schema_client.table("departamentos").upsert(
            rows, on_conflict="cod_empresa,cod_departamento", ignore_duplicates=True
        ).execute()


def upsert_folha(parsed: dict[str, Any]) -> dict[str, int]:
    """Recebe a saída do parser e persiste no Supabase.

    Estratégia:
      1. Garante que a empresa e a obra do cabeçalho existem (cria se faltar).
      2. Auto-cadastra cargos, obras, departamentos novos vindos do arquivo.
      3. Para cada funcionário: upsert em folha_mensal pela chave única.
      4. Apaga eventos antigos da chave (cascade) e insere os novos.

    Retorna {'linhas_inseridas': n, 'linhas_atualizadas': n}.
    """
    mes_ref = parsed.get("mes_ref")
    empresa = parsed.get("empresa") or {}
    cod_empresa = empresa.get("cod_empresa")
    cod_obra_header = (parsed.get("obra") or {}).get("cod_obra")
    arquivo = parsed.get("arquivo_origem", "")

    if not mes_ref or not cod_empresa:
        raise ValueError(
            f"Não consegui detectar mes_ref ({mes_ref}) ou empresa ({cod_empresa}) no arquivo."
        )

    client = get_client()
    schema = client.schema(SCHEMA)

    # 1) Garante empresa e obra (caso seja nova)
    if empresa:
        schema.table("empresas").upsert(
            {
                "cod_empresa": cod_empresa,
                "razao_social": empresa.get("razao_social", ""),
                "nome_curto": empresa.get("razao_social", "")[:20] or cod_empresa,
                "cnpj": empresa.get("cnpj"),
            },
            on_conflict="cod_empresa",
            ignore_duplicates=True,
        ).execute()

    if cod_obra_header:
        obra = parsed.get("obra") or {}
        schema.table("obras").upsert(
            {
                "cod_obra": cod_obra_header,
                "nome_obra": obra.get("nome_obra") or cod_obra_header,
                "cnpj_cno": obra.get("cnpj_cno"),
                "empresa_responsavel": cod_empresa,
            },
            on_conflict="cod_obra",
            ignore_duplicates=True,
        ).execute()

    # 1.5) Auto-cadastra cargos/obras/deps que vieram nos dados (não bloqueia FK)
    _garantir_cadastros(parsed, schema)

    # 2) Upsert dos funcionários
    rows_folha = []
    rows_eventos = []
    chaves: list[tuple[str, str, str]] = []
    for f in parsed.get("funcionarios", []):
        cod_obra_func = f.get("cod_obra") or cod_obra_header
        rows_folha.append(
            {
                "mes_ref": mes_ref,
                "cod_empresa": cod_empresa,
                "matricula": f["matricula"],
                "nome": f.get("nome"),
                "cpf": f.get("cpf"),
                "pis": f.get("pis"),
                "nascimento": _to_jsonable(f.get("nascimento")),
                "dt_admissao": _to_jsonable(f.get("dt_admissao")),
                "dt_demissao": _to_jsonable(f.get("dt_demissao")),
                "situacao": f.get("situacao"),
                "cod_departamento": f.get("cod_departamento"),
                "cod_obra": cod_obra_func,
                "cod_cargo": f.get("cod_cargo"),
                "cod_funcao": f.get("cod_funcao"),
                "salario_base": f.get("salario_base") or 0,
                "proventos_total": f.get("proventos_total") or 0,
                "descontos_total": f.get("descontos_total") or 0,
                "liquido": f.get("liquido") or 0,
                "base_inss": f.get("base_inss") or 0,
                "base_fgts": f.get("base_fgts") or 0,
                "fgts": f.get("fgts") or 0,
                "base_irrf": f.get("base_irrf") or 0,
                "dependentes_ir": f.get("dependentes_ir") or 0,
                "arquivo_origem": arquivo,
            }
        )
        chave = (mes_ref, cod_empresa, f["matricula"])
        chaves.append(chave)
        for ev in f.get("eventos") or []:
            rows_eventos.append(
                {
                    "mes_ref": mes_ref,
                    "cod_empresa": cod_empresa,
                    "matricula": f["matricula"],
                    "tipo": ev.get("tipo") or "PROVENTO",
                    "cod_rubrica": ev.get("cod_rubrica"),
                    "descricao": ev.get("descricao"),
                    "quantidade": ev.get("quantidade") or 0,
                    "valor": ev.get("valor") or 0,
                }
            )

    if not rows_folha:
        raise ValueError("Nenhum funcionário foi extraído do arquivo.")

    res = schema.table("folha_mensal").upsert(
        rows_folha, on_conflict="mes_ref,cod_empresa,matricula"
    ).execute()

    for mes, emp, mat in chaves:
        schema.table("eventos_folha").delete().eq("mes_ref", mes).eq(
            "cod_empresa", emp
        ).eq("matricula", mat).execute()
    if rows_eventos:
        schema.table("eventos_folha").insert(rows_eventos).execute()

    n = len(rows_folha)
    schema.table("ingestao_log").insert(
        {
            "arquivo": arquivo,
            "cod_empresa": cod_empresa,
            "mes_ref": mes_ref,
            "linhas_inseridas": n,
            "linhas_atualizadas": 0,
            "status": "OK",
            "observacao": f"{len(rows_eventos)} eventos",
        }
    ).execute()

    st.cache_data.clear()

    return {"linhas_processadas": n, "eventos_inseridos": len(rows_eventos)}
