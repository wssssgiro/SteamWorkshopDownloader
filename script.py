import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path
import aiohttp
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename="workshop_downloader.log",
    filemode="w",
    encoding="utf-8",
)

STEAMCMD_URL = "https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip"
STEAM_API_DETAILS_URL = "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
STEAM_API_COLLECTION_URL = "https://api.steampowered.com/ISteamRemoteStorage/GetCollectionDetails/v1/"
MAX_RETRIES = 3

TEXTS = {
    "ru": {
        "title": "=== Установщик модов Steam Workshop ===",
        "current_game": "Текущая игра: {name} [ID: {id}]",
        "no_game": "Игра ещё не выбрана!",
        "menu_game": [
            "1. Скачать моды по ссылкам",
            "2. Скачать всю коллекцию",
            "3. Сменить игру",
            "4. Сменить язык (RU/EN)",
            "5. Выход",
        ],
        "menu_no_game": [
            "1. Выбрать игру",
            "2. Сменить язык (RU/EN)",
            "3. Выход",
        ],
        "prompt": "Выберите действие: ",
        "setup_title": "=== Настройка игры ===",
        "setup_hint": "Вставьте ссылку на игру в магазине Steam\nПример: https://store.steampowered.com/app/108600/Project_Zomboid/",
        "invalid_link": "Неверная ссылка! Попробуйте ещё раз.",
        "urls_title": "=== Загрузка модов по ссылкам ===",
        "urls_hint": "Вставляйте ссылки на моды (можно несколько через пробел).\nДля старта нажмите Enter на пустой строке (или 'x' для отмены):",
        "col_title": "=== Загрузка коллекции ===",
        "col_hint": "Вставьте ссылку на коллекцию Steam Workshop (или 'x' для отмены):",
        "col_empty": "В этой коллекции не найдено модов (или она скрыта).",
        "col_found": "Найдено модов в коллекции: {count}",
        "confirm": "Начать скачивание? (y/n): ",
        "steamcmd_dl": "Скачиваю архив SteamCMD...",
        "steamcmd_init": "Первичная инициализация SteamCMD (подождите минутку)...",
        "fetching_info": "Получаю названия модов через Steam API...",
        "progress_desc": "Загрузка модов",
        "already_installed": "⏭️ [Пропуск] Мод [{title}] уже установлен.",
        "downloading": "⏳ Качаю: [{title}] (ID: {id})...",
        "retrying": "🔄 Ошибка [{title}]. Попытка {attempt}/{max}...",
        "failed": "❌ [Ошибка] Не удалось скачать [{title}] (ID: {id}).",
        "installed": "✅ [Готово] Мод [{title}] установлен в {path}!",
        "done_prompt": "\n✨ Все задачи завершены! Нажмите Enter для возврата в меню...",
        "sep": "─" * 52,
    },
    "en": {
        "title": "=== Steam Workshop Mod Downloader ===",
        "current_game": "Current game: {name} [ID: {id}]",
        "no_game": "No game selected!",
        "menu_game": [
            "1. Download mods by URLs",
            "2. Download from collection",
            "3. Change game",
            "4. Switch language (RU/EN)",
            "5. Exit",
        ],
        "menu_no_game": [
            "1. Select game",
            "2. Switch language (RU/EN)",
            "3. Exit",
        ],
        "prompt": "Choose an option: ",
        "setup_title": "=== Game Setup ===",
        "setup_hint": "Paste the Steam Store game link\nExample: https://store.steampowered.com/app/108600/Project_Zomboid/",
        "invalid_link": "Invalid link! Please try again.",
        "urls_title": "=== Download Mods by URLs ===",
        "urls_hint": "Paste Workshop mod links.\nPress Enter on an empty line to start (or 'x' to cancel):",
        "col_title": "=== Download Collection ===",
        "col_hint": "Paste the Steam Workshop Collection link (or 'x' to cancel):",
        "col_empty": "No mods found in this collection (or it is private).",
        "col_found": "Mods found in collection: {count}",
        "confirm": "Start downloading? (y/n): ",
        "steamcmd_dl": "Downloading SteamCMD archive...",
        "steamcmd_init": "Initializing SteamCMD for the first time...",
        "fetching_info": "Fetching mod titles via Steam API...",
        "progress_desc": "Downloading mods",
        "already_installed": "⏭️ [Skip] Mod [{title}] is already installed.",
        "downloading": "⏳ Downloading: [{title}] (ID: {id})...",
        "retrying": "🔄 Failed [{title}]. Retry {attempt}/{max}...",
        "failed": "❌ [Error] Could not download [{title}] (ID: {id}).",
        "installed": "✅ [Done] Mod [{title}] installed to {path}!",
        "done_prompt": "\n✨ All tasks finished! Press Enter to return to menu...",
        "sep": "─" * 52,
    },
}


