import requests
from datetime import datetime
import pandas as pd
import os
import time
import random
import json
import re
from urllib.parse import quote_plus
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

diretorio_atual = os.path.dirname(os.path.abspath(__file__))

caminho_csv = os.path.join(diretorio_atual, 'ofertas_consolidadas.csv')

categorias_alvo = {
    "placa de vídeo": "Placas de vídeo",
    "processador ryzen": "Processadores",
    "processador intel": "Processadores",
    "placa mãe": "Placas Mãe",
    "memória ram": "Memórias Ram",
    "hd interno": "Armazenamento",
    "ssd": "Armazenamento",
    "fonte": "Fontes",
    "teclado": "Teclados",
    "fone-de-ouvido": "Audio",
    "microfone": "Audio",
    "mouse": "Mouses",
    "headset": "Audio"
}

# 1. KABUM

def extrair_kabum(alvos):
    base_url = "https://servicespub.prod.api.aws.grupokabum.com.br/catalog/v2/products"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Origin': 'https://www.kabum.com.br'
    }
    
    ofertas_totais = []
    
    with requests.Session() as session:
        session.headers.update(headers)
        
        for termo, categoria in alvos.items():
            print(f"\n[KaBuM] Extraindo: {categoria} (Busca: '{termo}')")
            pagina = 1
            
            while True:
                params = {
                    'query': termo,
                    'page_number': pagina,
                    'page_size': 50 
                }
                
                try:
                    session.headers.update({'Referer': f'https://www.kabum.com.br/busca/{termo}?page_number={pagina}'})
                    response = session.get(base_url, params=params)
                    
                    if response.status_code in (403, 404):
                        break
                        
                    response.raise_for_status()
                    dados = response.json()
                    itens = dados.get('data', [])

                    if not itens:
                        break
                        
                    for item in itens:
                        attr = item.get('attributes', {})
                        preco = float(attr.get('price_with_discount', 0))
                        if preco == 0:
                            preco = float(attr.get('price', 0))
                            
                        if attr.get('available') and preco > 0:
                            slug = str(attr.get('product_link', '')).lstrip('/')
                            url = f"https://www.kabum.com.br/produto/{item['id']}/{slug}"
                            
                            ofertas_totais.append({
                                'id_produto_externo': str(item['id']),
                                'nome_produto': str(attr.get('title', '')),
                                'categoria_produto': categoria,
                                'preco': preco,
                                'nome_loja': 'KaBuM!',
                                'url_oferta': url,
                                'data_coleta': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            })
                            
                    time.sleep(random.uniform(1.0, 2.5))
                    pagina += 1
                    
                except Exception as e:
                    print(f"  -> Falha na página {pagina}: {e}")
                    break
                    
    return ofertas_totais

# 2. AMAZON

def extrair_amazon(alvos):
    print("\n[Amazon] Iniciando extração via Selenium com Paginação...")
    ofertas_totais = []
    
    chrome_options = Options()
    chrome_options.add_argument('--headless') # Descomente para rodar em segundo plano
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    chrome_options.add_argument('--log-level=3') 
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        
        for termo, categoria in alvos.items():
            print(f"  -> Buscando: '{termo}'...")
            
            pagina = 1
            max_paginas = 70 # Defina quantas páginas deseja varrer por termo
            
            while pagina <= max_paginas:
                # A URL estruturada com o parâmetro de página que você descobriu
                url_busca = f"https://www.amazon.com.br/s?k={quote_plus(termo)}&page={pagina}"
                print(f"     Acessando página {pagina}...")
                
                driver.get(url_busca)
                time.sleep(random.uniform(3.0, 5.0)) # Pausa para o Javascript carregar os blocos
                
                sopa = BeautifulSoup(driver.page_source, "html.parser")
                blocos = sopa.select('div[data-component-type="s-search-result"]')
                
                # Se a página não retornar nenhum bloco de produto, chegamos ao fim do catálogo
                if not blocos:
                    print(f"     -> Fim dos resultados na página {pagina}.")
                    break
                
                produtos_nesta_pagina = 0
                for bloco in blocos:
                    asin = bloco.get("data-asin")
                    cabecalho = bloco.select_one("h2")
                    
                    if not asin or cabecalho is None:
                        continue
                        
                    titulo = cabecalho.get("aria-label") or cabecalho.get_text(" ", strip=True)
                    titulo = re.sub(r"^An[uú]ncio patrocinado\s*[–-]\s*", "", titulo)
                    
                    elemento_preco = bloco.select_one("span.a-price:not(.a-text-price) span.a-offscreen")
                    
                    if elemento_preco:
                        texto_preco = elemento_preco.get_text()
                        preco_limpo = texto_preco.replace('R$', '').replace('.', '').replace(',', '.').strip()
                        try:
                            ofertas_totais.append({
                                'id_produto_externo': asin,
                                'nome_produto': titulo,
                                'categoria_produto': categoria,
                                'preco': float(preco_limpo),
                                'nome_loja': 'Amazon',
                                'url_oferta': f"https://www.amazon.com.br/dp/{asin}",
                                'data_coleta': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            })
                            produtos_nesta_pagina += 1
                        except ValueError:
                            continue
                            
                print(f"     -> {produtos_nesta_pagina} produtos extraídos na página {pagina}.")
                pagina += 1
                
    except Exception as e:
        print(f"  -> Falha crítica na Amazon: {e}")
    finally:
        driver.quit()
        
    print(f"  -> Total de {len(ofertas_totais)} ofertas coletadas na Amazon.")
    return ofertas_totais


