import os
import re
import shutil
import zipfile
import unicodedata
from datetime import datetime
import requests
import pandas as pd
import polars as pl
import time 
import config
from concurrent.futures import ThreadPoolExecutor, as_completed


def mes_anterior(ano: int, mes: int) -> str:
    if mes == 1:
        return f"{ano - 1}-12"
    return f"{ano}-{mes - 1:02d}"


def normalizar_texto(texto) -> str:
    if texto is None or pd.isna(texto):
        return ""
    texto = str(texto)
    texto_nfd = unicodedata.normalize("NFD", texto)
    texto_sem_acento = "".join(c for c in texto_nfd if unicodedata.category(c) != "Mn")
    return texto_sem_acento.lower().strip()


def _baixar_zip(url: str, local_zip: str, tentativas: int = 6) -> None:
    """Baixa com retomada (Range) e espera crescente: 30s, 60s, 120s, 240s, 300s."""
    for tentativa in range(1, tentativas + 1):
        try:
            ja = os.path.getsize(local_zip) if os.path.exists(local_zip) else 0
            headers = {"Range": f"bytes={ja}-"} if ja else {}
            retomada = f" [retomando em {ja // 1_000_000} MB]" if ja else ""
            print(f"  -> Baixando ({tentativa}/{tentativas}){retomada}: {url}")

            with requests.get(url, auth=(config.NC_SHARE_TOKEN, ""), headers=headers,
                              stream=True, timeout=config.TIMEOUT_SECONDS) as r:
                if r.status_code == 416:  # nada a retomar: já estava completo?
                    if zipfile.is_zipfile(local_zip):
                        return
                    os.remove(local_zip)
                    raise ValueError("Retomada recusada; recomeçando do zero")
                r.raise_for_status()
                restante = int(r.headers.get("Content-Length", 0))
                if r.status_code == 206:
                    modo, esperado = "ab", ja + restante
                else:  # 200: o servidor ignorou o Range
                    modo, esperado = "wb", restante
                with open(local_zip, modo) as f:
                    for chunk in r.iter_content(chunk_size=8192 * 16):
                        if chunk:
                            f.write(chunk)

            tamanho = os.path.getsize(local_zip)
            if tamanho == 0 or (esperado and tamanho != esperado) or not zipfile.is_zipfile(local_zip):
                raise ValueError(f"Download incompleto ({tamanho} de {esperado} bytes)")
            return
        except (requests.RequestException, ValueError, OSError) as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status == 404 or tentativa == tentativas:
                raise
            espera = min(30 * 2 ** (tentativa - 1), 300)
            print(f"     Falhou ({type(e).__name__}). Nova tentativa em {espera}s...")
            time.sleep(espera)


def _baixar_e_extrair_zip(url: str, pasta_destino: str, nome_zip: str) -> list[str]:
    """Baixa um ZIP (com retomada), extrai e devolve os nomes dos ficheiros extraídos."""
    if os.path.exists(pasta_destino):
        for f_antigo in os.listdir(pasta_destino):
            caminho_antigo = os.path.join(pasta_destino, f_antigo)
            if os.path.isfile(caminho_antigo):
                os.remove(caminho_antigo)

    local_zip = os.path.join(pasta_destino, nome_zip)
    _baixar_zip(url, local_zip)

    with zipfile.ZipFile(local_zip, "r") as zip_ref:
        zip_ref.extractall(pasta_destino)
    os.remove(local_zip)

    extraidos = [f for f in os.listdir(pasta_destino) if os.path.isfile(os.path.join(pasta_destino, f))]
    if not extraidos:
        raise ValueError(f"Nenhum ficheiro extraído de {nome_zip}")
    return sorted(extraidos)


