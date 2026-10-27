import os
import config
import etl
import dashboard
import charts
import polars as pl

def main():
    print("=== INICIANDO PIPELINE OBSERVATÓRIO COMEX COTIA ===")
    config.criar_diretorios_base()
    data_ref = config.obter_data_referencia()

    # 1. ETL (Download 1 zip por vez, filtro Cotia, junção e classificação Comex)
    df_final, df_comex, metadados_filtro, mes_baixado = etl.executar_etl(data_ref)

    # 2. Estatísticas (Idade, Crescimento e Bairros)
    print("\nCalculando estatísticas e agregações...")
    dados_estatisticos = dashboard.calcular_estatisticas(
        df_final=df_final,
        df_comex=df_comex,
        metadados_filtro=metadados_filtro,
        data_ref=data_ref,
    )

    # 3. Gráficos Plotly (6 temporais + 3 geográficos)
    print("\nGerando gráficos interativos...")
    charts.gerar_todos_os_graficos(dados_estatisticos)

    # 4. Geração do dashboard.html
    print("\nMontando dashboard HTML...")
    dashboard.gerar_dashboard_html(
        dados_estatisticos=dados_estatisticos,
        metadados_filtro=metadados_filtro,
        mes_para_baixar=mes_baixado,
    )
    if not os.path.exists("dashboard.html"):
        raise FileNotFoundError("dashboard.html não foi gerado")
    
        # Tabelas para o banco (D1)
    print("\nGerando tabelas para o banco...")
    os.makedirs(config.DIR_TABELAS, exist_ok=True)
    (df_comex.with_columns(pl.lit(mes_baixado).alias("mes_referencia"))
             .drop("is_comex")
             .write_csv(f"{config.DIR_TABELAS}/empresas_comex.csv"))
    dashboard.montar_indicadores(dados_estatisticos, mes_baixado).to_csv(
        f"{config.DIR_TABELAS}/indicadores.csv", index=False)

    # 5. Exportação (Controlada para não vazar dados individuais no deploy da Cloudflare)
    if config.EXPORTAR_EXCEL_INDIVIDUAL:
        caminho_excel = f"{config.DIR_OUTPUTS}/final {mes_baixado}.xlsx"
        print(f"\nExportando base individual para uso local: {caminho_excel}")
        df_final.write_excel(caminho_excel)
    else:
        print("\n[Segurança] Exportação de planilha individual ignorada (EXPORT_INDIVIDUAL_DATA=false).")

    print("\n=== PIPELINE FINALIZADO COM SUCESSO! ===")


if __name__ == "__main__":
    main()