import os
import socket
import json
import subprocess
from datetime import datetime
import pyudev
import time

# Функция для сбора информации о USB-устройствах
def get_usb_info():
    usb_info = []
    try:
        output = subprocess.check_output(['lsusb']).decode('utf-8')
        for line in output.splitlines():
            parts = line.split()
            usb_info.append({
                "device_name": ' '.join(parts[6:]),
                "serial_number": None,  # Серийный номер может потребовать дополнительных действий
                "identifiers": ' '.join(parts[:6])
            })
    except Exception as e:
        print(f"Error collecting USB info: {e}")
    return usb_info

# Функция для сбора информации о PCI-устройствах
def get_pci_info():
    pci_info = []
    try:
        output = subprocess.check_output(['lspci', '-vmm']).decode('utf-8')
        devices = output.strip().split('\n\n')
        for device in devices:
            lines = device.splitlines()
            info = {}
            for line in lines:
                key, value = line.split(':', 1)
                info[key.strip()] = value.strip()
            pci_info.append({
                "device_name": info.get("Device", "Unknown"),
                "bus_number": info.get("Slot", "Unknown"),
                "device_id": info.get("Vendor", "Unknown"),
                "subsystem_id": info.get("Subsys", "Unknown")
            })
    except Exception as e:
        print(f"Error collecting PCI info: {e}")
    return pci_info

# Функция для сбора информации о SCSI-устройствах
def get_scsi_info():
    scsi_info = []
    try:
        output = subprocess.check_output(['lsscsi', '-l']).decode('utf-8')
        for line in output.splitlines():
            parts = line.split()
            scsi_info.append({
                "device_name": ' '.join(parts[3:]),
                "serial_number": parts[-1] if len(parts) > 1 else "Unknown",
                "size": parts[-2] if len(parts) > 2 else "Unknown"
            })
    except Exception as e:
        print(f"Error collecting SCSI info: {e}")
    return scsi_info

# Функция для сбора информации о CPU
def get_cpu_info():
    cpu_info = []
    try:
        with open('/proc/cpuinfo') as f:
            data = f.read()
            for processor in data.split('\n\n'):
                info = {}
                for line in processor.splitlines():
                    if ':' in line:
                        key, value = line.split(':', 1)
                        info[key.strip()] = value.strip()
                cpu_info.append({
                    "device_name": info.get("model name", "Unknown"),
                    "serial_number": info.get("serial", "Unknown"),
                    "batch_number": info.get("stepping", "Unknown")
                })
    except Exception as e:
        print(f"Error collecting CPU info: {e}")
    return cpu_info

# Функция для сбора информации о RAM
def get_memory_info():
    memory_info = []
    try:
        output = subprocess.check_output(['dmidecode', '-t', 'memory']).decode('utf-8')
        for block in output.split("\n\n"):
            if "Memory Device" in block:
                info = {}
                for line in block.splitlines():
                    if ":" in line:
                        key, value = line.split(":", 1)
                        info[key.strip()] = value.strip()
                memory_info.append({
                    "device_name": info.get("Type", "Unknown"),
                    "serial_number": info.get("Serial Number", "Unknown"),
                    "batch_number": info.get("Part Number", "Unknown"),
                    "size": info.get("Size", "Unknown")
                })
    except Exception as e:
        print(f"Error collecting memory info: {e}")
    return memory_info

# Функция для отправки данных менеджеру
def send_data_to_manager(data, manager_ip="127.0.0.1", manager_port=5000):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((manager_ip, manager_port))
            s.sendall(json.dumps(data).encode('utf-8'))
        print("Data sent to manager successfully.")
    except Exception as e:
        print(f"Error sending data to manager: {e}")

# Функция для мониторинга событий udev
def monitor_udev_events():
    context = pyudev.Context()
    monitor = pyudev.Monitor.from_netlink(context)

    # Добавляем фильтры для всех нужных подсистем
    monitor.filter_by(subsystem='usb')  # Мониторим USB
    monitor.filter_by(subsystem='pci')  # Мониторим PCI
    monitor.filter_by(subsystem='scsi')  # Мониторим SCSI
    monitor.filter_by(subsystem='cpu')  # Мониторим CPU
    monitor.filter_by(subsystem='memory')  # Мониторим RAM

    monitor.start()

    # Словарь для отслеживания отправленных устройств
    sent_devices = set()

    for device in iter(monitor.poll, None):
        event = device.action  # 'add' или 'remove'
        subsystem = device.subsystem  # 'usb', 'pci', 'scsi', 'cpu', 'memory'

        # Проверяем, является ли устройство основным (не интерфейсом или драйвером)
        if subsystem == "usb":
            devtype = device.get("DEVTYPE", None)
            if devtype and devtype != "usb_device":  # Игнорируем интерфейсы и другие подкомпоненты
                continue

        # Уникальный идентификатор устройства
        device_id = f"{subsystem}:{device.device_path}"

        # Проверяем, было ли устройство уже отправлено
        if device_id in sent_devices and event != 'remove':
            print(f"Device {device_id} already sent. Skipping duplicate.")
            continue

        # Собираем информацию об устройстве
        device_info = {
            "device_name": device.get("ID_MODEL", "Unknown"),
            "serial_number": device.get("ID_SERIAL_SHORT", "Unknown"),
            "identifiers": f"{device.get('ID_VENDOR_ID', 'Unknown')}:{device.get('ID_MODEL_ID', 'Unknown')}"
        }

        # Формируем данные для отправки
        data = {
            "event": event,
            "device_type": subsystem,
            "device_info": device_info,
            "timestamp": datetime.now().isoformat()
        }

        # Отправляем данные менеджеру
        send_data_to_manager(data)

        # Добавляем устройство в список отправленных
        if event == 'add':
            sent_devices.add(device_id)
        elif event == 'remove':
            sent_devices.discard(device_id)

# Основная функция агента
def main():
    # Сбор информации при старте системы
    initial_data = {
        "usb": get_usb_info(),
        "pci": get_pci_info(),
        "scsi": get_scsi_info(),
        "cpu": get_cpu_info(),
        "memory": get_memory_info(),
        "timestamp": datetime.now().isoformat()
    }
    send_data_to_manager(initial_data)

    # Мониторинг изменений в составе оборудования
    monitor_udev_events()

if __name__ == "__main__":
    main()
