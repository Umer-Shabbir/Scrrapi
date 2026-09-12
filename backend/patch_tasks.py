with open("backend/app/workers/tasks.py") as f:
    text = f.read()

text = text.replace(
    "from app.core.runtime_settings import (",
    "from app.core.runtime_settings import (\n    get_email_verification_mode,"
)

text = text.replace(
    "            deep_crawl = get_deep_crawl_enabled(db)",
    "            deep_crawl = get_deep_crawl_enabled(db)\n            email_verification_mode = get_email_verification_mode(db)"
)

text = text.replace(
    "                        on_crawl=_announce_crawl,\n                    )\n                )",
    "                        on_crawl=_announce_crawl,\n                        email_verification_mode=email_verification_mode,\n                    )\n                )"
)

text = text.replace(
    "    budget=None,\n    on_crawl=None,\n) -> dict:",
    "    budget=None,\n    on_crawl=None,\n    email_verification_mode: str = \"off\",\n) -> dict:"
)

text = text.replace(
    "        place, deep_crawl=deep_crawl, budget=budget, on_crawl=on_crawl\n    )",
    "        place, deep_crawl=deep_crawl, budget=budget, on_crawl=on_crawl, email_verification_mode=email_verification_mode\n    )"
)

with open("backend/app/workers/tasks.py", "w") as f:
    f.write(text)
