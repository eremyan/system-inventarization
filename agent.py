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
            bus_id = parts[1]  # Bus ID (например, 002)
            device_id = parts[3].rstrip(':')  # Device ID (например, 003)

            # Получаем серийный номер через udevadm
            serial_number = None
            if "Linux Foundation" not in line:  # Игнорируем "root hub"
                try:
                    udev_output = subprocess.check_output(
                        ['udevadm', 'info', '--query=all', '--name=/dev/bus/usb/' + bus_id + '/' + device_id]
                    ).decode('utf-8')
                    for udev_line in udev_output.splitlines():
                        if 'ID_SERIAL_SHORT' in udev_line:
                            serial_number = udev_line.split('=')[1]
                            break
                except Exception:
                    serial_number = None  # Если серийный номер недоступен

            # Формируем информацию об устройстве
            vendor_id = parts[5].split(':')[0]  # Vendor ID
            product_id = parts[5].split(':')[1]  # Product ID
            usb_info.append({
                "device_name": ' '.join(parts[6:]),
                "serial_number": serial_number,
                "identifiers": f"{vendor_id}:{product_id}"
            })
    except Exception as e:
        print(f"Error collecting USB info: {e}")
    return usb_info

# Функция для сбора информации о PCI-устройствах
def get_pci_info():
    pci_info = []
    try:
        # Получаем список PCI-устройств через lspci
        output = subprocess.check_output(['lspci', '-vmm']).decode('utf-8')
        devices = output.strip().split('\n\n')

        for device in devices:
            lines = device.splitlines()
            info = {}
            for line in lines:
                if ':' in line:
                    key, value = line.split(':', 1)
                    info[key.strip()] = value.strip()

            # Извлекаем Slot (шина:устройство:функция)
            slot = info.get("Slot", "Unknown")
            if slot == "Unknown":
                continue

            # Читаем device_id и subsystem_id из файлов в /sys
            try:
                with open(f"/sys/bus/pci/devices/0000:{slot}/device", "r") as f:
                    device_id = f"0x{f.read().strip()}"
                with open(f"/sys/bus/pci/devices/0000:{slot}/subsystem_device", "r") as f:
                    subsystem_id = f"0x{f.read().strip()}"
            except Exception:
                device_id = "Unknown"
                subsystem_id = "Unknown"

            pci_info.append({
                "device_name": info.get("Device", "Unknown"),
                "bus_number": slot,
                "device_id": device_id,
                "subsystem_id": subsystem_id
            })
    except Exception as e:
        print(f"Error collecting PCI info: {e}")
    return pci_info

# Функция для сбора информации о SCSI-устройствах
def get_scsi_info():
    scsi_info = []
    try:
        # Используем lsblk для получения данных о SCSI-устройствах
        output = subprocess.check_output(['lsblk', '-o', 'TYPE,SIZE,SERIAL,MODEL', '--json']).decode('utf-8')
        data = json.loads(output)

        for device in data.get("blockdevices", []):
            # Игнорируем разделы (только физические устройства)
            if device.get("type") != "disk":
                continue

            scsi_info.append({
                "device_name": device.get("model", "Unknown"),
                "serial_number": device.get("serial", "Unknown"),
                "size": device.get("size", "Unknown")
            })
    except Exception as e:
        print(f"Error collecting SCSI info: {e}")
    return scsi_info

# Функция для сбора информации о CPU
def get_cpu_info():
    cpu_info = []
    try:
        # Используем dmidecode для сбора информации о CPU
        output = subprocess.check_output(['dmidecode', '-t', 'processor']).decode('utf-8')
        blocks = output.strip().split('\n\n')

        for block in blocks:
            info = {}
            for line in block.splitlines():
                if ":" in line:
                    key, value = line.split(":", 1)
                    info[key.strip()] = value.strip()

            # Проверяем, есть ли значимая информация в блоке
            if not any(info.get(field) and info[field] != "Unknown" for field in ["Version", "Serial Number", "Part Number"]):
                continue

            # Формируем информацию о CPU
            cpu_info.append({
                "device_name": info.get("Version", "Unknown"),
                "serial_number": info.get("Serial Number", "Unknown"),
                "batch_number": info.get("Part Number", "Unknown")
            })
    except Exception as e:
        print(f"Error collecting CPU info: {e}")
    return cpu_info

# Функция для сбора информации о RAM
def get_memory_info():
    memory_info = []
    try:
        # Используем dmidecode для сбора информации о RAM
        output = subprocess.check_output(['dmidecode', '-t', 'memory']).decode('utf-8')
        blocks = output.strip().split('\n\n')

        for block in blocks:
            if "Memory Device" in block:
                info = {}
                for line in block.splitlines():
                    if ":" in line:
                        key, value = line.split(":", 1)
                        info[key.strip()] = value.strip()

                # Если серийный номер равен "0x00000000", заменяем его на "Unknown"
                serial_number = info.get("Serial Number", "Unknown")
                if serial_number == "0x00000000":
                    serial_number = "Unknown"

                # Формируем название устройства
                device_name = f"{info.get('Manufacturer', 'Unknown')} " \
                              f"{info.get('Form Factor', 'Unknown')} " \
                              f"{info.get('Type', 'Unknown')}"

                memory_info.append({
                    "device_name": device_name,
                    "serial_number": serial_number,
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