class WorkshopDownloader:
    def __init__(self):
        self.base_dir = (
            Path(sys.executable).parent
            if getattr(sys, "frozen", False)
            else Path(__file__).parent.resolve()
        )
        self.main_dir = self.base_dir / "main"
        self.steamcmd_dir = self.main_dir / "SteamCMD"
        self.steamcmd_exe = self.steamcmd_dir / (
            "steamcmd.exe" if os.name == "nt" else "steamcmd.sh"
        )
        self.config_path = self.main_dir / "config.json"
        self.games_dir = self.base_dir / "games"
        self.temp_dir = self.base_dir / "temp"

        self.lang = "ru"
        self.game_id = None
        self.game_name = None
        self.game_folder = None
        self.max_concurrent = 2

        self.load_config()
        self.ensure_steamcmd()

    @property
    def t(self):
        return TEXTS[self.lang]

    def clear_screen(self):
        os.system("cls" if os.name == "nt" else "clear")

    def clean_folder_name(self, name: str) -> str:
        cleaned = re.sub(r'[\\/:*?"<>|]', "", name)
        cleaned = re.sub(r"\s+", "_", cleaned.strip(" ."))
        return cleaned[:45] or "unnamed_mod"

    def load_config(self):
        if not self.config_path.exists():
            self.save_config()
            return
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.lang = data.get("LANGUAGE", "ru")
            if self.lang not in TEXTS:
                self.lang = "ru"
            self.game_id = data.get("GAME_ID")
            self.game_name = data.get("GAME_NAME")
            self.game_folder = data.get("GAME_FOLDER")
            self.max_concurrent = data.get("MAX_CONCURRENT_DOWNLOADS", 2)
        except Exception as e:
            logging.error(f"Config load error: {e}")

    def save_config(self):
        self.main_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "GAME_NAME": self.game_name,
            "GAME_ID": self.game_id,
            "GAME_FOLDER": self.game_folder,
            "MAX_CONCURRENT_DOWNLOADS": self.max_concurrent,
            "LANGUAGE": self.lang,
        }
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def ensure_steamcmd(self):
        if not self.steamcmd_exe.exists():
            self.steamcmd_dir.mkdir(parents=True, exist_ok=True)
            zip_path = self.steamcmd_dir / "steamcmd.zip"
            print(self.t["steamcmd_dl"])

            # Прогресс-бар для скачивания самого архива SteamCMD
            with tqdm(unit="B", unit_scale=True, desc="SteamCMD", ncols=75) as pbar:
                def report_hook(block_num, block_size, total_size):
                    if total_size > 0:
                        pbar.total = total_size
                    pbar.update(block_size)

                urllib.request.urlretrieve(STEAMCMD_URL, zip_path, reporthook=report_hook)

            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(self.steamcmd_dir)
            zip_path.unlink(missing_ok=True)

        if os.name == "nt" and not (self.steamcmd_dir / "steamclient.dll").exists():
            print(self.t["steamcmd_init"])
            subprocess.run(
                [str(self.steamcmd_exe), "+quit"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    @property
    def mods_path(self) -> Path:
        return self.games_dir / self.game_folder / "mods"

    def setup_game(self):
        self.clear_screen()
        print(f"{self.t['setup_title']}\n{self.t['sep']}\n{self.t['setup_hint']}\n")
        while True:
            url = input("> ").strip()
            match = re.search(r"/app/(\d+)(?:/([^/?#]+))?", url)
            if match:
                self.game_id = match.group(1)
                raw_name = match.group(2) or f"Game_{self.game_id}"
                self.game_name = raw_name.replace("_", " ")
                self.game_folder = self.clean_folder_name(raw_name)
                self.mods_path.mkdir(parents=True, exist_ok=True)
                self.save_config()
                break
            print(self.t["invalid_link"])

    async def get_mods_titles(self, session: aiohttp.ClientSession, mod_ids: list[str]) -> dict[str, str]:
        payload = {"itemcount": len(mod_ids)}
        for idx, mid in enumerate(mod_ids):
            payload[f"publishedfileids[{idx}]"] = mid

        titles = {mid: mid for mid in mod_ids}
        try:
            async with session.post(STEAM_API_DETAILS_URL, data=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    details = data.get("response", {}).get("publishedfiledetails", [])
                    for item in details:
                        mid = str(item.get("publishedfileid", ""))
                        title = item.get("title")
                        if mid and title:
                            titles[mid] = title
        except Exception as e:
            logging.warning(f"Failed to fetch titles via API: {e}")
        return titles

    async def get_collection_items(self, collection_id: str) -> list[str]:
        payload = {"collectioncount": 1, "publishedfileids[0]": collection_id}
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(STEAM_API_COLLECTION_URL, data=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        details = data.get("response", {}).get("collectiondetails", [])
                        if details and "children" in details[0]:
                            return [
                                str(child["publishedfileid"])
                                for child in details[0]["children"]
                                if "publishedfileid" in child
                            ]
            except Exception as e:
                logging.error(f"Error fetching collection via API: {e}")
        return []

    def is_mod_installed(self, clean_title: str, mod_id: str) -> bool:
        return (self.mods_path / clean_title).is_dir() or (self.mods_path / mod_id).is_dir()

    def copy_mod_files(self, mod_src: Path, clean_title: str, mod_id: str) -> Path:
        dest_root = self.mods_path
        dest_target = dest_root / clean_title

        if self.game_id == "108600" and (mod_src / "mods").is_dir():
            submods = [p for p in (mod_src / "mods").iterdir() if p.is_dir()]
            if submods:
                for submod in submods:
                    target = dest_root / self.clean_folder_name(submod.name)
                    shutil.copytree(submod, target, dirs_exist_ok=True)
                return dest_root

        try:
            shutil.copytree(mod_src, dest_target, dirs_exist_ok=True)
            return dest_target
        except OSError:
            fallback_target = dest_root / mod_id
            shutil.copytree(mod_src, fallback_target, dirs_exist_ok=True)
            return fallback_target

    async def download_single_mod(
        self, mod_id: str, title: str, semaphore: asyncio.Semaphore, pbar: tqdm
    ):
        clean_title = self.clean_folder_name(title)
        if self.is_mod_installed(clean_title, mod_id):
            tqdm.write(self.t["already_installed"].format(title=title))
            pbar.update(1)
            return

        async with semaphore:
            for attempt in range(1, MAX_RETRIES + 1):
                tqdm.write(self.t["downloading"].format(title=title, id=mod_id))
                temp_mod_dir = self.temp_dir / mod_id
                temp_mod_dir.mkdir(parents=True, exist_ok=True)

                cmd = [
                    str(self.steamcmd_exe),
                    "+force_install_dir",
                    str(temp_mod_dir),
                    "+login",
                    "anonymous",
                    "+workshop_download_item",
                    str(self.game_id),
                    str(mod_id),
                    "+quit",
                ]

                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await proc.communicate()
                out_text = stdout.decode("utf-8", errors="ignore")

                mod_src = (
                    temp_mod_dir
                    / "steamapps"
                    / "workshop"
                    / "content"
                    / str(self.game_id)
                    / str(mod_id)
                )

                if proc.returncode == 0 and mod_src.exists():
                    final_path = await asyncio.to_thread(
                        self.copy_mod_files, mod_src, clean_title, mod_id
                    )
                    await asyncio.to_thread(shutil.rmtree, temp_mod_dir, ignore_errors=True)
                    tqdm.write(self.t["installed"].format(title=title, path=final_path.name))
                    pbar.update(1)
                    return

                logging.warning(f"Attempt {attempt} failed for {mod_id}. Output:\n{out_text}")
                await asyncio.to_thread(shutil.rmtree, temp_mod_dir, ignore_errors=True)

                if attempt < MAX_RETRIES:
                    tqdm.write(
                        self.t["retrying"].format(title=title, attempt=attempt, max=MAX_RETRIES)
                    )
                    await asyncio.sleep(3)

            tqdm.write(self.t["failed"].format(title=title, id=mod_id))
            pbar.update(1)

    async def process_mods(self, mod_ids: list[str]):
        print(self.t["fetching_info"])
        async with aiohttp.ClientSession() as session:
            titles = await self.get_mods_titles(session, mod_ids)

        print()
        semaphore = asyncio.Semaphore(self.max_concurrent)
        # Общий прогресс-бар для всех скачиваемых модов
        with tqdm(
            total=len(mod_ids),
            desc=self.t["progress_desc"],
            unit="мод",
            ncols=80,
            colour="green",
        ) as pbar:
            tasks = [
                self.download_single_mod(mid, titles.get(mid, mid), semaphore, pbar)
                for mid in mod_ids
            ]
            await asyncio.gather(*tasks)

        await asyncio.to_thread(shutil.rmtree, self.temp_dir, ignore_errors=True)

    def menu_download_urls(self):
        self.clear_screen()
        print(f"{self.t['urls_title']}\n{self.t['sep']}\n{self.t['urls_hint']}\n")
        mod_ids = []
        while True:
            line = input("> ").strip()
            if line.lower() == "x":
                return
            if not line:
                if mod_ids:
                    break
                continue
            found = re.findall(r"[?&]id=(\d+)", line)
            if found:
                for mid in found:
                    if mid not in mod_ids:
                        mod_ids.append(mid)
            else:
                print(self.t["invalid_link"])

        if mod_ids:
            asyncio.run(self.process_mods(mod_ids))
            input(self.t["done_prompt"])

    def menu_download_collection(self):
        self.clear_screen()
        print(f"{self.t['col_title']}\n{self.t['sep']}\n{self.t['col_hint']}\n")
        while True:
            line = input("> ").strip()
            if line.lower() == "x":
                return
            match = re.search(r"[?&]id=(\d+)", line)
            if not match:
                print(self.t["invalid_link"])
                continue

            col_id = match.group(1)
            mod_ids = asyncio.run(self.get_collection_items(col_id))
            if not mod_ids:
                print(self.t["col_empty"])
                continue

            print(self.t["col_found"].format(count=len(mod_ids)))
            if input(self.t["confirm"]).strip().lower() == "y":
                asyncio.run(self.process_mods(mod_ids))
                input(self.t["done_prompt"])
            break

    def toggle_language(self):
        self.lang = "en" if self.lang == "ru" else "ru"
        self.save_config()

    def run(self):
        while True:
            self.clear_screen()
            print(f"{self.t['title']}\n{self.t['sep']}")
            if self.game_id:
                print(self.t["current_game"].format(name=self.game_name, id=self.game_id))
                print(self.t["sep"])
                print("\n".join(self.t["menu_game"]))
                print(self.t["sep"])
                choice = input(self.t["prompt"]).strip()
                if choice == "1":
                    self.menu_download_urls()
                elif choice == "2":
                    self.menu_download_collection()
                elif choice == "3":
                    self.setup_game()
                elif choice == "4":
                    self.toggle_language()
                elif choice == "5":
                    sys.exit(0)
            else:
                print(self.t["no_game"])
                print(self.t["sep"])
                print("\n".join(self.t["menu_no_game"]))
                print(self.t["sep"])
                choice = input(self.t["prompt"]).strip()
                if choice == "1":
                    self.setup_game()
                elif choice == "2":
                    self.toggle_language()
                elif choice == "3":
                    sys.exit(0)


if __name__ == "__main__":
    try:
        WorkshopDownloader().run()
    except KeyboardInterrupt:
        sys.exit(0)
