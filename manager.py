import socket
import json
from datetime import datetime
import os
from elasticsearch import Elasticsearch

# Подключение к Elasticsearch
ELASTICSEARCH_HOST = "http://172.19.0.2:9200"

es = Elasticsearch(
    [ELASTICSEARCH_HOST],
    request_timeout=30,
    retry_on_timeout=True
)

# Проверка подключения
if not es.ping():
    print("Elasticsearch is not running or connection failed.")
    exit(1)
else:
    print("Connected to Elasticsearch successfully.")

INDEX_NAME = "computer_data"  # Имя индекса для хранения данных

# Функция для сохранения данных в файл
def save_data_to_file(data):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"data_{timestamp}.json"
    
    # Проверяем, существует ли уже файл с такими данными
    if os.path.exists(filename):
        print(f"File {filename} already exists. Skipping duplicate.")
        return
    
    # Сохраняем данные в файл
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)
    print(f"Data saved to {filename}")

# Функция для сохранения данных о компьютере в Elasticsearch
def save_computer_to_elasticsearch(computer_id, computer_data, timestamp):
    try:
        # Генерация уникального ID для документа
        doc_id = f"{timestamp}_{computer_id}"
        
        # Создание документа для Elasticsearch
        document = {
            "computer_id": computer_id,
            "timestamp": timestamp,
            "devices": computer_data
        }
        
        # Отправка данных в Elasticsearch
        response = es.index(index=INDEX_NAME, id=doc_id, document=document)
        print(f"Data saved to Elasticsearch. Response: {response}")
    except Exception as e:
        print(f"Error saving data to Elasticsearch: {e}")

# Основная функция менеджера
def main():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(("0.0.0.0", 5000))
    server_socket.listen(5)
    print("Manager is listening on port 5000...")

    while True:
        client_socket, addr = server_socket.accept()
        print(f"Connection from {addr}")
        
        try:
            # Чтение данных по частям
            data_chunks = []
            while True:
                chunk = client_socket.recv(4096).decode('utf-8')
                if not chunk:
                    break
                data_chunks.append(chunk)
            
            # Склеивание данных
            raw_data = ''.join(data_chunks)
            
            # Проверка, что данные не пустые
            if not raw_data.strip():
                print("Received empty data")
                continue
            
            # Разбор JSON
            try:
                parsed_data = json.loads(raw_data)
                print(f"Received data: {parsed_data}")  # Логируем полученные данные
                
                # Проверяем наличие временной метки
                timestamp = parsed_data.get('timestamp')
                if not timestamp:
                    print("Missing 'timestamp' in received data")
                    continue
                
                # Генерация уникального идентификатора компьютера
                computer_id = f"{addr[0]}"  # Используем IP-адрес клиента как идентификатор компьютера
                
                # Удаляем ключ "timestamp" из данных устройств
                devices_data = {key: value for key, value in parsed_data.items() if key != "timestamp"}
                
                # Сохранение данных о компьютере в Elasticsearch
                save_computer_to_elasticsearch(computer_id, devices_data, timestamp)
                
                # Сохранение данных в файл
                save_data_to_file(parsed_data)
            
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON: {e}")
                print(f"Raw data received: {raw_data[:100]}...")  # Вывод первых 100 символов для отладки
        
        except Exception as e:
            print(f"Error processing data: {e}")
        
        finally:
            client_socket.close()

if __name__ == "__main__":
    main()
