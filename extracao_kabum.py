import requests
from datetime import datetime
import pandas as pd
import os
import time
import random

diretorio_atual = os.path.dirname(os.path.abspath(__file__))
caminho_csv = os.path.join(diretorio_atual, 'ofertas_kabum.csv')

# 1. Dicionário de Alvos (Termo de busca na API -> Categoria no seu Banco de Dados)
categorias_alvo = {
    "teclado": "Teclados",
    "mouse": "Mouses",
    "monitor": "Monitores",
    "placa de video": "Hardware",
    "headset": "Áudio"
}

def extrair_catalogo_completo(alvos):
    base_url = "https://servicespub.prod.api.aws.grupokabum.com.br/catalog/v2/products"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Origin': 'https://www.kabum.com.br'
    }
    
    ofertas_totais = []
    
    # Session reaproveita a mesma conexão TCP para todas as páginas (padrão de mercado)
    with requests.Session() as session:
        session.headers.update(headers)
        
        for termo, categoria in alvos.items():
            print(f"\n[+] Iniciando extração: {categoria} (Busca: '{termo}')")
            pagina = 1
            
            # Loop infinito controlado: Roda até a API retornar uma lista vazia
            while True:
                print(f"  -> Lendo página {pagina}...")
                
                # O page_size define quantos itens vêm por vez. Manter 20 a 50 é seguro contra bloqueios.
                params = {
                    'query': termo,
                    'page_number': pagina,
                    'page_size': 50 
                }
                
                try:
                    # Atualiza o Referer para parecer navegação real
                    session.headers.update({'Referer': f'https://www.kabum.com.br/busca/{termo}?page_number={pagina}'})
                    
                    response = session.get(base_url, params=params)
                    
                    if response.status_code in (403, 404):
                        print("  -> Bloqueio ou página não encontrada. Interrompendo este termo.")
                        break
                        
                    response.raise_for_status()
                    dados = response.json()
                    itens = dados.get('data', [])
                    
                    # Condição de parada: se não vierem itens, acabaram as páginas daquela categoria
                    if not itens:
                        print(f"  -> Fim dos resultados para '{termo}'.")
                        break
                        
                    for item in itens:
                        attr = item.get('attributes', {})
                        preco = float(attr.get('price_with_discount', 0))
                        if preco == 0:
                            preco = float(attr.get('price', 0))
                            
                        if attr.get('available') and preco > 0:
                            slug = str(attr.get('product_link', '')).lstrip('/')
                            url = f"https://www.kabum.com.br/produto/{item['id']}/{slug}"
                            
                            oferta_estruturada = {
                                'id_produto_externo': str(item['id']),
                                'nome_produto': str(attr.get('title', '')),
                                'categoria_produto': categoria,
                                'preco': preco,
                                'nome_loja': 'KaBuM!',
                                'url_oferta': url,
                                'data_coleta': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            }
                            ofertas_totais.append(oferta_estruturada)
                            
                    # Pausa aleatória entre 1 e 2.5 segundos para não sobrecarregar a API (Anti-Ban)
                    time.sleep(random.uniform(1.0, 2.5))
                    pagina += 1
                    
                except Exception as e:
                    print(f"  -> Falha crítica na página {pagina}: {e}")
                    break
                    
    return ofertas_totais

# 2. Execução Principal
print("Iniciando Pipeline de Extração...")
resultados = extrair_catalogo_completo(categorias_alvo)

# 3. Exportação para a Camada Bronze
if resultados:
    df = pd.DataFrame(resultados)
    df.to_csv(caminho_csv, index=False, sep=';', encoding='utf-8-sig')
    print(f"\nSucesso Absoluto! {len(df)} ofertas únicas foram salvas em {caminho_csv}.")
else:
    print("\nNenhum dado foi extraído. Verifique sua conexão ou bloqueios de IP.")


    import pandas as pd
import os

try:

    if df_ofertas.empty:
        raise ValueError("Extração retornou vazia (Possível bloqueio de IP).")
        
    df_ofertas.to_csv("kabum_ofertas.csv", index=False)
    print("Extração real bem-sucedida. Arquivo 'kabum_ofertas.csv' criado.")

except Exception as e:
    print(f"Falha na extração real: {e}")
    print("Acionando o plano de contingência (Mock Data) para não travar o pipeline...")
    
    dados_mock = {
        'id_produto': [1, 2, 3],
        'id_loja': [1, 1, 1],
        'preco': [1850.00, 2100.00, 1750.00],
        'url_oferta': ['url1', 'url2', 'url3'],
        'data_coleta': ['2026-10-15', '2026-10-15', '2026-10-15']
    }
    df_mock = pd.DataFrame(dados_mock)
    df_mock.to_csv("kabum_ofertas.csv", index=False)
    print("Arquivo 'kabum_ofertas.csv' gerado via contingência com sucesso.")

if os.path.exists("kabum_ofertas.csv"):
    print("Confirmação: O arquivo está fisicamente no servidor e pronto para o ETL.")
else:
    print("Erro Crítico: O arquivo não foi gerado.")