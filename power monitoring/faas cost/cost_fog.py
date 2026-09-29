import requests
import time
import os
import cv2
import json
import pickle
import base64
import csv

# --- Configurações ---
NEVOA_IP = "10.81.24.151"
OPENFAAS_URL = f"http://{NEVOA_IP}:31112/function/crowdcount-yolo"
START_URL = f"http://{NEVOA_IP}:6000/start"
STOP_URL = f"http://{NEVOA_IP}:6000/stop"

# Ajuste o caminho da imagem conforme necessário
IMG_PATH = "/home/rafael/Desktop/quarto_ano/TCC/Dataset/frames/seq_000001.jpg" 
ARQUIVO_SAIDA = "resultado_faas_sequencial.csv"

# Número de execuções
TOTAL_EXECUCOES = 7
WARMUP_COUNT = 2

# --- Funções Auxiliares ---
def serialize(imgpath):
    if not os.path.exists(imgpath):
        raise FileNotFoundError(f"Imagem não encontrada: {imgpath}")
    img = cv2.imread(imgpath)
    if img is None:
        raise ValueError("Falha ao ler a imagem com cv2.")
    imgdata = pickle.dumps(img)
    imserial = {'image_data': base64.b64encode(imgdata).decode('ascii')}
    return imserial

def construct_json(imserial):
    data = {'data': imserial}
    return json.dumps(data)

# A função parse_faces antiga foi removida pois agora lemos JSON direto

# --- Main ---
def run_sequential_test():
    # Cabeçalho do CSV
    cabecalho = [
        "iteracao", 
        "status", 
        "pessoas_detectadas", 
        "tempo_req_client_s", 
        "tempo_proc_server_s", # Agora virá do 'elapsed' da função FaaS
        "energia_mWh", 
        "potencia_media_W"
    ]
    
    # Cria arquivo novo (overwrite) e escreve o cabeçalho
    with open(ARQUIVO_SAIDA, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(cabecalho)

    print(f"Iniciando teste sequencial. {TOTAL_EXECUCOES} execuções (Ignorando as {WARMUP_COUNT} primeiras).")
    
    # Safety Stop inicial
    try:
        requests.post(STOP_URL, timeout=2)
    except:
        pass
    
    for i in range(TOTAL_EXECUCOES):
        print(f"\n--- Execução {i+1}/{TOTAL_EXECUCOES} ---")
        
        iteracao_id = i + 1
        is_warmup = i < WARMUP_COUNT
        
        try:
            # A. Serializa Imagem
            imserial = serialize(IMG_PATH)
            json_payload = construct_json(imserial)

            # B. Inicia Medição de Energia (app_medidor.py)
            resp_start = requests.post(START_URL)
            if resp_start.status_code != 200:
                print(f"[ERRO] Falha ao iniciar medição: {resp_start.text}")
                continue

            # C. Timer Cliente e Requisição FaaS
            t_start_client = time.monotonic()
            
            response_faas = requests.post(OPENFAAS_URL, data=json_payload)
            
            t_end_client = time.monotonic()
            
            # D. Para Medição de Energia
            resp_stop = requests.post(STOP_URL)
            
            # --- Processamento dos Dados ---
            
            # 1. Dados do Cliente (Latência total de rede + processamento)
            tempo_req_client = t_end_client - t_start_client
            
            # 2. Dados do Medidor de Energia
            measure_data = resp_stop.json().get("data", {})
            energia_mwh = measure_data.get("consumed_cpu_mWh", 0.0)
            avg_power = measure_data.get("avg_power_W", 0.0)
            
            # 3. Dados da Função FaaS (Correção solicitada)
            faces = 0
            tempo_proc_server = 0.0
            status = "error"

            if response_faas.status_code == 200:
                try:
                    # Parseia o JSON retornado pela função: {"person_count": X, "elapsed": Y}
                    faas_data = response_faas.json()
                    faces = faas_data.get("person_count", 0)
                    # Aqui pegamos o tempo exato de inferência relatado pelo Python dentro do container
                    tempo_proc_server = faas_data.get("elapsed", 0.0) 
                    status = "valid"
                except json.JSONDecodeError:
                    print(f"[ERRO] Resposta não é JSON válido: {response_faas.text}")
            else:
                print(f"[ERRO] FaaS retornou status {response_faas.status_code}")

            print(f"Status: {status} | Faces: {faces} | Energia: {energia_mwh:.4f} mWh | FaaS Elapsed: {tempo_proc_server:.4f}s")

            # E. Salva no CSV
            if not is_warmup:
                with open(ARQUIVO_SAIDA, 'a', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        iteracao_id,                 # int
                        status,                      # string
                        faces,                       # int
                        round(tempo_req_client, 4),  # float
                        round(tempo_proc_server, 4), # float (Agora vindo do FaaS)
                        round(energia_mwh, 6),       # float
                        round(avg_power, 4)          # float
                    ])
                print(f"-> Gravado no CSV.")
            else:
                print(f"-> Warmup (ignorado).")

            time.sleep(2)

        except Exception as e:
            print(f"[EXCEPTION] Erro na iteração {i}: {e}")
            try: requests.post(STOP_URL) 
            except: pass

if __name__ == "__main__":
    if not os.path.exists(IMG_PATH):
        print(f"AVISO: Imagem '{IMG_PATH}' não encontrada.")
        files = [f for f in os.listdir('.') if f.endswith('.jpg')]
        if files:
            IMG_PATH = files[0]
            print(f"Usando imagem encontrada: {IMG_PATH}")
        else:
            print("ERRO: Nenhuma imagem .jpg encontrada.")
            exit(1)
            
    run_sequential_test()