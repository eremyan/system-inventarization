import socket
import json
from datetime import datetime
import os

# Функция для сохранения данных в файл
def save_data(data):
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
                save_data(parsed_data)
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON: {e}")
                print(f"Raw data received: {raw_data[:100]}...")  # Вывод первых 100 символов для отладки
        
        except Exception as e:
            print(f"Error processing data: {e}")
        
        finally:
            client_socket.close()

if __name__ == "__main__":
    main()
