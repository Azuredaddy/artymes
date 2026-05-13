from datetime import datetime


def _get_weather() -> str:
    try:
        import requests
        r = requests.get("https://wttr.in/?format=3", timeout=4)
        if r.status_code == 200:
            return r.text.strip()
    except Exception:
        pass
    return None


def _get_news_headlines() -> str:
    try:
        import requests
        import re
        r = requests.get(
            "https://feeds.bbci.co.uk/news/rss.xml", timeout=5,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        if r.status_code == 200:
            titles = re.findall(r"<title><!\[CDATA\[(.*?)\]\]></title>", r.text)
            headlines = [t for t in titles[1:6] if t]
            if headlines:
                return "; ".join(headlines)
    except Exception:
        pass
    return None


def build_live_context() -> str:
    """
    Builds a real-time awareness block injected into ARTY's system prompt.
    Covers: date/time, day of week, weather, top news.
    """
    now = datetime.now()
    lines = []

    # Date & time
    lines.append(f"Current date: {now.strftime('%A, %d %B %Y')}")
    lines.append(f"Current time: {now.strftime('%H:%M')}")

    # Season
    month = now.month
    if month in (12, 1, 2):
        season = "winter"
    elif month in (3, 4, 5):
        season = "spring"
    elif month in (6, 7, 8):
        season = "summer"
    else:
        season = "autumn"
    lines.append(f"Current season: {season}")

    # Weather
    weather = _get_weather()
    if weather:
        lines.append(f"Current weather: {weather}")

    # News
    headlines = _get_news_headlines()
    if headlines:
        lines.append(f"Today's top news headlines: {headlines}")

    block = "\n".join(lines)
    return f"## Live Awareness\n{block}\n\nUse this information naturally when relevant. Don't recite it unprompted — only bring it up if the user asks or it's genuinely useful."
