#!/usr/bin/env bash

alembic upgrade head
fastapi run
