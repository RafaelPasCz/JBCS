# Certifique-se de que o arquivo adapt_exec_client.py está na pasta Adaptive_execution
import adapt_exec_client as adapt_faas
import sys
import time
import os
import cv2
import json
import pickle
import base64
import threading
from datetime import datetime

# --- Configurações ---

# Leitura segura do argumento de tempo
TEMPO_ESPERA = float(sys.argv[1])
print(f"Tempo de espera: {TEMPO_ESPERA}")

ARQUIVO_SAIDA = f"resultados_adaptativo_{TEMPO_ESPERA}.csv"
DATASET_PATH = "/home/rafael/Desktop/quarto_ano/TCC/Dataset/frames/"
ARQUIVO_CONFIG = "./config.yml"

# URLs para comparação
URL_BORDA = "http://10.81.24.51:8080/function/crowdcount-yolo"
URL_NEVOA = "http://10.81.24.151:31112/function/crowdcount-yolo"
URL_NUVEM = "http://35.247.206.133:30080/function/crowdcount-yolo"

ADAPT_SERVER_URL = "http://10.81.24.139:5000"

# Inicializa o cliente Adaptativo
# Nota: O cliente deve estar configurado para lidar com sessões internamente ou criar novas
adapt_client = adapt_faas.Adaptive_FaaS(ADAPT_SERVER_URL, ARQUIVO_CONFIG)

try:
    response = adapt_client.send_config()
    print(f"Configuração enviada: {response}")
    time.sleep(11) # Tempo para propagação da config
except Exception as e:
    print(f"Aviso ao enviar config: {e}")

# Listagem de fotos
try:
    fotos = sorted(os.listdir(DATASET_PATH))
except FileNotFoundError:
    print(f"Diretório {DATASET_PATH} não encontrado. Usando lista vazia.")
    fotos = []

# --- Variáveis Globais e Locks ---
csv_lock = threading.Lock()

# --- Preparação do CSV ---
if not os.path.exists(ARQUIVO_SAIDA):
    with open(ARQUIVO_SAIDA, 'w') as f:
        # Cabeçalho atualizado
        f.write("imagem,iteracao,duracao_req,tempo_execução,total_faces_detectadas,borda_true,nevoa_true,nuvem_true\n")

# --- Funções Auxiliares ---
def serialize(imgpath):
    img = cv2.imread(imgpath)
    imgdata = pickle.dumps(img)
    imserial = {'image_data' : base64.b64encode(imgdata).decode('ascii')}
    return imserial

def construct_json(imserial):
    data = {'data' : imserial}
    json_data = json.dumps(data)
    return json_data

# --- Função da Thread de Processamento ---
def processar_foto_em_thread(foto_nome, foto_path, iteracao_atual):
    try:
        imserial = serialize(foto_path)
        img_json = construct_json(imserial)

        # Marca inicio da requisição (Client Side)
        start_req = time.time()

        # Envia requisição via cliente adaptativo
        # response: objeto de resposta, best_faas: url escolhida
        response, best_faas = adapt_client.request("crowdcount-yolo", img_json, json=True, timeout=100)
        if '\n' in response.text.strip():
        # print('entrou')
            response = response.text.strip().split('\n')[-1]
        else:
        #print('nao entrou')
            response = response.text.strip()
        
        # Marca fim da requisição
        end_req = time.time()
        duracao_req = end_req - start_req

        # Identifica onde foi processado (0 ou 1)
        # Remove barras finais ou espaços para garantir a comparação correta, se necessário
        url_utilizada = best_faas.strip()
        
        borda_true = 1 if url_utilizada == URL_BORDA else 0
        nevoa_true = 1 if url_utilizada == URL_NEVOA else 0
        nuvem_true = 1 if url_utilizada == URL_NUVEM else 0

        # Processa o JSON de resposta (vinda do faas.py)
        # Esperado: {"person_count": int, "elapsed": float}
        try:
            # Tenta decodificar o JSON. O adapt_client retorna requests.Response
            if hasattr(response, 'json'):
                resp_data = response.json()
            else:
                resp_data = json.loads(response)
            
            # Caso o retorno seja uma string contendo json (double encoded)
            if isinstance(resp_data, str):
                resp_data = json.loads(resp_data)

            faces = resp_data.get('person_count', 0)
            tempo_execucao_server = resp_data.get('elapsed', 0.0)

            # Escrita no CSV segura
            with csv_lock:
                with open(ARQUIVO_SAIDA, 'a') as f:
                    f.write(f"{foto_nome},{iteracao_atual},{duracao_req:.4f},{tempo_execucao_server:.4f},{faces},{borda_true},{nevoa_true},{nuvem_true}\n")
            
            # Log simples no console para acompanhamento
            local_str = "BORDA" if borda_true else ("NEVOA" if nevoa_true else "NUVEM")
            print(f"[{iteracao_atual}] {foto_nome} -> {local_str} | Faces: {faces} | Req: {duracao_req:.2f}s")

        except json.JSONDecodeError:
            print(f"Erro ao decodificar JSON de {foto_nome}. Resposta crua: {response.text}")
            
    except Exception as e:
        print(f"Erro processando {foto_nome}: {e}")

# --- Loop Principal ---
print(f"Iniciando processamento adaptativo (Imagem por imagem). Saída: {ARQUIVO_SAIDA}")

for i in range(7):
    print(f"--- Iniciando Iteração {i} ---")
    
    threads = []
    time.sleep(60)
    # Dispara Threads
    for foto in fotos:
        foto_completa = os.path.join(DATASET_PATH, foto)
        
        t = threading.Thread(target=processar_foto_em_thread, args=(foto, foto_completa, i))
        threads.append(t)
        t.start()
        
        time.sleep(TEMPO_ESPERA)

    # Aguarda todas as threads da iteração terminarem
    for t in threads:
        t.join()

    print(f"Iteração {i} concluída.")

print("Processo finalizado.")
