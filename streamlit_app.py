# -*- coding: utf-8 -*-
"""
兼容入口：直接复用 app.py 的部署版本。
部署平台如果仍然启动 streamlit_app.py，也会加载同一套界面。
"""
from app import *  # noqa: F401,F403
