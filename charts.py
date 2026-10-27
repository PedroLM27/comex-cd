import os
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import config


def calcular_indice_base_100(series: pd.Series) -> pd.Series:
    if len(series) == 0 or series.iloc[0] == 0:
        return pd.Series([100] * len(series))
    return (series / series.iloc[0]) * 100


def gerar_todos_os_graficos(dados_estatisticos: dict):
    os.makedirs(config.DIR_GRAFICOS, exist_ok=True)

    df_grafico_anual = dados_estatisticos["df_grafico_anual"].copy()
    df_grafico_mensal = dados_estatisticos["df_grafico_mensal"].copy()
    df_crescimento_acumulado = dados_estatisticos["df_crescimento_acumulado"].copy()
    top_20_df = dados_estatisticos["top_20_geral"].to_pandas()
    concentracao_df = dados_estatisticos["bairros_concentracao"].to_pandas()
    top_10_comex_df = dados_estatisticos["top_10_comex"].to_pandas()

    # ==========================================
    # 1. CRESCIMENTO ANUAL (ABSOLUTO)
    # ==========================================
    fig_anual = go.Figure()
    fig_anual.add_trace(go.Scatter(
        x=df_grafico_anual["ano"], y=df_grafico_anual["total"],
        mode="lines+markers", name="Total", line=dict(color="#1f77b4", width=3), marker=dict(size=8),
        hovertemplate="<b>Ano:</b> %{x}<br><b>Total:</b> %{y:,}<extra></extra>"
    ))
    fig_anual.add_trace(go.Scatter(
        x=df_grafico_anual["ano"], y=df_grafico_anual["comex"],
        mode="lines+markers", name="Comex", line=dict(color="#2ca02c", width=3), marker=dict(size=8),
        hovertemplate="<b>Ano:</b> %{x}<br><b>Comex:</b> %{y:,}<extra></extra>"
    ))
    fig_anual.add_trace(go.Scatter(
        x=df_grafico_anual["ano"], y=df_grafico_anual["nao_comex"],
        mode="lines+markers", name="Não-Comex", line=dict(color="#ff7f0e", width=3), marker=dict(size=8),
        hovertemplate="<b>Ano:</b> %{x}<br><b>Não-Comex:</b> %{y:,}<extra></extra>"
    ))
    fig_anual.update_layout(
        title={"text": "<b>Crescimento Anual de Empresas - Últimos 10 Anos</b><br><sub>Cotia/SP</sub>", "x": 0.5, "xanchor": "center", "font": {"size": 20}},
        xaxis_title="<b>Ano</b>", yaxis_title="<b>Número de Empresas Abertas</b>",
        hovermode="x unified", template="plotly_white", font=dict(size=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        autosize=True, xaxis=dict(dtick=1, tickmode="linear"), yaxis=dict(gridcolor="lightgray", gridwidth=0.5)
    )
    fig_anual.write_html(f"{config.DIR_GRAFICOS}/crescimento_anual_empresas.html", include_plotlyjs="cdn")

    # ==========================================
    # 2. EVOLUÇÃO MENSAL (ABSOLUTO)
    # ==========================================
    fig_mensal = go.Figure()
    fig_mensal.add_trace(go.Scatter(
        x=df_grafico_mensal["mes_formatado"], y=df_grafico_mensal["total"],
        mode="lines+markers", name="Total", line=dict(color="#1f77b4", width=3), marker=dict(size=10),
        hovertemplate="<b>Mês:</b> %{x}<br><b>Total:</b> %{y:,}<extra></extra>"
    ))
    fig_mensal.add_trace(go.Scatter(
        x=df_grafico_mensal["mes_formatado"], y=df_grafico_mensal["comex"],
        mode="lines+markers", name="Comex", line=dict(color="#2ca02c", width=3), marker=dict(size=10),
        hovertemplate="<b>Mês:</b> %{x}<br><b>Comex:</b> %{y:,}<extra></extra>"
    ))
    fig_mensal.add_trace(go.Scatter(
        x=df_grafico_mensal["mes_formatado"], y=df_grafico_mensal["nao_comex"],
        mode="lines+markers", name="Não-Comex", line=dict(color="#ff7f0e", width=3), marker=dict(size=10),
        hovertemplate="<b>Mês:</b> %{x}<br><b>Não-Comex:</b> %{y:,}<extra></extra>"
    ))
    fig_mensal.update_layout(
        title={"text": "<b>Evolução Mensal de Abertura de Empresas - Últimos 12 Meses</b><br><sub>Cotia/SP</sub>", "x": 0.5, "xanchor": "center", "font": {"size": 20}},
        xaxis_title="<b>Mês</b>", yaxis_title="<b>Número de Empresas Abertas</b>",
        hovermode="x unified", template="plotly_white", font=dict(size=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        autosize=True, xaxis=dict(tickangle=-45), yaxis=dict(gridcolor="lightgray", gridwidth=0.5)
    )
    fig_mensal.write_html(f"{config.DIR_GRAFICOS}/evolucao_mensal_empresas.html", include_plotlyjs="cdn")

    # ==========================================
    # 3. CRESCIMENTO ACUMULADO MENSAL (ABSOLUTO)
    # ==========================================
    fig_crescimento = make_subplots(specs=[[{"secondary_y": True}]])
    for col, nome, cor in [("total", "Total", "#1f77b4"), ("comex", "Comex", "#2ca02c"), ("nao_comex", "Não-Comex", "#ff7f0e")]:
        fig_crescimento.add_trace(
            go.Scatter(
                x=df_crescimento_acumulado["mes_formatado"], y=df_crescimento_acumulado[col],
                mode="lines+markers", name=nome, line=dict(color=cor, width=3), marker=dict(size=8),
                hovertemplate=f"<b>Mês:</b> %{{x}}<br><b>{nome}:</b> %{{y:,}}<br><extra></extra>"
            ),
            secondary_y=False
        )
    fig_crescimento.update_layout(
        title={"text": "<b>Crescimento acumulado de Empresas - Últimos 12 Meses</b><br><sub>Cotia/SP</sub>", "x": 0.5, "xanchor": "center", "font": {"size": 20}},
        hovermode="x unified", template="plotly_white", font=dict(size=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=0.94),
        autosize=True, margin=dict(l=80, r=20, t=100, b=80),
        xaxis=dict(title="<b>Mês</b>", tickangle=-45, showgrid=True, gridcolor="lightgray", gridwidth=0.5)
    )
    fig_crescimento.update_yaxes(title_text="<b>Número de Empresas Abertas</b>", secondary_y=False, gridcolor="lightgray", gridwidth=0.5)
    fig_crescimento.write_html(f"{config.DIR_GRAFICOS}/crescimento_acumulado_mensal.html", include_plotlyjs="cdn")

    # ==========================================
    # 4. CRESCIMENTO ANUAL (ÍNDICE BASE 100)
    # ==========================================
    df_grafico_anual["total_indice"] = calcular_indice_base_100(df_grafico_anual["total"])
    df_grafico_anual["comex_indice"] = calcular_indice_base_100(df_grafico_anual["comex"])
    df_grafico_anual["nao_comex_indice"] = calcular_indice_base_100(df_grafico_anual["nao_comex"])

    fig_anual_100 = go.Figure()
    for col, col_ind, nome, cor in [
        ("total", "total_indice", "Total", "#1f77b4"),
        ("comex", "comex_indice", "Comex", "#2ca02c"),
        ("nao_comex", "nao_comex_indice", "Não-Comex", "#ff7f0e"),
    ]:
        fig_anual_100.add_trace(go.Scatter(
            x=df_grafico_anual["ano"], y=df_grafico_anual[col_ind],
            mode="lines+markers", name=nome, line=dict(color=cor, width=3), marker=dict(size=8),
            customdata=list(zip(df_grafico_anual[col], df_grafico_anual[col_ind])),
            hovertemplate=f"<b>Ano:</b> %{{x}}<br><b>{nome}:</b> %{{customdata[0]:,}} empresas<br><b>Índice:</b> %{{customdata[1]:.1f}}<br><extra></extra>"
        ))
    fig_anual_100.add_hline(y=100, line_dash="dash", line_color="gray", opacity=0.5, annotation_text="Base (100)", annotation_position="right")
    fig_anual_100.update_layout(
        title={"text": f"<b>Crescimento Anual de Empresas - Índice Base 100</b><br><sub>Base: {df_grafico_anual['ano'].iloc[0]} = 100 | Cotia/SP</sub>", "x": 0.5, "xanchor": "center", "font": {"size": 20}},
        xaxis_title="<b>Ano</b>", yaxis_title="<b>Índice (Base 100)</b>",
        hovermode="x unified", template="plotly_white", font=dict(size=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=500, xaxis=dict(dtick=1, tickmode="linear"), yaxis=dict(gridcolor="lightgray", gridwidth=0.5)
    )
    fig_anual_100.write_html(f"{config.DIR_GRAFICOS}/crescimento_anual_empresas_indice100.html", include_plotlyjs="cdn")

    # ==========================================
    # 5. EVOLUÇÃO MENSAL (ÍNDICE BASE 100)
    # ==========================================
    df_grafico_mensal["total_indice"] = calcular_indice_base_100(df_grafico_mensal["total"])
    df_grafico_mensal["comex_indice"] = calcular_indice_base_100(df_grafico_mensal["comex"])
    df_grafico_mensal["nao_comex_indice"] = calcular_indice_base_100(df_grafico_mensal["nao_comex"])

    fig_mensal_100 = go.Figure()
    for col, col_ind, nome, cor in [
        ("total", "total_indice", "Total", "#1f77b4"),
        ("comex", "comex_indice", "Comex", "#2ca02c"),
        ("nao_comex", "nao_comex_indice", "Não-Comex", "#ff7f0e"),
    ]:
        fig_mensal_100.add_trace(go.Scatter(
            x=df_grafico_mensal["mes_formatado"], y=df_grafico_mensal[col_ind],
            mode="lines+markers", name=nome, line=dict(color=cor, width=3), marker=dict(size=10),
            customdata=list(zip(df_grafico_mensal[col], df_grafico_mensal[col_ind])),
            hovertemplate=f"<b>Mês:</b> %{{x}}<br><b>{nome}:</b> %{{customdata[0]:,}} empresas<br><b>Índice:</b> %{{customdata[1]:.1f}}<br><extra></extra>"
        ))
    fig_mensal_100.add_hline(y=100, line_dash="dash", line_color="gray", opacity=0.5, annotation_text="Base (100)", annotation_position="right")
    fig_mensal_100.update_layout(
        title={"text": f"<b>Evolução Mensal de Abertura de Empresas - Índice Base 100</b><br><sub>Base: {df_grafico_mensal['mes_formatado'].iloc[0]} = 100 | Cotia/SP</sub>", "x": 0.5, "xanchor": "center", "font": {"size": 20}},
        xaxis_title="<b>Mês</b>", yaxis_title="<b>Índice (Base 100)</b>",
        hovermode="x unified", template="plotly_white", font=dict(size=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        autosize=True, xaxis=dict(tickangle=-45), yaxis=dict(gridcolor="lightgray", gridwidth=0.5)
    )
    fig_mensal_100.write_html(f"{config.DIR_GRAFICOS}/evolucao_mensal_empresas_indice100.html", include_plotlyjs="cdn")

    # ==========================================
    # 6. CRESCIMENTO ACUMULADO (ÍNDICE BASE 100)
    # ==========================================
    df_cres = df_crescimento_acumulado.copy()
    df_cres["total_indice"] = calcular_indice_base_100(df_cres["total"])
    df_cres["comex_indice"] = calcular_indice_base_100(df_cres["comex"])
    df_cres["nao_comex_indice"] = calcular_indice_base_100(df_cres["nao_comex"])

    fig_cres_100 = go.Figure()
    fig_cres_100.add_trace(go.Scatter(
        x=df_cres["mes_formatado"], y=df_cres["total_indice"],
        mode="lines+markers", name="Total de Empresas", line=dict(color="#1f77b4", width=3), marker=dict(size=10),
        customdata=list(zip(df_cres["total"], df_cres["total_indice"], df_cres["crescimento_total_pct"].fillna(0))),
        hovertemplate="<b>Mês:</b> %{x}<br><b>Total:</b> %{customdata[0]:,} empresas<br><b>Índice:</b> %{customdata[1]:.1f}<br><b>Crescimento:</b> %{customdata[2]:.2f}%<br><extra></extra>"
    ))
    fig_cres_100.add_trace(go.Scatter(
        x=df_cres["mes_formatado"], y=df_cres["comex_indice"],
        mode="lines+markers", name="Empresas Comex", line=dict(color="#2ca02c", width=3), marker=dict(size=10),
        customdata=list(zip(df_cres["comex"], df_cres["comex_indice"])),
        hovertemplate="<b>Mês:</b> %{x}<br><b>Comex:</b> %{customdata[0]:,} empresas<br><b>Índice:</b> %{customdata[1]:.1f}<br><extra></extra>"
    ))
    fig_cres_100.add_trace(go.Scatter(
        x=df_cres["mes_formatado"], y=df_cres["nao_comex_indice"],
        mode="lines+markers", name="Empresas Não-Comex", line=dict(color="#ff7f0e", width=3), marker=dict(size=10),
        customdata=list(zip(df_cres["nao_comex"], df_cres["nao_comex_indice"])),
        hovertemplate="<b>Mês:</b> %{x}<br><b>Não-Comex:</b> %{customdata[0]:,} empresas<br><b>Índice:</b> %{customdata[1]:.1f}<br><extra></extra>"
    ))
    fig_cres_100.add_hline(y=100, line_dash="dash", line_color="gray", opacity=0.5, annotation_text="Base (100)", annotation_position="right")
    fig_cres_100.update_layout(
        title={"text": f"<b>Crescimento Acumulado de Empresas - Índice Base 100</b><br><sub>Base: {df_cres['mes_formatado'].iloc[0]} = 100 | Cotia/SP</sub>", "x": 0.5, "xanchor": "center", "font": {"size": 20}},
        xaxis_title="<b>Mês</b>", yaxis_title="<b>Índice (Base 100)</b>",
        hovermode="x unified", template="plotly_white", font=dict(size=12),
        legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.05, font=dict(size=11)),
        autosize=True, xaxis=dict(tickangle=-45), yaxis=dict(gridcolor="lightgray", gridwidth=0.5)
    )
    fig_cres_100.write_html(f"{config.DIR_GRAFICOS}/crescimento_acumulado_mensal_indice100.html", include_plotlyjs="cdn")

    # ==========================================
    # 7. GEOGRÁFICO: TOP 20 BAIRROS COMPARATIVO
    # ==========================================
    fig_bairros = go.Figure()
    fig_bairros.add_trace(go.Bar(
        y=top_20_df["bairro_padronizado"], x=top_20_df["total_empresas"],
        name="Total de Empresas", orientation="h", marker=dict(color="#1f77b4"),
        hovertemplate="<b>%{y}</b><br>Total: %{x:,}<extra></extra>"
    ))
    fig_bairros.add_trace(go.Bar(
        y=top_20_df["bairro_padronizado"], x=top_20_df["total_comex"],
        name="Empresas Comex", orientation="h", marker=dict(color="#2ca02c"),
        hovertemplate="<b>%{y}</b><br>Comex: %{x:,}<extra></extra>"
    ))
    fig_bairros.update_layout(
        title={"text": "<b>Top 20 Bairros com Mais Empresas</b><br><sub>Comparativo: Total vs Comex - Cotia/SP</sub>", "x": 0.5, "xanchor": "center", "font": {"size": 20}},
        xaxis_title="<b>Número de Empresas</b>", yaxis_title="<b>Bairro</b>",
        barmode="group", template="plotly_white", font=dict(size=11),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        autosize=True, yaxis=dict(autorange="reversed"), hovermode="y unified"
    )
    fig_bairros.write_html(f"{config.DIR_GRAFICOS}/top_20_bairros_comparativo.html", include_plotlyjs="cdn")

    # ==========================================
    # 8. GEOGRÁFICO: TOP 15 CONCENTRAÇÃO COMEX
    # ==========================================
    fig_concentracao = go.Figure()
    fig_concentracao.add_trace(go.Bar(
        y=concentracao_df["bairro_padronizado"], x=concentracao_df["percentual_comex"],
        orientation="h",
        marker=dict(color=concentracao_df["percentual_comex"], colorscale="Viridis", showscale=True, colorbar=dict(title="% Comex")),
        text=concentracao_df["percentual_comex"].round(1).astype(str) + "%", textposition="outside",
        hovertemplate="<b>%{y}</b><br>Percentual Comex: %{x:.1f}%<br>Comex: %{customdata[0]}<br>Total: %{customdata[1]}<extra></extra>",
        customdata=concentracao_df[["total_comex", "total_empresas"]]
    ))
    fig_concentracao.update_layout(
        title={"text": "<b>Top 15 Bairros com Maior Concentração de Comex</b><br><sub>Percentual de empresas Comex - Cotia/SP</sub>", "x": 0.5, "xanchor": "center", "font": {"size": 20}},
        xaxis_title="<b>Percentual de Empresas Comex (%)</b>", yaxis_title="<b>Bairro</b>",
        template="plotly_white", font=dict(size=11), showlegend=False, autosize=True,
        yaxis=dict(autorange="reversed"), xaxis=dict(range=[0, concentracao_df["percentual_comex"].max() * 1.15])
    )
    fig_concentracao.write_html(f"{config.DIR_GRAFICOS}/bairros_concentracao_comex.html", include_plotlyjs="cdn")

    # ==========================================
    # 9. GEOGRÁFICO: TOP 10 BAIRROS COMEX (BARRAS)
    # ==========================================
    bairros_lista = top_10_comex_df["bairro_padronizado"].tolist()
    valores_lista = top_10_comex_df["total_comex"].tolist()

    if sum(valores_lista) > 0:
        fig_barras = go.Figure()
        fig_barras.add_trace(go.Bar(
            y=bairros_lista[::-1], x=valores_lista[::-1],
            orientation="h",
            marker=dict(color="#2ca02c", line=dict(color="#1a5f1a", width=0.5)),
            text=valores_lista[::-1], textposition="auto",
            hovertemplate="<b>%{y}</b><br>Empresas Comex: %{x:,}<extra></extra>"
        ))
        fig_barras.update_layout(
            title={"text": "<b>Top 10 Bairros com Mais Empresas de Comex</b><br><sub>Cotia/SP</sub>", "x": 0.5, "xanchor": "center", "font": {"size": 20}},
            xaxis_title="<b>Número de Empresas Comex</b>", yaxis_title="<b>Bairro</b>",
            template="plotly_white", font=dict(size=12), autosize=True,
            margin=dict(l=150, r=50, t=100, b=50)
        )
        fig_barras.write_html(f"{config.DIR_GRAFICOS}/top_10_bairros_comex_barras.html", include_plotlyjs="cdn")

    print("\nTodos os 9 gráficos foram gerados na pasta 'graficos/'.")