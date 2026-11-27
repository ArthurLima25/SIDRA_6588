from pathlib import Path
import time
import pandas as pd
import requests
import sidrapy

TABELA = '6588'
UF_CODIGO = '29'  # Bahia
VARIAVEIS = '109,35'  # 109 = Área plantada | 35 = Produção
TAMANHO_LOTE = 24  # Meses por pedido para evitar limites da API
PASTA_SAIDA = Path('saida')


def obter_metadados_6588() -> tuple[dict[str, str], list[str]]:
  """Obtém classificações e todos os períodos disponíveis na tabela."""
  url_meta = (
      f'https://servicodados.ibge.gov.br/api/v3/agregados/{TABELA}/metadados'
  )
  resp_meta = requests.get(url_meta, timeout=30)
  resp_meta.raise_for_status()
  meta = resp_meta.json()

  classificacoes = {
      str(item['id']): 'all' for item in meta.get('classificacoes', [])
  }

  url_periodos = (
      f'https://servicodados.ibge.gov.br/api/v3/agregados/{TABELA}/periodos'
  )
  resp_per = requests.get(url_periodos, timeout=30)
  resp_per.raise_for_status()
  periodos = [str(p['id']) for p in resp_per.json()]

  return classificacoes, periodos


def baixar_serie_completa() -> pd.DataFrame:
  classificacoes, periodos = obter_metadados_6588()
  print(f'Total de períodos encontrados: {len(periodos)}')
  print('Classificações:', classificacoes)

  partes = []
  for i in range(0, len(periodos), TAMANHO_LOTE):
    lote = periodos[i : i + TAMANHO_LOTE]
    periodo_str = ','.join(lote)
    print(f'A transferir {lote[0]} até {lote[-1]}...')

    dados = sidrapy.get_table(
        table_code=TABELA,
        territorial_level='3',
        ibge_territorial_code=UF_CODIGO,
        variable=VARIAVEIS,
        period=periodo_str,
        classifications=classificacoes if classificacoes else None,
        header='n',
        format='list',
    )

    if dados:
      partes.append(pd.DataFrame(dados))

    time.sleep(0.5)

  df = pd.concat(partes, ignore_index=True)

  if 'V' in df.columns:
    df['V'] = pd.to_numeric(df['V'], errors='coerce')

  return df


def exportar_arquivos(df: pd.DataFrame, pasta: Path, prefixo: str) -> None:
  """Exporta o DataFrame para XLSX, CSV, JSON e TSV."""
  pasta.mkdir(parents=True, exist_ok=True)

  arq_xlsx = pasta / f'{prefixo}.xlsx'
  arq_csv = pasta / f'{prefixo}.csv'
  arq_json = pasta / f'{prefixo}.json'
  arq_tsv = pasta / f'{prefixo}.tsv'

  df.to_excel(arq_xlsx, index=False, sheet_name=f'Bahia_{TABELA}')
  df.to_csv(arq_csv, index=False, sep=',', decimal='.', encoding='utf-8-sig')
  df.to_json(arq_json, orient='records', force_ascii=False, indent=2)
  df.to_csv(arq_tsv, sep='\t', index=False, encoding='utf-8-sig')

  print(f'Ficheiros gerados com sucesso em {pasta.resolve()}:')
  print(f'  - {arq_xlsx.name}')
  print(f'  - {arq_csv.name}')
  print(f'  - {arq_json.name}')
  print(f'  - {arq_tsv.name}')


if __name__ == '__main__':
  df_historico = baixar_serie_completa()
  prefixo = f'SIDRA_bahia_{TABELA}_serie_completa'
  exportar_arquivos(df_historico, PASTA_SAIDA, prefixo)