def _processar_estabelecimento_arquivo(caminho_csv: str) -> pl.DataFrame:
    """Lê um único ficheiro de estabelecimento, filtra Cotia (6361) e Ativa (02) e retorna DataFrame."""
    df_lazy = pl.scan_csv(
        caminho_csv,
        separator=";",
        encoding="utf8-lossy",
        has_header=False,
        infer_schema_length=0,  # Lê tudo como String sem erro de tipagem
    )
    # Pega os nomes reais das colunas geradas pelo Polars (seja column_1 ou column_0)
    cols = df_lazy.collect_schema().names()

    # Mapeamento por índice (0-based) correspondente às colunas da Receita Federal:
    # 0: cnpj_basico, 1: cnpj_ordem, 2: cnpj_dv, 3: id_matriz_filial, 4: nome_fantasia,
    # 5: sit_cadastral, 6: dt_sit_cadastral, 10: dt_inicio_atv, 11: cnae_principal,
    # 12: cnae_secundario, 13: tipo_logradouro, 14: logradouro, 15: numero,
    # 16: complemento, 17: bairro, 18: cep, 20: municipio, 21: ddd, 22: telefone, 27: email
    mapa_colunas = {
        cols[0]: "cnpj_basico",
        cols[1]: "cnpj_ordem",
        cols[2]: "cnpj_dv",
        cols[3]: "id_matriz_filial",
        cols[4]: "nome_fantasia",
        cols[5]: "sit_cadastral",
        cols[6]: "dt_sit_cadastral",
        cols[10]: "dt_inicio_atv",
        cols[11]: "cnae_principal",
        cols[12]: "cnae_secundario",
        cols[13]: "tipo_logradouro",
        cols[14]: "logradouro",
        cols[15]: "numero",
        cols[16]: "complemento",
        cols[17]: "bairro",
        cols[18]: "cep",
        cols[20]: "municipio",
        cols[21]: "ddd",
        cols[22]: "telefone",
        cols[27]: "email",
    }

    return (
        df_lazy
        .filter(
            pl.col(cols[20]).is_not_null()
            & (pl.col(cols[20]) == config.MUNICIPIO_ALVO)
            & (pl.col(cols[5]) == config.SITUACAO_CADASTRAL)
        )
        .select(list(mapa_colunas.keys()))
        .rename(mapa_colunas)
        .with_columns([
            pl.col("email").str.to_lowercase(),
            pl.col("dt_sit_cadastral").str.to_date(format="%Y%m%d", strict=False).alias("dt_sit_cadastral"),
            pl.col("dt_inicio_atv").str.to_date(format="%Y%m%d", strict=False).alias("dt_inicio_atv"),
        ])
        .collect()
    )


def _processar_empresa_arquivo(caminho_csv: str, cnpjs_cotia: pl.Series) -> pl.DataFrame:
    """Lê um único ficheiro de empresas e filtra apenas os CNPJs básicos que pertencem a Cotia."""
    df_lazy = pl.scan_csv(
        caminho_csv,
        separator=";",
        encoding="utf8-lossy",
        has_header=False,
        infer_schema_length=0,
    )
    cols = df_lazy.collect_schema().names()

    mapa_colunas = {
        cols[0]: "cnpj_basico",
        cols[1]: "razao_social",
        cols[3]: "qualif_responsavel",
        cols[4]: "capital_social",
        cols[5]: "porte",
    }

    return (
        df_lazy
        .filter(pl.col(cols[0]).is_in(cnpjs_cotia))
        .select(list(mapa_colunas.keys()))
        .rename(mapa_colunas)
        .collect()
    )

