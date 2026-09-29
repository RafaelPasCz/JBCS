import serial
import time
import sys
import os
from datetime import datetime

# --- Configurações ---
SERIAL_PORT = '/dev/ttyUSB0'  # Ajuste conforme sua porta
BAUDRATE = 115200
ARQUIVO_SAIDA = "consumo_por_minuto_tvbox.csv"
DURACAO_MINUTO = 60  # Segundos por ciclo
TOTAL_CICLOS = 5     # Quantas vezes vai repetir (5 minutos)

def monitorar_energia():
    print(f"--- Iniciando Monitor de Energia ---")
    print(f"Porta: {SERIAL_PORT} | Ciclos: {TOTAL_CICLOS} de {DURACAO_MINUTO}s")
    
    # Prepara o CSV
    if not os.path.exists(ARQUIVO_SAIDA):
        with open(ARQUIVO_SAIDA, 'w') as f:
            f.write("timestamp_registro,ciclo,energia_mWh,potencia_media_mW\n")

    try:
        with serial.Serial(SERIAL_PORT, BAUDRATE, timeout=1) as ser:
            # Limpa o buffer inicial para evitar leitura de dados "velhos"
            ser.reset_input_buffer()
            
            for ciclo in range(1, TOTAL_CICLOS + 1):
                print(f"\nIniciando Ciclo {ciclo}/{TOTAL_CICLOS}...")
                
                start_time_sys = time.time()
                mWh_acumulado_ciclo = 0.0
                prev_device_timestamp = None
                amostras_validas = 0
                
                # Loop de 1 minuto (ou tempo configurado)
                while (time.time() - start_time_sys) < DURACAO_MINUTO:
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                    
                    if line:
                        try:
                            # Formato esperado: timestamp;corrente;tensao
                            parts = line.split(";")
                            if len(parts) >= 3:
                                dev_timestamp = int(parts[0]) # Timestamp do Arduino/ESP (ms)
                                current = float(parts[1])     # Amperes ou mA (dependendo do seu firmware, assumindo a lógica anterior)
                                voltage = float(parts[2])     # Volts
                                
                                # Cálculo de Potência Instantânea (mW)
                                power_mW = current * voltage 
                                
                                # Cálculo de Energia (Integração no tempo)
                                if prev_device_timestamp is not None:
                                    delta_ms = dev_timestamp - prev_device_timestamp
                                    
                                    # Filtro para evitar deltas negativos (reinício do microcontrolador) ou gigantes
                                    if 0 < delta_ms < 2000: 
                                        # Energia (mWh) = Potência (mW) * tempo (h)
                                        # tempo (h) = delta_ms / 3600000
                                        energy_increment = (power_mW * delta_ms) / 3600000.0
                                        mWh_acumulado_ciclo += energy_increment
                                        amostras_validas += 1

                                prev_device_timestamp = dev_timestamp

                        except ValueError:
                            # Ignora linhas corrompidas na serial
                            continue
                
                # Fim do minuto: Salvar dados
                timestamp_agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Cálculo da potência média no minuto (apenas informativo)
                # Potência Média (mW) = Energia Total (mWh) / Tempo (h)
                # 1 minuto = 1/60 horas
                potencia_media = mWh_acumulado_ciclo / (DURACAO_MINUTO / 3600.0)

                output_line = f"{timestamp_agora},{ciclo},{mWh_acumulado_ciclo:.6f},{potencia_media:.2f}\n"
                
                with open(ARQUIVO_SAIDA, 'a') as f:
                    f.write(output_line)
                
                print(f"Ciclo {ciclo} finalizado.")
                print(f"  > Energia Consumida: {mWh_acumulado_ciclo:.4f} mWh")
                print(f"  > Potência Média Aprox: {potencia_media:.2f} mW")

    except serial.SerialException as e:
        print(f"ERRO CRÍTICO NA SERIAL: {e}")
        print("Verifique se o dispositivo está conectado e se a porta está correta.") #

    print("\nMonitoramento finalizado com sucesso.")

if __name__ == "__main__":
    monitorar_energia()