def _decodificar_texto(texto):
    """Função do colega: converte sequências como \u00e9 em caracteres normais."""
    try:
        return json.loads(f'"{texto}"')
    except ValueError:
        return texto

#def extrair_pichau(alvos_pichau):
    print("\n[Pichau] Iniciando extração via Selenium (Session Cycling para evitar o Pombo)...")
    ofertas_totais = []
    
    chrome_options = Options()
    # chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--log-level=3')
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    _PRODUTO = re.compile(r'"url_key":"([a-z0-9-]+)","name":"([^"]+)"')
    _AVISTA = re.compile(r'"pichau_prices":\{"avista":([0-9.]+)')
    _ESTOQUE = re.compile(r'"stock_status":"([A-Z_]+)"')
    _OPENBOX = re.compile(r'"is_openbox":(\d)')
    
    for url_categoria, categoria_nome in alvos_pichau.items():
        print(f"  -> Lendo categoria: '{categoria_nome}'...")
        
        pagina = 1
        max_paginas = 6
        
        while pagina <= max_paginas:
            url_paginada = f"{url_categoria}?page={pagina}"
            print(f"     Acessando página {pagina} (Nova Sessão)...")
            
            # 1. ABRIMOS O CHROME AQUI DENTRO (Nova Visita!)
            try:
                driver = webdriver.Chrome(options=chrome_options)
                driver.get(url_paginada)
                
                time.sleep(random.uniform(5.0, 7.0)) 
                
                html = driver.page_source
                dados = html.replace('\\"', '"')
                
                encontrados = list(_PRODUTO.finditer(dados))
                anuncios_processados = set()
                
                if not encontrados:
                    print(f"     -> Pombo detectado ou fim do catálogo na página {pagina}.")
                    driver.quit() # Fecha antes de quebrar
                    break 
                    
                produtos_nesta_pagina = 0
                for i, achado in enumerate(encontrados):
                    fim = (encontrados[i + 1].start() if i + 1 < len(encontrados) else achado.end() + 20000)
                    trecho = dados[achado.end():fim]
                    
                    avista = _AVISTA.search(trecho)
                    if avista is None:
                        continue 
                        
                    estoque = _ESTOQUE.search(trecho)
                    openbox = _OPENBOX.search(trecho)
                    
                    url_key = achado.group(1)
                    if url_key in anuncios_processados:
                        continue
                    anuncios_processados.add(url_key)
                    
                    disponivel = (estoque is None or estoque.group(1) == "IN_STOCK") and not (openbox and openbox.group(1) == "1")
                    
                    if disponivel:
                        ofertas_totais.append({
                            'id_produto_externo': url_key,
                            'nome_produto': _decodificar_texto(achado.group(2)),
                            'categoria_produto': categoria_nome,
                            'preco': float(avista.group(1)),
                            'nome_loja': 'Pichau',
                            'url_oferta': f"https://www.pichau.com.br/{url_key}",
                            'data_coleta': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        })
                        produtos_nesta_pagina += 1
                
                print(f"     -> {produtos_nesta_pagina} produtos extraídos.")
                
            except Exception as e:
                print(f"     -> Falha na página {pagina}: {e}")
            finally:
                # 2. DESTRUÍMOS O CHROME NO FINAL DA PÁGINA
                try:
                    driver.quit()
                except:
                    pass
            
            # Avança para a próxima página
            pagina += 1
            # Pausa extra entre sessões para o servidor da Pichau não estranhar
            time.sleep(random.uniform(2.0, 4.0))
            
    print(f"  -> Total de {len(ofertas_totais)} ofertas coletadas na Pichau.")
    return ofertas_totais