def _processar_tipo(nome, mes, pasta, processar, pasta_cache, prefixo):
    """Baixa os zips de um tipo (vários em paralelo), processa um a um, com cache em Parquet."""
    n = config.NUM_ARQUIVOS
    os.makedirs(pasta, exist_ok=True)
    os.makedirs(pasta_cache, exist_ok=True)
    partes, pendentes = {}, []
    for i in range(n):
        cache = os.path.join(pasta_cache, f"{prefixo}_{i}.parquet")
        if os.path.exists(cache):
            print(f"  -> {nome}{i}: usando cache")
            partes[i] = pl.read_parquet(cache)
        else:
            pendentes.append(i)

    def baixar(i):
        destino = os.path.join(pasta, f"{nome}{i}.zip")
        t0 = time.time()
        _baixar_zip(f"{config.BASE_URL}{mes}/{nome}{i}.zip", destino)
        seg = max(time.time() - t0, 1)
        mb = os.path.getsize(destino) / 1e6
        print(f"  -> {nome}{i}: {mb:.0f} MB baixados em {seg:.0f}s ({mb / seg:.2f} MB/s)")
        return i, destino

    if pendentes:
        ex = ThreadPoolExecutor(max_workers=config.DOWNLOADS_PARALELOS)
        try:
            futuros = [ex.submit(baixar, i) for i in pendentes]
            for fut in as_completed(futuros):
                i, caminho_zip = fut.result()
                t0 = time.time()
                pasta_ext = os.path.join(pasta, f"ext_{i}")
                os.makedirs(pasta_ext, exist_ok=True)
                with zipfile.ZipFile(caminho_zip) as z:
                    arquivos = [m for m in z.namelist() if not m.endswith("/")]
                    z.extractall(pasta_ext, members=arquivos)
                    print(f"     {nome}{i}: descompactado = {sum(m.file_size for m in z.infolist()) / 1e9:.1f} GB | disco livre agora: {shutil.disk_usage(pasta).free / 1e9:.1f} GB")
                os.remove(caminho_zip)
                df_zip = pl.concat([processar(os.path.join(pasta_ext, a)) for a in arquivos])
                shutil.rmtree(pasta_ext, ignore_errors=True)
                df_zip.write_parquet(os.path.join(pasta_cache, f"{prefixo}_{i}.parquet"))
                partes[i] = df_zip
                print(f"     {nome}{i}: extração e filtro em {time.time() - t0:.0f}s ({df_zip.height} linhas)")
        except BaseException:
            ex.shutdown(wait=False, cancel_futures=True)
            raise
        else:
            ex.shutdown()

    return pl.concat([partes[i] for i in range(n)])

