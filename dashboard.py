from datetime import datetime
import pandas as pd
import polars as pl
import config

def formatar_idade(anos_decimal) -> str:
    if anos_decimal is None or pd.isna(anos_decimal):
        return "N/A"
    anos = int(anos_decimal)
    meses = int((anos_decimal - anos) * 12)
    if anos == 0:
        return f"{meses} {'mês' if meses == 1 else 'meses'}"
    elif meses == 0:
        return f"{anos} {'ano' if anos == 1 else 'anos'}"
    return f"{anos} {'ano' if anos == 1 else 'anos'} e {meses} {'mês' if meses == 1 else 'meses'}"


def formatar_lista_para_html(lista: list[str]) -> str:
    if not lista:
        return "<em>Nenhum item definido</em>"
    return "<br>".join(f"• {item}" for item in lista)


def fmt(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def calcular_estatisticas(
    df_final: pl.DataFrame,
    df_comex: pl.DataFrame,
    metadados_filtro: dict,
    data_ref: datetime,
) -> dict:
    """Calcula estatísticas gerais, temporais (parametrizadas por data_ref) e geográficas."""
    total_empresas = df_final.height
    total_comex = df_comex.height
    percentual_comex = (total_comex / total_empresas) * 100 if total_empresas > 0 else 0
    total_nao_comex = total_empresas - total_comex

    cnaes_aceitos = metadados_filtro["cnaes_aceitos_codigos"]
    if cnaes_aceitos:
        comex_principal = df_comex.filter(
            pl.col("cnae_principal").str.slice(0, 5).is_in(cnaes_aceitos)
        ).height
        comex_secundaria = total_comex - comex_principal
    else:
        comex_principal = 0
        comex_secundaria = total_comex

    # --- ANÁLISE TEMPORAL PARAMETRIZADA ---
    df_com_idade = df_final.with_columns([
        (
            (pl.lit(data_ref.year) - pl.col("dt_inicio_atv").dt.year())
            + ((pl.lit(data_ref.month) - pl.col("dt_inicio_atv").dt.month()) / 12)
            + ((pl.lit(data_ref.day) - pl.col("dt_inicio_atv").dt.day()) / 365)
        ).alias("idade_anos")
    ]).filter(pl.col("dt_inicio_atv").is_not_null() & (pl.col("idade_anos") >= 0))

    empresas_com_data = df_com_idade.height
    empresas_sem_data = df_final.height - empresas_com_data

    idade_media_geral = df_com_idade.select(pl.col("idade_anos").mean()).item()
    idade_mediana_geral = df_com_idade.select(pl.col("idade_anos").median()).item()
    idade_min = df_com_idade.select(pl.col("idade_anos").min()).item()
    idade_max = df_com_idade.select(pl.col("idade_anos").max()).item()

    comparacao_idade = (
        df_com_idade.group_by("is_comex")
        .agg([
            pl.len().alias("quantidade"),
            pl.col("idade_anos").mean().alias("idade_media"),
            pl.col("idade_anos").median().alias("idade_mediana"),
            pl.col("idade_anos").std().alias("desvio_padrao"),
        ])
        .sort("is_comex")
    )

    idade_extremos = (
        df_com_idade.group_by("is_comex")
        .agg([
            pl.col("idade_anos").min().alias("idade_min"),
            pl.col("idade_anos").max().alias("idade_max"),
        ])
    )

    comex_stats = comparacao_idade.filter(pl.col("is_comex")).to_dicts()[0]
    comex_extremos = idade_extremos.filter(pl.col("is_comex")).to_dicts()[0]

    # --- EVOLUÇÃO MENSAL (ÚLTIMOS 12 MESES) ---
    df_evolucao = df_com_idade.with_columns([
        pl.col("dt_inicio_atv").dt.strftime("%Y-%m").alias("ano_mes")
    ])
    evolucao_mensal = (
        df_evolucao.group_by(["ano_mes", "is_comex"])
        .agg(pl.len().alias("quantidade"))
        .sort("ano_mes")
    )

    data_limite = datetime(data_ref.year - 1, data_ref.month, 1)
    ano_mes_limite = data_limite.strftime("%Y-%m")
    ultimos_12_meses = evolucao_mensal.filter(pl.col("ano_mes") >= ano_mes_limite)
    meses_unicos = sorted(ultimos_12_meses.select("ano_mes").unique().to_series().to_list())

    meses_nomes = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

    dados_grafico_mensal = []
    dados_crescimento_acumulado = []

    for mes_str in meses_unicos:
        dados_mes = ultimos_12_meses.filter(pl.col("ano_mes") == mes_str)
        total_mes = dados_mes.select("quantidade").sum().item()
        comex_mes = dados_mes.filter(pl.col("is_comex")).select("quantidade")
        qtd_comex = comex_mes.sum().item() if comex_mes.height > 0 else 0
        nao_comex_mes = dados_mes.filter(~pl.col("is_comex")).select("quantidade")
        qtd_nao_comex = nao_comex_mes.sum().item() if nao_comex_mes.height > 0 else 0

        ano_s, mes_s = mes_str.split("-")
        ano_i, mes_i = int(ano_s), int(mes_s)
        mes_formatado = f"{meses_nomes[mes_i - 1]}/{ano_s[2:]}"

        dados_grafico_mensal.append({
            "ano_mes": mes_str,
            "mes_formatado": mes_formatado,
            "total": total_mes,
            "comex": qtd_comex,
            "nao_comex": qtd_nao_comex,
        })

        data_fim = datetime(ano_i + 1, 1, 1) if mes_i == 12 else datetime(ano_i, mes_i + 1, 1)
        empresas_ate_mes = df_com_idade.filter(pl.col("dt_inicio_atv") < pl.lit(data_fim))

        dados_crescimento_acumulado.append({
            "ano_mes": mes_str,
            "mes_formatado": mes_formatado,
            "total": empresas_ate_mes.height,
            "comex": empresas_ate_mes.filter(pl.col("is_comex")).height,
            "nao_comex": empresas_ate_mes.filter(~pl.col("is_comex")).height,
        })

    df_grafico_mensal = pd.DataFrame(dados_grafico_mensal)
    df_crescimento_acumulado = pd.DataFrame(dados_crescimento_acumulado)
    df_crescimento_acumulado["crescimento_total_pct"] = df_crescimento_acumulado["total"].pct_change() * 100
    df_crescimento_acumulado["crescimento_comex_pct"] = df_crescimento_acumulado["comex"].pct_change() * 100
    df_crescimento_acumulado["crescimento_nao_comex_pct"] = df_crescimento_acumulado["nao_comex"].pct_change() * 100

    crescimento_total_periodo = (
        (df_crescimento_acumulado["total"].iloc[-1] - df_crescimento_acumulado["total"].iloc[0])
        / df_crescimento_acumulado["total"].iloc[0] * 100
    )
    crescimento_comex_periodo = (
        (df_crescimento_acumulado["comex"].iloc[-1] - df_crescimento_acumulado["comex"].iloc[0])
        / df_crescimento_acumulado["comex"].iloc[0] * 100
    )

    # --- CRESCIMENTO ANUAL (ÚLTIMOS 10 ANOS) ---
    df_anual = df_com_idade.with_columns([
        pl.col("dt_inicio_atv").dt.year().alias("ano")
    ]).filter(pl.col("ano") >= (data_ref.year - 10))

    crescimento_anual = (
        df_anual.group_by(["ano", "is_comex"])
        .agg(pl.len().alias("quantidade"))
        .sort("ano")
    )
    anos_unicos = sorted(crescimento_anual.select("ano").unique().to_series().to_list())

    dados_grafico_anual = []
    for ano in anos_unicos:
        dados_ano = crescimento_anual.filter(pl.col("ano") == ano)
        total_ano = dados_ano.select("quantidade").sum().item()
        comex_ano = dados_ano.filter(pl.col("is_comex")).select("quantidade")
        qtd_comex = comex_ano.sum().item() if comex_ano.height > 0 else 0
        nao_comex_ano = dados_ano.filter(~pl.col("is_comex")).select("quantidade")
        qtd_nao_comex = nao_comex_ano.sum().item() if nao_comex_ano.height > 0 else 0

        dados_grafico_anual.append({
            "ano": ano,
            "total": total_ano,
            "comex": qtd_comex,
            "nao_comex": qtd_nao_comex,
        })
    df_grafico_anual = pd.DataFrame(dados_grafico_anual)

    # --- ANÁLISE GEOGRÁFICA ---
    df_geo = df_final.with_columns([
        pl.col("bairro").str.to_uppercase().str.strip_chars().alias("bairro_padronizado")
    ])
    dist_geral = (
        df_geo.filter(pl.col("bairro_padronizado").is_not_null() & (pl.col("bairro_padronizado") != ""))
        .group_by("bairro_padronizado")
        .agg(pl.len().alias("total_empresas"))
        .sort("total_empresas", descending=True)
    )
    dist_comex = (
        df_geo.filter(pl.col("is_comex") & pl.col("bairro_padronizado").is_not_null() & (pl.col("bairro_padronizado") != ""))
        .group_by("bairro_padronizado")
        .agg(pl.len().alias("total_comex"))
        .sort("total_comex", descending=True)
    )
    dist_completa = (
        dist_geral.join(dist_comex, on="bairro_padronizado", how="left")
        .with_columns([
            pl.col("total_comex").fill_null(0),
            ((pl.col("total_comex").fill_null(0) / pl.col("total_empresas")) * 100).alias("percentual_comex"),
        ])
        .sort("total_empresas", descending=True)
    )

    top_20_geral = dist_completa.head(20)
    top_10_comex = dist_completa.sort("total_comex", descending=True).head(10)
    bairros_concentracao = (
        dist_completa.filter(pl.col("total_empresas") >= 10)
        .sort("percentual_comex", descending=True)
        .head(15)
    )

    stats = {
        "total_empresas": total_empresas,
        "total_comex": total_comex,
        "percentual_comex": percentual_comex,
        "total_nao_comex": total_nao_comex,
        "comex_principal": comex_principal,
        "comex_secundaria": comex_secundaria,
        "pct_principal": (comex_principal / total_comex * 100) if total_comex > 0 else 0,
        "pct_secundaria": (comex_secundaria / total_comex * 100) if total_comex > 0 else 0,
        "empresas_com_data": empresas_com_data,
        "empresas_sem_data": empresas_sem_data,
        "idade_media_geral": formatar_idade(idade_media_geral),
        "idade_mediana_geral": formatar_idade(idade_mediana_geral),
        "idade_max": formatar_idade(idade_max),
        "idade_min": formatar_idade(idade_min),
        "idade_comex_media": formatar_idade(comex_stats["idade_media"]),
        "idade_comex_mediana": formatar_idade(comex_stats["idade_mediana"]),
        "idade_comex_max": formatar_idade(comex_extremos["idade_max"]),
        "idade_comex_min": formatar_idade(comex_extremos["idade_min"]),
        "crescimento_total_periodo": crescimento_total_periodo,
        "total_inicial": df_crescimento_acumulado["total"].iloc[0],
        "total_final": df_crescimento_acumulado["total"].iloc[-1],
        "dif_total": df_crescimento_acumulado["total"].iloc[-1] - df_crescimento_acumulado["total"].iloc[0],
        "crescimento_comex_periodo": crescimento_comex_periodo,
        "comex_inicial": df_crescimento_acumulado["comex"].iloc[0],
        "comex_final": df_crescimento_acumulado["comex"].iloc[-1],
        "dif_comex": df_crescimento_acumulado["comex"].iloc[-1] - df_crescimento_acumulado["comex"].iloc[0],
    }

    return {
        "stats": stats,
        "df_grafico_anual": df_grafico_anual,
        "df_grafico_mensal": df_grafico_mensal,
        "df_crescimento_acumulado": df_crescimento_acumulado,
        "top_20_geral": top_20_geral,
        "top_10_comex": top_10_comex,
        "bairros_concentracao": bairros_concentracao,
        "dist_bairros": dist_completa,
        "idade_raw": {
            "total": {"media": idade_media_geral, "mediana": idade_mediana_geral,
                      "minimo": idade_min, "maximo": idade_max},
            "comex": {"media": comex_stats["idade_media"], "mediana": comex_stats["idade_mediana"],
                      "minimo": comex_extremos["idade_min"], "maximo": comex_extremos["idade_max"]},
        },
    }


def gerar_dashboard_html(dados_estatisticos: dict, metadados_filtro: dict, mes_para_baixar: str):
    stats = dados_estatisticos["stats"]

    metodologia_html = {
        "cnaes_aceitos": formatar_lista_para_html(metadados_filtro["lista_cnaes_aceitos"]),
        "cnaes_rejeitados": formatar_lista_para_html(metadados_filtro["lista_cnaes_rejeitados"]),
        "palavras_chave": formatar_lista_para_html(metadados_filtro["lista_palavras"]),
        "total_aceitos": len(metadados_filtro["lista_cnaes_aceitos"]),
        "total_rejeitados": len(metadados_filtro["lista_cnaes_rejeitados"]),
        "total_palavras": len(metadados_filtro["lista_palavras"]),
        "mes": mes_para_baixar,
    }

    html_template = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Dashboard - Empresas Comex em Cotia</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <div class="container">
    <header>
      <div class="header-content">
        <a href="https://fateccotia.cps.sp.gov.br/">
          <img src="https://bkpsitecpsnew.blob.core.windows.net/uploadsitecps/sites/115/2024/07/logo-fatec_cotia.png" 
               alt="Logo Fatec Cotia"
               class="logo">
        </a>
        <div class="header-text">
          <h1>Observatório Comex Cotia</h1>
          <p>{metodologia_html["mes"]}</p>
        </div>
      </div>
    </header>

    <div class="highlight">
      <h3>Resumo Geral</h3>
      <div class="metric-card">
        <strong>Total de empresas ativas em Cotia:</strong> {fmt(stats['total_empresas'])}<br>
        <strong>Total de empresas com atividades passíveis de comex:</strong> {fmt(stats['total_comex'])}<br>
        <strong>Percentual de empresas com atividade passíveis de comex:</strong> {stats['percentual_comex']:.2f}%<br>
        <strong>Total de empresas sem atividade Comex:</strong> {fmt(stats['total_nao_comex'])}
      </div>
    </div>

    <div class="highlight">
      <h3>Comex como Atividade Principal vs Secundária</h3>
      <div class="metric-card">
        <strong>Empresas com Comex como atividade PRINCIPAL:</strong> {fmt(stats['comex_principal'])} ({stats['pct_principal']:.1f}%)<br>
        <strong>Empresas com Comex como atividade SECUNDÁRIA:</strong> {fmt(stats['comex_secundaria'])} ({stats['pct_secundaria']:.1f}%)
      </div>
    </div>

    <div class="highlight">
      <h3>Tempo Médio de Atividade</h3>
      <div class="age-comparison">
        <div class="age-card">
          <h4>Geral (Todas as empresas)</h4>
          <div class="metric-card">
            <strong>Idade média:</strong> {stats['idade_media_geral']}<br>
            <strong>Idade mediana:</strong> {stats['idade_mediana_geral']}<br>
            <strong>Empresa mais antiga:</strong> {stats['idade_max']}<br>
            <strong>Empresa mais nova:</strong> {stats['idade_min']}
          </div>
        </div>
        <div class="age-card">
          <h4>Empresas COMEX</h4>
          <div class="metric-card">
            <strong>Idade média:</strong> {stats['idade_comex_media']}<br>
            <strong>Idade mediana:</strong> {stats['idade_comex_mediana']}<br>
            <strong>Empresa mais antiga:</strong> {stats['idade_comex_max']}<br>
            <strong>Empresa mais nova:</strong> {stats['idade_comex_min']}
          </div>
        </div>
      </div>
    </div>

    <div class="highlight">
      <h3>Crescimento Acumulado (Últimos 12 Meses)</h3>
      <div class="growth-comparison">
        <div class="growth-card">
          <h4>Geral (Todas as empresas)</h4>
          <div class="metric-card">
            <strong>Crescimento:</strong> {stats['crescimento_total_periodo']:+.2f}%<br>
            De {fmt(stats['total_inicial'])} para {fmt(stats['total_final'])} empresas<br>
            Diferença: {fmt(stats['dif_total'])} empresas
          </div>
        </div>
        <div class="growth-card">
          <h4>Empresas COMEX</h4>
          <div class="metric-card comex-highlight">
            <strong>Crescimento:</strong> {stats['crescimento_comex_periodo']:+.2f}%<br>
            De {fmt(stats['comex_inicial'])} para {fmt(stats['comex_final'])} empresas<br>
            Diferença: {fmt(stats['dif_comex'])} empresas
          </div>
        </div>
      </div>
    </div>

    <h2>Gráficos Temporais</h2>
    <div class="plot-container"><iframe src="graficos/crescimento_anual_empresas.html"></iframe></div>
    <div class="plot-container"><iframe src="graficos/crescimento_acumulado_mensal.html"></iframe></div>
    <div class="plot-container"><iframe src="graficos/evolucao_mensal_empresas.html"></iframe></div>
    <hr class="linha">
    <div class="plot-container"><iframe src="graficos/crescimento_anual_empresas_indice100.html"></iframe></div>
    <div class="plot-container"><iframe src="graficos/crescimento_acumulado_mensal_indice100.html"></iframe></div>
    <div class="plot-container"><iframe src="graficos/evolucao_mensal_empresas_indice100.html"></iframe></div>
    
    <h2>Análise Geográfica</h2>
    <div class="plot-container"><iframe src="graficos/top_20_bairros_comparativo.html"></iframe></div>
    <div class="plot-container"><iframe src="graficos/bairros_concentracao_comex.html"></iframe></div>
    <div class="plot-container"><iframe src="graficos/top_10_bairros_comex_barras.html"></iframe></div>

    <h2>Metodologia</h2>
    <div class="methodology-section">
      <p>Base de dados utilizada disponível em: <a href="https://dados.gov.br/dados/conjuntos-dados/cadastro-nacional-da-pessoa-juridica---cnpj">Cadastro Nacional da Pessoa Jurídica - CNPJ</a></p>
      <p>
        Este dashboard analisa empresas passíveis de Comércio Exterior em Cotia/SP com status de atividade "Aberta" no mês {metodologia_html["mes"]}, com base em dois critérios complementares:
        atividade econômica (CNAE) e palavras-chave em razão social ou nome fantasia.<br><br>
        A classificação é feita usando um arquivo de referência com regras manuais para garantir precisão e evitar falsos positivos.
      </p>
      
      <h3>Critérios de classificação</h3>
      <p>As empresas são consideradas Comex se atenderem ao menos um dos critérios abaixo e não estiverem em categorias rejeitadas:</p>

      <div class="criteria-grid">
        <div class="criterion accept">
          <h4>Aceita</h4>
          <p>Empresas com CNAE marcado como <strong>"Aceita"</strong> <strong>OU</strong> que contenham <strong>palavras-chave</strong> em razão social/nome fantasia.</p>
          <p><em>Exemplo de palavra-chave: "exportação", "importação", "internacional", "trade", etc.</em></p>
        </div>
        <div class="criterion reject">
          <h4>Rejeita</h4>
          <p>Empresas com CNAE marcado como <strong>"Rejeita"</strong> são <strong>excluídas</strong>, mesmo que atendam aos critérios positivos. Evitar falsos positivos.</p>
          <p><em>Exemplo real: empresa com nome "Igreja Internacional" (contém "internacional") mas CNAE religioso → <strong>rejeitada</strong>.</em></p>
        </div>
        <div class="criterion neutral">
          <h4>Ok</h4>
          <p>Empresas com CNAE marcado como <strong>"Ok"</strong> são consideradas <strong>não-Comex</strong> por padrão, a menos que atendam a critérios de nome.</p>
        </div>
      </div>

      <h3>Fluxo de classificação</h3>
      <ol>
        <li>Busca por palavras-chave em <em>razão social</em> e <em>nome fantasia</em> (normalizados: sem acentos, minúsculas);</li>
        <li>Verificação de CNAE principal e CNAEs secundários;</li>
        <li>Aplicação de regras: <strong>ACEITA</strong> se (palavra-chave ou CNAE aceito) e <strong>NÃO</strong> (CNAE rejeitado);</li>
        <li>Resultado: coluna <code>is_comex = True/False</code> no dataset final.</li>
      </ol>

      <h3>Palavras-chave utilizadas na busca</h3>
      <p>Foram usadas <strong>{metodologia_html['total_palavras']}</strong> palavras ou expressões para identificar empresas com atividade passíveis de comércio exterior:</p>
      <div class="criteria-list">{metodologia_html['palavras_chave']}</div>

      <h3>CNAEs considerados como <span class="tag accept">Aceita</span></h3>
      <p><strong>{metodologia_html['total_aceitos']}</strong> classes CNAE foram marcadas como atividade de Comex:</p>
      <div class="criteria-list">{metodologia_html['cnaes_aceitos']}</div>

      <h3>CNAEs marcados como <span class="tag reject">Rejeita</span></h3>
      <p><strong>{metodologia_html['total_rejeitados']}</strong> classes CNAE foram excluídas para evitar falsos positivos (ex: instituições religiosas, entidades sem fins lucrativos):</p>
      <div class="criteria-list">{metodologia_html['cnaes_rejeitados']}</div>
    </div>
  </div>
</body>
</html>
"""

    with open("dashboard.html", "w", encoding="utf-8") as f:
        f.write(html_template)

    print("Dashboard HTML gerado com sucesso: dashboard.html")


def montar_indicadores(dados: dict, mes_referencia: str) -> pd.DataFrame:
    """Tabela agregada (sem dados por empresa) para o D1."""
    linhas = []

    def add(indicador, dimensao, total=None, comex=None, nao_comex=None):
        linhas.append({"mes_referencia": mes_referencia, "indicador": indicador,
                       "dimensao": str(dimensao), "total": total,
                       "comex": comex, "nao_comex": nao_comex})

    def r(x):
        return None if x is None else round(float(x), 2)

    s = dados["stats"]
    add("resumo", "empresas_ativas", s["total_empresas"], s["total_comex"], s["total_nao_comex"])
    add("comex_tipo_cnae", "principal", comex=s["comex_principal"])
    add("comex_tipo_cnae", "secundaria", comex=s["comex_secundaria"])

    for chave in ["media", "mediana", "minimo", "maximo"]:
        add("idade_anos", chave, total=r(dados["idade_raw"]["total"][chave]),
            comex=r(dados["idade_raw"]["comex"][chave]))

    for indicador, chave_df, col in [("abertura_anual", "df_grafico_anual", "ano"),
                                     ("abertura_mensal", "df_grafico_mensal", "ano_mes"),
                                     ("acumulado_mensal", "df_crescimento_acumulado", "ano_mes")]:
        for _, l in dados[chave_df].iterrows():
            add(indicador, l[col], int(l["total"]), int(l["comex"]), int(l["nao_comex"]))

    # Bairros pequenos ficam de fora para não individualizar
    grandes = dados["dist_bairros"].filter(pl.col("total_empresas") >= config.MIN_EMPRESAS_BAIRRO)
    for l in grandes.iter_rows(named=True):
        add("bairro", l["bairro_padronizado"], l["total_empresas"], l["total_comex"],
            l["total_empresas"] - l["total_comex"])

    return pd.DataFrame(linhas)