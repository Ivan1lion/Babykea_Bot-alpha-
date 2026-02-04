import os
import chromadb
from pathlib import Path

# === НАСТРОЙКИ ПУТЕЙ ===
# 1. resolve() -> полный путь к файлу manage_chroma.py
# 2. .parent   -> папка app
# 3. .parent   -> папка Babykea_Bot(alpha) (КОРЕНЬ, где лежит chromadb_storage)
BASE_DIR = Path(__file__).resolve().parent.parent

CHROMA_DB_PATH = os.path.join(BASE_DIR, "chromadb_storage")

# Проверка (чтобы ты видел в консоли, куда он смотрит)
print(f"📁 Ищу базу по пути: {CHROMA_DB_PATH}")

# Инициализация клиента
chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
collection = chroma_client.get_or_create_collection(name="strollers")


def show_stats():
    """Показывает сколько всего товаров в базе"""
    count = collection.count()
    print(f"\n📊 Всего товаров в векторной базе: {count}")
    if count > 0:
        # Показываем пример метаданных первого товара, чтобы убедиться, что source_url пишется
        peek = collection.peek(limit=1)
        print(f"👀 Пример данных (проверка полей): {peek['metadatas'][0].keys()}")


def delete_by_feed_url():
    """
    Удаляет ВСЕ товары, которые пришли из конкретного YML файла.
    Используется, когда магазин с уникальным фидом уходит.
    """
    url = input("\n🔗 Введите URL фида (YML), который нужно удалить: ").strip()

    if not url:
        print("❌ URL не может быть пустым.")
        return

    print(f"⏳ Ищу товары из источника: {url}...")

    # Проверяем, есть ли такие товары (используем фильтр по метаданным)
    existing = collection.get(where={"source_url": url})
    count = len(existing['ids'])

    if count == 0:
        print(f"⚠️ Товаров по этой ссылке не найдено.")
        print("Возможные причины:")
        print("1. Вы еще не запускали update_vectors.py с новым кодом (нет поля source_url).")
        print("2. Ссылка отличается от той, что в базе.")
        return

    print(f"🔥 Найдено {count} товаров.")
    confirm = input(f"Вы уверены, что хотите УДАЛИТЬ их навсегда? (yes/no): ").lower()

    if confirm == "yes":
        collection.delete(where={"source_url": url})
        print(f"✅ Успешно удалено {count} записей.")
    else:
        print("🚫 Операция отменена.")


def menu():
    while True:
        print("\n=== 🦖 CHROMA DB ADMIN ===")
        print("1. 📊 Статистика базы")
        print("2. 🗑 Удалить YML файл (Уход уникального магазина)")
        print("0. Выход")

        choice = input("Ваш выбор: ")

        if choice == "1":
            show_stats()
        elif choice == "2":
            delete_by_feed_url()
        elif choice == "0":
            break
        else:
            print("Неверный ввод")


if __name__ == "__main__":
    menu()