def baixar_e_carregar_dados_receita(data_ref: datetime) -> tuple[pl.DataFrame, pl.DataFrame, str]:
    """
    Baixa e processa um zip de cada vez (mantendo o uso de disco baixo).
    Retorna: (df_final_bruto, df_cnae, mes_baixado)
    """
    if not config.NC_SHARE_TOKEN:
        raise ValueError("A variável de ambiente NC_SHARE_TOKEN não está definida!")

    ano, mes = data_ref.year, data_ref.month
    mes_para_baixar = f"{ano}-{mes:02d}"

    for tentativa in range(2):
        print(f"\n=> Tentativa {tentativa + 1}: baixar e processar dados de {mes_para_baixar} ...")
        pasta_unicos = os.path.join(config.DIR_UNICOS, mes_para_baixar)
        pasta_estab = os.path.join(config.DIR_ESTABELECIMENTOS, mes_para_baixar)
        pasta_emp = os.path.join(config.DIR_EMPRESAS, mes_para_baixar)

        os.makedirs(pasta_unicos, exist_ok=True)
        os.makedirs(pasta_estab, exist_ok=True)
        os.makedirs(pasta_emp, exist_ok=True)

        try:
            # 1. Baixar CNAEs
            print("\n[1/3] Baixando tabela de CNAEs...")
            url_cnae = f"{config.BASE_URL}{mes_para_baixar}/Cnaes.zip"
            novos_cnae = _baixar_e_extrair_zip(url_cnae, pasta_unicos, "Cnaes.zip")
            caminho_cnae = os.path.join(pasta_unicos, novos_cnae[0])

            df_cnae_raw = pl.read_csv(
                caminho_cnae,
                separator=";",
                encoding="latin1",
                has_header=False,
                infer_schema_length=0,
            )
            cols_cnae = df_cnae_raw.columns
            df_cnae = (
                df_cnae_raw
                .rename({cols_cnae[0]: "cod_cnae", cols_cnae[1]: "descricao"})
                .with_columns([
                    pl.col("descricao").cast(pl.Utf8),
                    pl.col("cod_cnae").cast(pl.Utf8).str.zfill(7).alias("cod_cnae"),
                ])
            )
            os.remove(caminho_cnae)

            # 2. Baixar e filtrar Estabelecimentos (1 de cada vez para poupar disco)
            # Criação da pasta de cache para o mês atual
            pasta_cache = os.path.join(config.DIR_CACHE, f"{mes_para_baixar}_n{config.NUM_ARQUIVOS}")
            os.makedirs(pasta_cache, exist_ok=True)

                       # Baixar e filtrar Estabelecimentos e Empresas (downloads em paralelo, com cache em Parquet)
            print(f"\n[2/3] Processando Estabelecimentos (0 a {config.NUM_ARQUIVOS - 1})...")
            df_estabelecimentos = _processar_tipo(
                "Estabelecimentos", mes_para_baixar, pasta_estab,
                _processar_estabelecimento_arquivo, pasta_cache, "estab")
            cnpjs_cotia = df_estabelecimentos.select("cnpj_basico").unique()["cnpj_basico"].implode()

            print(f"\n[3/3] Processando Empresas (0 a {config.NUM_ARQUIVOS - 1})...")
            df_empresas = _processar_tipo(
                "Empresas", mes_para_baixar, pasta_emp,
                lambda caminho: _processar_empresa_arquivo(caminho, cnpjs_cotia),
                pasta_cache, "emp")

            # Limpar pastas temporárias
            shutil.rmtree(pasta_unicos, ignore_errors=True)
            shutil.rmtree(pasta_estab, ignore_errors=True)
            shutil.rmtree(pasta_emp, ignore_errors=True)

            ordem_colunas = [
                "cnpj_basico", "cnpj_ordem", "cnpj_dv", "id_matriz_filial", "razao_social",
                "nome_fantasia", "qualif_responsavel", "capital_social", "porte",
                "sit_cadastral", "dt_sit_cadastral", "dt_inicio_atv", "cnae_principal",
                "cnae_secundario", "tipo_logradouro", "logradouro", "numero",
                "complemento", "bairro", "cep", "municipio", "telefone_completo", "email",
            ]

            df_final = (
                df_estabelecimentos
                .join(df_empresas, on="cnpj_basico", how="left")
                .with_columns([
                    pl.col("sit_cadastral").replace(old=["02"], new=["ATIVA"]),
                    pl.col("municipio").replace(old=[config.MUNICIPIO_ALVO], new=[config.NOME_MUNICIPIO]),
                    pl.col("porte").replace(
                        old=["00", "01", "03", "05"],
                        new=["NÃO INFORMADO", "MICRO EMPRESA", "EMPRESA DE PEQUENO PORTE", "DEMAIS"],
                    ),
                    pl.concat_str([pl.col("ddd"), pl.col("telefone")], separator="").alias("telefone_completo"),
                ])
                .select(ordem_colunas)
            )

            print(f"\nSucesso! Dados de {mes_para_baixar} carregados ({df_final.height} empresas ativas em Cotia).")
            return df_final, df_cnae, mes_para_baixar

        except Exception as e:
            shutil.rmtree(pasta_unicos, ignore_errors=True)
            shutil.rmtree(pasta_estab, ignore_errors=True)
            shutil.rmtree(pasta_emp, ignore_errors=True)
            nao_publicado = (
                isinstance(e, requests.HTTPError)
                and e.response is not None
                and e.response.status_code == 404
            )
            if not nao_publicado:
                raise  # erro de rede ou de código: mostra a causa real
            print(f"\nMês {mes_para_baixar} ainda não publicado (404). Tentando o anterior...")
            mes_para_baixar = mes_anterior(ano, mes)

    raise RuntimeError("Nenhum mês disponível para download (atual nem anterior).")


