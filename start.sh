#!/usr/bin/env bash
# Запускает Gunicorn, который использует наше Flask-приложение 'app' из файла 'server.py'
gunicorn server:app