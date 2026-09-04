import requests
import os
import time
import sys
import signal

# Глобальный флаг для прерывания
interrupted = False


def signal_handler(sig, frame):
    global interrupted
    interrupted = True
    print("\n\n⏹️ Прерывание...")
    sys.exit(0)


def download_with_resume(url, local_filepath, max_retries=5):
    """Скачивает файл с докачкой и автоматическими переподключениями"""
    global interrupted

    retry_count = 0
    total_downloaded_overall = 0
    start_time = time.time()

    # Создаём папку, если её нет
    os.makedirs(os.path.dirname(os.path.abspath(local_filepath)), exist_ok=True)

    while retry_count < max_retries and not interrupted:
        try:
            # Проверяем, сколько байт уже скачано
            resume_byte = 0
            if os.path.exists(local_filepath):
                resume_byte = os.path.getsize(local_filepath)
                print(
                    f"\n📁 Найден частичный файл: {format_size(resume_byte)} уже скачано (попытка {retry_count + 1}/{max_retries})"
                )
            else:
                print(
                    f"\n📁 Создаём новый файл (попытка {retry_count + 1}/{max_retries})"
                )

            headers = {"Range": f"bytes={resume_byte}-"} if resume_byte > 0 else {}

            # Получаем общий размер файла
            total_size = None
            try:
                head_response = requests.head(url, timeout=10)
                if "content-length" in head_response.headers:
                    total_size = int(head_response.headers["content-length"])
                    print(f"📊 Общий размер: {format_size(total_size)}")
            except:
                pass

            # Загружаем с таймаутами
            downloaded = resume_byte
            last_progress = resume_byte
            last_progress_time = time.time()

            with requests.get(url, headers=headers, stream=True, timeout=(10, 30)) as r:
                r.raise_for_status()

                # Проверяем поддержку докачки
                mode = "ab" if resume_byte > 0 and r.status_code == 206 else "wb"
                if resume_byte > 0 and r.status_code != 206:
                    print("⚠️ Сервер НЕ поддерживает докачку! Начинаем с начала.")
                    mode = "wb"
                    downloaded = 0

                with open(local_filepath, mode) as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if interrupted:
                            print(f"\n💾 Прервано. Сохранено {format_size(downloaded)}")
                            return

                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            total_downloaded_overall += len(chunk)

                            # Обновляем прогресс
                            current_time = time.time()
                            if current_time - last_progress_time > 0.3:
                                if total_size:
                                    progress_bar(
                                        downloaded, total_size, start_time, retry_count
                                    )
                                else:
                                    print_progress_mb(downloaded, start_time)
                                last_progress_time = current_time

                            # Проверка "зависания"
                            if downloaded == last_progress:
                                if current_time - last_progress_time > 10:
                                    print(
                                        f"\n⚠️ Нет данных от сервера в течение 10 секунд! Переподключаемся..."
                                    )
                                    raise TimeoutError("Нет данных от сервера")
                            else:
                                last_progress = downloaded
                                last_progress_time = current_time

            # Если дошли сюда - загрузка завершена успешно
            print("\n\n✅ Загрузка завершена!")
            print(f"📁 Файл сохранён: {local_filepath}")
            print(f"📊 Итоговый размер: {format_size(downloaded)}")
            return True

        except (
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
            requests.exceptions.ChunkedEncodingError,
            TimeoutError,
        ) as e:
            retry_count += 1
            print(f"\n⚠️ Ошибка: {str(e)[:50]}")
            print(
                f"⏳ Переподключение через {retry_count * 2} секунд... (попытка {retry_count}/{max_retries})"
            )
            time.sleep(retry_count * 2)

        except KeyboardInterrupt:
            print("\n\n⏹️ Прервано пользователем")
            return False
        except Exception as e:
            print(f"\n❌ Неожиданная ошибка: {e}")
            retry_count += 1
            time.sleep(retry_count * 2)

    print(f"\n❌ Не удалось завершить загрузку после {max_retries} попыток")
    if os.path.exists(local_filepath):
        print(f"💾 Сохранено: {format_size(os.path.getsize(local_filepath))}")
    return False


def progress_bar(current, total, start_time, retry_count):
    """Рисует прогресс-бар"""
    percent = (current / total) * 100
    bar_length = 40
    filled_length = int(bar_length * current // total)
    bar = "█" * filled_length + "░" * (bar_length - filled_length)

    elapsed = time.time() - start_time
    if elapsed > 0:
        speed = current / elapsed
        speed_str = format_size(speed) + "/с"
    else:
        speed_str = "..."

    if speed > 0:
        remaining = (total - current) / speed
        time_str = format_time(remaining)
    else:
        time_str = "..."

    retry_info = f" [попытка {retry_count + 1}]" if retry_count > 0 else ""
    sys.stdout.write(
        f"\r📥 {percent:5.1f}% [{bar}] {format_size(current)}/{format_size(total)} | {speed_str} | ост. {time_str}{retry_info}"
    )
    sys.stdout.flush()


def print_progress_mb(current, start_time):
    """Простой вывод без процентов"""
    elapsed = time.time() - start_time
    if elapsed > 0:
        speed = current / elapsed
        speed_str = format_size(speed) + "/с"
    else:
        speed_str = "..."

    sys.stdout.write(f"\r📥 Скачано: {format_size(current)} | Скорость: {speed_str}")
    sys.stdout.flush()


def format_size(bytes):
    """Форматирует байты в читаемый вид"""
    if bytes == 0:
        return "0 Б"
    for unit in ["Б", "КБ", "МБ", "ГБ"]:
        if bytes < 1024.0:
            return f"{bytes:3.1f} {unit}"
        bytes /= 1024.0
    return f"{bytes:3.1f} ТБ"


def format_time(seconds):
    """Форматирует секунды"""
    if seconds < 60:
        return f"{seconds:.0f} сек"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes} мин {secs} сек"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours} ч {minutes} мин"