def classificar_comex(df_final: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame, dict]:
    """
    Lê a folha de cálculo de filtros do Google Sheets, aplica regras de CNAE e palavras-chave
    e retorna (df_final_com_flag, df_comex, metadados_metodologia).
    """
    print("\nBaixando planilha de filtros e classificando empresas Comex...")
    cols_filtro_cnae = ["Classe", "Denominação", "Seleção"]
    df_filtro_cnae = pd.read_excel(config.URL_EXCEL_FILTRO, sheet_name="Filtro por cnae", usecols=cols_filtro_cnae)
    df_filtro_cnae["cnae_padronizado"] = (
        df_filtro_cnae["Classe"]
        .astype(str)
        .str.replace(".", "", regex=False)
        .str.replace("-", "", regex=False)
    )

    df_filtro_nome = pd.read_excel(config.URL_EXCEL_FILTRO, sheet_name="Filtro por nome")

    cnaes_aceitos = df_filtro_cnae[
        df_filtro_cnae["Seleção"].str.upper() == "ACEITA"
    ]["cnae_padronizado"].tolist()

    cnaes_rejeitados = df_filtro_cnae[
        df_filtro_cnae["Seleção"].str.upper() == "REJEITA"
    ]["cnae_padronizado"].tolist()

    palavras_chave_originais = (
        df_filtro_nome["Nome Considerado em: Razão social ou nome fantasia"].dropna().tolist()
    )

    palavras_chave_normalizadas = []
    for palavra in palavras_chave_originais:
        if any(char in str(palavra) for char in ["[", "]", "(", ")", "|", "\\", "^", "$", "*", "+", "?", "."]):
            palavras_chave_normalizadas.append(str(palavra))
        else:
            palavra_norm = normalizar_texto(palavra)
            palavras_chave_normalizadas.append(re.escape(palavra_norm))

    df_final_norm = df_final.with_columns([
        pl.col("razao_social").map_elements(
            lambda x: normalizar_texto(x) if x is not None else "", return_dtype=pl.Utf8
        ).alias("razao_social_norm"),
        pl.col("nome_fantasia").map_elements(
            lambda x: normalizar_texto(x) if x is not None else "", return_dtype=pl.Utf8
        ).alias("nome_fantasia_norm"),
    ])

    regex_pattern = "|".join(palavras_chave_normalizadas) if palavras_chave_normalizadas else None
    regex_cnaes_aceitos = r"(?:^|,\s*)(" + "|".join(cnaes_aceitos) + r")(?:\d{2})?(?:,|$)" if cnaes_aceitos else None
    regex_cnaes_rejeitados = r"(?:^|,\s*)(" + "|".join(cnaes_rejeitados) + r")(?:\d{2})?(?:,|$)" if cnaes_rejeitados else None

    filtro_aceita = pl.lit(False)
    if regex_pattern:
        filtro_aceita = (
            filtro_aceita
            | pl.col("razao_social_norm").str.contains(regex_pattern)
            | pl.col("nome_fantasia_norm").str.contains(regex_pattern)
        )
    if cnaes_aceitos:
        filtro_aceita = filtro_aceita | pl.col("cnae_principal").str.slice(0, 5).is_in(cnaes_aceitos)
    if regex_cnaes_aceitos:
        filtro_aceita = filtro_aceita | pl.col("cnae_secundario").str.contains(regex_cnaes_aceitos)

    filtro_rejeita = pl.lit(False)
    if cnaes_rejeitados:
        filtro_rejeita = filtro_rejeita | pl.col("cnae_principal").str.slice(0, 5).is_in(cnaes_rejeitados)
    if regex_cnaes_rejeitados:
        filtro_rejeita = filtro_rejeita | pl.col("cnae_secundario").str.contains(regex_cnaes_rejeitados)

    df_comex_temp = df_final_norm.filter(filtro_aceita & ~filtro_rejeita)
    cnpj_comex = df_comex_temp.select("cnpj_basico").unique()

    df_final = df_final.with_columns(
        pl.col("cnpj_basico").is_in(cnpj_comex["cnpj_basico"].implode()).alias("is_comex")
    )
    df_comex = df_final.filter(pl.col("is_comex"))

    df_aceitos = df_filtro_cnae[df_filtro_cnae["Seleção"].str.upper() == "ACEITA"][["Classe", "Denominação"]]
    lista_cnaes_aceitos = [f"{r['Classe']} – {r['Denominação']}" for _, r in df_aceitos.iterrows()]

    df_rejeitados = df_filtro_cnae[df_filtro_cnae["Seleção"].str.upper() == "REJEITA"][["Classe", "Denominação"]]
    lista_cnaes_rejeitados = [f"{r['Classe']} – {r['Denominação']}" for _, r in df_rejeitados.iterrows()]

    lista_palavras = palavras_chave_originais if palavras_chave_originais else ["(nenhuma palavra definida)"]

    metadados_filtro = {
        "cnaes_aceitos_codigos": cnaes_aceitos,
        "lista_cnaes_aceitos": lista_cnaes_aceitos,
        "lista_cnaes_rejeitados": lista_cnaes_rejeitados,
        "lista_palavras": lista_palavras,
    }

    return df_final, df_comex, metadados_filtro


def executar_etl(data_ref: datetime) -> tuple[pl.DataFrame, pl.DataFrame, dict, str]:
    df_final, _df_cnae, mes_baixado = baixar_e_carregar_dados_receita(data_ref)
    df_final, df_comex, metadados_filtro = classificar_comex(df_final)
    return df_final, df_comex, metadados_filtro, mes_baixado