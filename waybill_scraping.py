import argparse
from bs4 import BeautifulSoup
import requests
import pandas as pd

URL = "https://www.buymall.com.my/"
LOGIN_ROUTE = "site/login.html"
HEADERS = {
    "content-type": "application/x-www-form-urlencoded",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36",
}
parser = argparse.ArgumentParser()
parser.add_argument(
    "-u", "--url", action="store", dest="waybill", default=None, required=True
)
parser.add_argument(
    "-n", "--username", action="store", dest="username", default=None, required=True
)
parser.add_argument(
    "-p", "--password", action="store", dest="password", default=None, required=True
)
waybill_url = parser.parse_args().waybill
username = parser.parse_args().username
password = parser.parse_args().password
with requests.Session() as session:
    csrf_token = BeautifulSoup(session.get(URL + LOGIN_ROUTE).text, "lxml").find(
        "input", {"name": "YII_CSRF_TOKEN"}
    )["value"]
    login_payload = {
        "LoginForm[username]": username,
        "LoginForm[password]": password,
        "LoginForm[rememberMe]": "0",
        "YII_CSRF_TOKEN": csrf_token,
    }
    post = session.post(URL + LOGIN_ROUTE, data=login_payload)
    assert post.status_code == 200
    waybill = session.get(URL + waybill_url).text
    soup = BeautifulSoup(waybill, "lxml")
    fee_agent = float(
        soup.find(
            "table",
            {"class": "items table table-striped table-bordered table-condensed"},
        )
        .find_all("tr")[7]
        .find("td")
        .find_next_sibling()
        .text.strip()
        .replace("MYR", "")
        .strip()
    )
    fee_shipping = float(
        soup.find(
            "table",
            {"class": "items table table-striped table-bordered table-condensed"},
        )
        .find_all("tr")[14]
        .find("td")
        .find_next_sibling()
        .text.strip()
        .replace("MYR", "")
        .strip()
    )
    fee_total = fee_agent + fee_shipping
    items = [
        item.find_all("a", href=True)[1].text
        for item in soup.find_all("tr", {"class": "js-order-container"})
    ]
    prices = [
        float(price.find_all("td", {"class": "paid"})[0].get("rm"))
        for price in soup.find_all("tr", {"class": "js-order-container"})
    ]
    weight = [
        float(str(weight.find_all("div")[1]).split("<br/>")[6].split("kg")[0])
        for weight in soup.find_all("tr", {"class": "js-order-container"})
    ]
    displacement = [
        float(
            str(weight.find_all("div")[1])
            .split("<br/>")[6]
            .split("m3")[0]
            .split("\xa0\xa0")[1]
        )
        for weight in soup.find_all("tr", {"class": "js-order-container"})
    ]
    waybill = (
        pd.DataFrame(
            {
                "Item": items,
                "Displacement": displacement,
                "Weight": weight,
                "Price": prices,
            }
        )
        .pipe(
            lambda df: df.assign(
                **{
                    "Agent Fee": df["Price"].div(df["Price"].sum()).multiply(fee_agent),
                    "Shipping Fee": df["Weight"]
                    .div(df["Weight"].sum())
                    .multiply(fee_shipping),
                }
            )
        )
        .pipe(
            lambda df: df.assign(
                **{"Total Price": df["Price"] + df["Agent Fee"] + df["Shipping Fee"]}
            )
        )
    ).sort_values(by="Total Price", ascending=False)
    waybill.to_csv(
        f"waybill_{waybill_url.split('/')[2].split('.html')[0]}.csv",
        float_format="%.3f",
        index=False,
        encoding="utf-8",
    )