#def extrair_terabyte(alvos_terabyte):
    print("\n[Terabyte] Iniciando extração via Selenium + BeautifulSoup (Método Categoria)...")
    ofertas_totais = []
    
    chrome_options = Options()
    #chrome_options.add_argument('--headless')
    #chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--log-level=3')
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        
        for url_categoria, categoria_nome in alvos_terabyte.items():
            print(f"  -> Lendo categoria: '{categoria_nome}'...")
            driver.get(url_categoria)
            time.sleep(random.uniform(3.0, 5.0))
            
            # (Opcional) A Terabyte tem um botão "Ver Mais Produtos"

            sopa = BeautifulSoup(driver.page_source, "html.parser")
            
            cards = sopa.select("div.product-item__box")
            
            for card in cards:
                link = card.select_one("a.product-item__name")
                if link is None:
                    continue
                    
                titulo = link.get("title") or link.get_text(" ", strip=True)
                url_produto = link.get("href")
                
                id_externo = "ND"
                match_id = re.search(r'/produto/(\d+)/', url_produto)
                if match_id:
                    id_externo = match_id.group(1)
                
                esgotado = card.select_one(".tbt_esgotado") is not None
                if esgotado:
                    continue
                    
                preco_el = card.select_one(".product-item__new-price span")
                if preco_el:
                    texto_preco = preco_el.get_text()
                    preco_limpo = texto_preco.replace('R$', '').replace('.', '').replace(',', '.').strip()
                    try:
                        preco_float = float(preco_limpo)
                        
                        ofertas_totais.append({
                            'id_produto_externo': id_externo,
                            'nome_produto': titulo,
                            'categoria_produto': categoria_nome,
                            'preco': preco_float,
                            'nome_loja': 'Terabyte',
                            'url_oferta': url_produto,
                            'data_coleta': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        })
                    except ValueError:
                        continue
                        
    except Exception as e:
        print(f"  -> Falha crítica na Terabyte: {e}")
    finally:
        driver.quit()
        
    print(f"  -> {len(ofertas_totais)} ofertas coletadas na Terabyte.")
    return ofertas_totais


print("=== INICIANDO EXTRAÇÃO (KABUM + AMAZON) ===")

try:
    # Foco total na estabilidade: rodamos apenas as duas gigantes de maior confiabilidade
    resultados_kabum = extrair_kabum(categorias_alvo)
    resultados_amazon = extrair_amazon(categorias_alvo)
    
    # Junta tudo
    resultados_totais = resultados_kabum + resultados_amazon

    if not resultados_totais:
        raise ValueError("Extração retornou vazia.")
        
    # Salva o CSV
    df_ofertas = pd.DataFrame(resultados_totais)
    df_ofertas.to_csv(caminho_csv, index=False, sep=';', encoding='utf-8-sig')
    print(f"\n[SUCESSO] {len(df_ofertas)} ofertas coletadas e salvas com estabilidade total!")


except Exception as e:
    print(f"\n[FALHA NA EXTRAÇÃO REAL]: {e}")
    print("Acionando o plano de contingência (Mock Data) para não travar a IA...")
    
    dados_mock = {
        'id_produto_externo': ['1001', '1002', '1003'],
        'nome_produto': ['Placa de Vídeo RTX 4060', 'Processador AMD Ryzen 5', 'Placa Mãe B550M'],
        'categoria_produto': ['Hardware', 'Processadores', 'Placa-mãe'],
        'preco': [1850.00, 1100.00, 750.00],
        'nome_loja': ['KaBuM!', 'Amazon', 'KaBuM!'],
        'url_oferta': ['url_mock_1', 'url_mock_2', 'url_mock_3'],
        'data_coleta': [datetime.now().strftime('%Y-%m-%d %H:%M:%S')] * 3
    }
    df_mock = pd.DataFrame(dados_mock)
    df_mock.to_csv(caminho_csv, index=False, sep=';', encoding='utf-8-sig')
    print(f"Arquivo '{caminho_csv}' gerado via contingência com sucesso.")

if os.path.exists(caminho_csv):
    print("Confirmação final: O arquivo está no servidor e pronto para a Inteligência Artificial.")
else:
    print("Erro Crítico: O arquivo não foi gerado.")