def get_save_path(url):
    """Запрашивает у пользователя путь для сохранения файла"""
    print("\n" + "=" * 60)
    print("📁 НАСТРОЙКА СОХРАНЕНИЯ")
    print("=" * 60)

    # Предлагаем имя файла из URL
    default_filename = url.split("/")[-1]
    if not default_filename or "." not in default_filename:
        default_filename = "downloaded_file"

    # Запрашиваем имя файла
    while True:
        filename = input(
            f"Введите имя файла (по умолчанию: {default_filename}): "
        ).strip()
        if not filename:
            filename = default_filename
            break

        # Проверяем, что имя не содержит опасных символов
        invalid_chars = '<>:"/\\|?*'
        if any(c in invalid_chars for c in filename):
            print('⚠️ Имя файла содержит недопустимые символы: < > : " / \\ | ? *')
            print("Пожалуйста, введите другое имя.")
        else:
            break

    # Запрашиваем папку для сохранения
    default_dir = os.path.join(os.path.expanduser("~"), "Downloads")
    print(f"\n📂 Папка для сохранения (по умолчанию: {default_dir})")

    while True:
        folder = input(
            "Введите путь к папке (или оставьте пустым для папки по умолчанию): "
        ).strip()
        if not folder:
            folder = default_dir
            break

        # Проверяем, существует ли папка
        if os.path.exists(folder):
            if os.path.isdir(folder):
                break
            else:
                print("⚠️ Указанный путь существует, но это не папка!")
        else:
            # Спрашиваем, создать ли папку
            create = (
                input(f"Папка '{folder}' не существует. Создать? (y/n): ")
                .strip()
                .lower()
            )
            if create in ["y", "yes", "да", "д"]:
                try:
                    os.makedirs(folder, exist_ok=True)
                    print(f"✅ Папка создана: {folder}")
                    break
                except Exception as e:
                    print(f"❌ Не удалось создать папку: {e}")
            else:
                print("Попробуйте указать другой путь.")

    # Формируем полный путь
    full_path = os.path.join(folder, filename)

    # Проверяем, не существует ли уже файл
    if os.path.exists(full_path):
        print(f"\n⚠️ Файл '{full_path}' уже существует.")
        choice = (
            input("Что делать? (o - перезаписать, r - переименовать, a - отмена): ")
            .strip()
            .lower()
        )

        if choice in ["o", "overwrite", "перезаписать"]:
            # Удаляем старый файл
            os.remove(full_path)
            print(f"🗑️ Старый файл удалён.")
        elif choice in ["r", "rename", "переименовать"]:
            # Добавляем номер к имени
            base, ext = os.path.splitext(filename)
            counter = 1
            while True:
                new_filename = f"{base}_{counter}{ext}"
                new_full_path = os.path.join(folder, new_filename)
                if not os.path.exists(new_full_path):
                    full_path = new_full_path
                    print(f"📝 Файл будет сохранён как: {new_filename}")
                    break
                counter += 1
        else:
            print("❌ Отмена.")
            sys.exit(0)

    return full_path


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)

    print("=" * 60)
    print("🚀 ЗАГРУЗЧИК С ДОКАЧКОЙ И АВТОПЕРЕПОДКЛЮЧЕНИЕМ")
    print("=" * 60)
    print("💡 Нажмите Ctrl+C для прерывания загрузки")
    print("🔄 Программа автоматически переподключится при обрыве связи")
    print("-" * 60)

    # Вводим URL
    file_url = input("\n🌐 Введите URL для скачивания: ").strip()
    if not file_url:
        file_url = "https://speed.hetzner.de/100MB.bin"
        print(f"Использую тестовый URL: {file_url}")

    # Получаем путь для сохранения
    save_path = get_save_path(file_url)

    print("\n" + "=" * 60)
    print("📥 НАЧАЛО ЗАГРУЗКИ")
    print("=" * 60)
    print(f"📁 Сохранение в: {save_path}")
    print("-" * 60)

    try:
        success = download_with_resume(file_url, save_path, max_retries=9999999999)
        if not success:
            print("\n⚠️ Загрузка не завершена. Попробуйте запустить программу снова.")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")

    input("\n\nНажмите Enter для выхода...")
