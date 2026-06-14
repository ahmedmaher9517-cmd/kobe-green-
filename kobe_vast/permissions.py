# -*- coding: utf-8 -*-
"""Permission matrix for user admin display."""
from kobe_vast.nav_menu import PAGE_LABELS, ROLE_PAGES


def role_pages_summary(role):
    keys = ROLE_PAGES.get(role, ROLE_PAGES["مشاهدة"])
    return [PAGE_LABELS.get(k, k) for k in keys]
