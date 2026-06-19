from kufar_bot.kufar.url_parser import short_kufar_list_url


def test_short_kufar_list_url():
    url = (
        "https://www.kufar.by/l/r~mogilevskaya-obl/sad-i-ogorod/bez-posrednikov"
        "?ar=v.or%3A12%2C80%2C81%2C83%2C14&sort=lst.d"
    )
    short = short_kufar_list_url(url)
    assert short.startswith("r~mogilevskaya-obl/sad-i-ogorod")
    assert "kufar.by" not in short
