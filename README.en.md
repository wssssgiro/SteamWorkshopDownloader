# Steam Workshop Downloader

![Python](https://img.shields.io/badge/Python-3.7+-blue.svg?style=flat-square&logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)

**Download mods and collections from the Steam Workshop even without owning the game!**

This tool allows you to download Steam Workshop content for various games, even if you haven't purchased them on Steam. Simply provide the link to the game's Steam Store page along with the link to the mod or collection you want to download. Mods are neatly organized in the `/games/[Game Name]/mods/` folder.

## Features

*   **Download Mods by URL:** Install individual mods using their Steam Workshop links.
*   **Download Collections by URL:** Install entire Steam Workshop collections with a single link.
*   **Game Selection:** Easily configure and switch between different games to install mods.
*   **Parallel Downloads:** Supports downloading multiple mods simultaneously to speed up the process (configurable).
*   **Automatic SteamCMD Setup:** Automatically downloads and sets up SteamCMD if it is not already installed.
*   **Mod Existence Check:** Prevents re-downloading mods that are already installed.
*   **Invalid Character Handling in Mod Titles:** Sanitizes mod folder names to ensure compatibility with your operating system.
*   **Customizable Language:** Supports English and Russian (easy to add more languages).
*   **Logging:** Detailed logging to the `workshop_downloader.log` file for troubleshooting.

## Tested Games

This downloader has been tested for performance and confirmed to work properly with:

*   **Counter-Strike 2**
*   **RimWorld**
*   **Project Zomboid** (Optimized for Project Zomboid)

It may work with other games as well, but these have been personally verified.

## Mod Structure Support

This downloader is designed to handle standard Steam Workshop mod folder structures. However, some games or mods may use unique or non-standard directory layouts.

If you encounter issues installing mods with unusual structures, or if you would like to request extended support for mods with specific folder structures (especially for games other than Project Zomboid, Counter-Strike 2, and RimWorld), please contact me on Discord: **seilce**.

## Requirements

*   Python 3.8+ installed
*   Windows or Linux OS

## Installation and Launch

1. Download the `script.py` file.

2. Install the required dependencies:
   Open your terminal (PowerShell or Command Prompt) in the folder containing the script and run:

         pip install aiohttp tqdm
   Run the script:
   Execute the launch command:

         python script.py
