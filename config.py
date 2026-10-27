import os
from datetime import datetime

# --- CREDENCIAIS E URLS ---
NC_HOST = "https://arquivos.receitafederal.gov.br"
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
# Lê da variável de ambiente no GitHub Actions (com fallback local apenas para testes se desejar, mas idealmente via .env)
NC_SHARE_TOKEN = os.environ.get("NC_SHARE_TOKEN", "")
BASE_URL = f"{NC_HOST}/public.php/webdav/Dados/Cadastros/CNPJ/"

URL_EXCEL_FILTRO = "https://docs.google.com/spreadsheets/d/1hILH0eUnzQKG2XWmpXGRytSfO8c6VM4Q/export?format=xlsx"

# --- PARÂMETROS DE NEGÓCIO ---
MUNICIPIO_ALVO = "6361"        # Cotia
NOME_MUNICIPIO = "COTIA"
SITUACAO_CADASTRAL = "02"      # Ativa
NUM_ARQUIVOS = int(os.environ.get("NUM_ARQUIVOS", "10"))
DOWNLOADS_PARALELOS = int(os.environ.get("DOWNLOADS_PARALELOS", "4"))
TIMEOUT_SECONDS = 120

# --- DIRETÓRIOS ---
DIR_EMPRESAS = "empresas"
DIR_ESTABELECIMENTOS = "estabelecimentos"
DIR_UNICOS = "arquivos_unicos"
DIR_OUTPUTS = "outputs"
DIR_GRAFICOS = "graficos"
DIR_CACHE = "cache"
MIN_EMPRESAS_BAIRRO = 10
DIR_TABELAS = os.path.join(DIR_OUTPUTS, "tabelas")


DIRETORIOS = [
    DIR_EMPRESAS,
    DIR_ESTABELECIMENTOS,
    DIR_UNICOS,
    DIR_OUTPUTS,
    DIR_GRAFICOS,
    DIR_TABELAS,
    DIR_CACHE,
]

# --- CONTROLE DE EXPORTAÇÃO E DATA ---
# Por padrão False para não expor dados individuais fora do repositório/Cloudflare
EXPORTAR_EXCEL_INDIVIDUAL = os.environ.get("EXPORT_INDIVIDUAL_DATA", "false").lower() == "true"

# Permite forçar uma data de referência via env (formato YYYY-MM-DD), senão usa a data atual
DATA_REF_ENV = os.environ.get("DATA_REFERENCIA", "")


def obter_data_referencia() -> datetime:
    if DATA_REF_ENV:
        return datetime.strptime(DATA_REF_ENV, "%Y-%m-%d")
    return datetime.today()


def criar_diretorios_base():
    for d in DIRETORIOS:
        os.makedirs(d, exist_ok=True)