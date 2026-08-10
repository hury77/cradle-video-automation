#!/usr/bin/env bash
# install_hooks.sh
# Skrypt do instalacji wersjonowanych hooków Git dla repozytorium cradle-video-automation.

# Ustawia ścieżkę do hooków na folder .githooks w głównym katalogu repozytorium.
git config core.hooksPath .githooks

echo "✅ Git hooks zostały pomyślnie zainstalowane."
echo "Wszystkie zdefiniowane hooki (np. pre-checkout) będą teraz wywoływane automatycznie."
