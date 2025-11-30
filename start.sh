#!/usr/bin/env bash
gunicorn --timeout 150 server:app
