#!/usr/bin/env python3
"""
Скрипт для запуска приложения НейроКонсультант по ВНД
"""
import uvicorn
import os
import sys
import traceback

def kill_process_on_port(port):
    """Остановить процесс, занимающий указанный порт (Windows)"""
    import subprocess
    import time
    try:
        # Находим PID процесса на порту
        result = subprocess.run(
            ['netstat', '-ano'],
            capture_output=True,
            text=True,
            shell=True
        )
        
        processes_killed = []
        for line in result.stdout.split('\n'):
            if f':{port}' in line and 'LISTENING' in line:
                parts = line.split()
                if len(parts) >= 5:
                    pid = parts[-1]
                    try:
                        # Останавливаем процесс
                        subprocess.run(['taskkill', '/F', '/PID', pid], 
                                     capture_output=True, shell=True)
                        processes_killed.append(pid)
                        print(f"✓ Остановлен процесс {pid}, занимавший порт {port}")
                    except:
                        pass
        
        # Если были остановлены процессы, ждем освобождения порта
        if processes_killed:
            print(f"Ожидание освобождения порта {port}...")
            for i in range(5):  # Проверяем до 5 раз
                time.sleep(1)
                result = subprocess.run(
                    ['netstat', '-ano'],
                    capture_output=True,
                    text=True,
                    shell=True
                )
                port_in_use = False
                for line in result.stdout.split('\n'):
                    if f':{port}' in line and 'LISTENING' in line:
                        port_in_use = True
                        break
                if not port_in_use:
                    print(f"✓ Порт {port} свободен")
                    return True
            print(f"⚠️  Порт {port} все еще может быть занят")
        
        return len(processes_killed) > 0
    except Exception as e:
        print(f"⚠️  Не удалось проверить порт {port}: {e}")
        return False

def check_port_free(port):
    """Проверить, свободен ли порт"""
    import subprocess
    try:
        result = subprocess.run(
            ['netstat', '-ano'],
            capture_output=True,
            text=True,
            shell=True
        )
        for line in result.stdout.split('\n'):
            if f':{port}' in line and 'LISTENING' in line:
                return False
        return True
    except:
        return True  # В случае ошибки считаем порт свободным

if __name__ == "__main__":
    try:
        # Проверяем наличие .env файла
        env_path = os.path.join(os.path.dirname(__file__), '.env')
        if not os.path.exists(env_path):
            print("⚠️  Внимание: файл .env не найден!")
            print("Создайте файл .env на основе env_template.txt")
            print("Минимально необходимые переменные:")
            print("  - DATABASE_URL (можно использовать sqlite:///./wnd.db для тестирования)")
            print("  - OPENAI_API_KEY")
            print("  - SECRET_KEY")
            print("\nПродолжаем запуск...")
        
        # Проверяем и освобождаем порт 8011
        print("Проверка порта 8011...")
        kill_process_on_port(8011)
        
        # Финальная проверка, что порт свободен
        import time
        time.sleep(2)  # Даем время порту освободиться
        
        if not check_port_free(8011):
            print("❌ ОШИБКА: Порт 8011 все еще занят!")
            print("Попробуйте:")
            print("  1. Запустите kill_port_8011.bat от имени администратора")
            print("  2. Проверьте диспетчер задач на наличие процессов python.exe")
            print("  3. Перезагрузите компьютер, если проблема сохраняется")
            sys.exit(1)
        
        print("✓ Порт 8011 свободен, продолжаем запуск...")
        
        # Меняем рабочую директорию на backend
        backend_dir = os.path.join(os.path.dirname(__file__), 'backend')
        if not os.path.exists(backend_dir):
            print(f"❌ Ошибка: папка backend не найдена: {backend_dir}")
            sys.exit(1)
        
        os.chdir(backend_dir)
        sys.path.insert(0, backend_dir)
        
        print("=" * 60)
        print("Запуск сервера НейроКонсультант по ВНД")
        print("=" * 60)
        print(f"Рабочая директория: {os.getcwd()}")
        print(f"Порт: 8011")
        print(f"URL: http://localhost:8011")
        print("=" * 60)
        print()
        
        # Запускаем сервер
        # Отключаем reload для избежания проблем с портом
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8011,
            reload=False,  # Отключаем reload для стабильности
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n\nОстановка сервера...")
    except Exception as e:
        print(f"\n❌ Ошибка при запуске сервера: {e}")
        print("\nДетали ошибки:")
        traceback.print_exc()
        sys.exit(1)

