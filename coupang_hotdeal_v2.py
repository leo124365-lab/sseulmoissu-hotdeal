import os
import hmac
import hashlib
import requests
import html

from time import gmtime, strftime
from datetime import datetime
from dotenv import load_dotenv


# =========================================================
# 1. 쿠팡 API 키 불러오기
# =========================================================

load_dotenv()

ACCESS_KEY = os.getenv("COUPANG_ACCESS_KEY")
SECRET_KEY = os.getenv("COUPANG_SECRET_KEY")

DOMAIN = "https://api-gateway.coupang.com"
METHOD = "GET"

URL = "/v2/providers/affiliate_open_api/apis/openapi/products/goldbox"


# =========================================================
# 2. 쿠팡 인증
# =========================================================

def generate_hmac(method, url, secret_key, access_key):

    path, *query_parts = url.split("?")

    datetime_gmt = (
        strftime("%y%m%d", gmtime())
        + "T"
        + strftime("%H%M%S", gmtime())
        + "Z"
    )

    query_string = query_parts[0] if query_parts else ""

    message = datetime_gmt + method + path + query_string

    signature = hmac.new(
        bytes(secret_key, "utf-8"),
        message.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    return (
        f"CEA algorithm=HmacSHA256, "
        f"access-key={access_key}, "
        f"signed-date={datetime_gmt}, "
        f"signature={signature}"
    )


authorization = generate_hmac(
    METHOD,
    URL,
    SECRET_KEY,
    ACCESS_KEY
)


# =========================================================
# 3. 오늘 골드박스 상품 가져오기
# =========================================================

response = requests.get(
    DOMAIN + URL,
    headers={
        "Authorization": authorization,
        "Content-Type": "application/json;charset=UTF-8"
    }
)

if response.status_code != 200:
    print("쿠팡 API 호출 실패")
    print(response.status_code)
    print(response.text)
    exit()


data = response.json()

products = data.get("data", [])

if isinstance(products, dict):
    products = products.get("productData", [])


print("오늘 골드박스 상품:", len(products), "개")


# =========================================================
# 4. 핫딜 상품 자동 점수 계산
# =========================================================

def calculate_scores(product):

    deal_score = 0
    content_score = 0

    name = str(product.get("productName", ""))
    category = str(product.get("categoryName", ""))

    try:
        price = float(product.get("productPrice", 0))
    except:
        price = 0

    try:
        rank = int(product.get("rank", 999))
    except:
        rank = 999


    # 1. 골드박스 순번 점수
    if rank <= 3:
        deal_score += 15
    elif rank <= 10:
        deal_score += 10
    elif rank <= 20:
        deal_score += 5


    # 2. 골드박스 등록 기본점수
    deal_score += 20


    # 3. 가격 점수
    if 10000 <= price < 50000:
        deal_score += 25
    elif 50000 <= price < 100000:
        deal_score += 20
    elif price < 10000:
        deal_score += 18
    elif 100000 <= price < 200000:
        deal_score += 12
    elif 200000 <= price < 300000:
        deal_score += 6


    # 4. 배송 점수
    if product.get("isRocket"):
        deal_score += 10

    if product.get("isFreeShipping"):
        deal_score += 5


    # 5. 카테고리 점수
    category_scores = {
        "생활용품": 15,
        "가전디지털": 18,
        "주방용품": 18,
        "뷰티": 14,
        "홈인테리어": 15,
        "자동차용품": 15,
        "스포츠/레저": 10,
        "식품": 8,
        "로켓프레시": 8,
    }

    deal_score += category_scores.get(category, 5)


    # 6. 콘텐츠성이 강한 상품
    strong_keywords = [
        "자동",
        "무선",
        "청소",
        "세척",
        "클리너",
        "살균",
        "흡입",
        "방수",
        "LED",
        "충전",
        "전기",
        "온열",
        "가열",
        "건조",
        "마사지",
        "교정",
        "수납",
        "정리",
        "절약",
        "초경량",
        "안심",
        "스텐",
    ]

    if any(word in name for word in strong_keywords):
        content_score += 25


    # 7. 화면에서 기능이 잘 보이는 상품
    visual_keywords = [
        "전후",
        "회전",
        "분사",
        "접이식",
        "LED",
        "자동",
        "세척",
        "흡입",
        "건조",
        "커팅",
        "방수",
    ]

    if any(word in name for word in visual_keywords):
        content_score += 12


    # 8. 계절성
    current_month = datetime.now().month

    cold_season_keywords = [
        "전기요",
        "온열",
        "난방",
        "히터",
        "보온",
        "가습",
        "전기장판",
    ]

    if current_month in [10, 11, 12, 1, 2]:
        if any(word in name for word in cold_season_keywords):
            content_score += 20


    # 9. 콘텐츠로는 약한 생필품 감점
    weak_content_keywords = [
        "생수",
        "콜라",
        "음료",
        "두유",
        "우유",
        "종이컵",
        "화장지",
        "메론",
    ]

    if any(word in name for word in weak_content_keywords):
        content_score -= 12

    if content_score < 0:
        content_score = 0


    total_score = deal_score + content_score

    return deal_score, content_score, total_score


# 모든 골드박스 상품 점수 계산
for product in products:

    deal_score, content_score, total_score = calculate_scores(product)

    product["_deal_score"] = deal_score
    product["_content_score"] = content_score
    product["_score"] = total_score
# =========================================================
# 판매용 TOP 10
# 프로필 핫딜 페이지에 보여줄 상품
# =========================================================

hotdeal_products = sorted(
    products,
    key=lambda x: x.get("_deal_score", 0),
    reverse=True
)

selected_products = hotdeal_products[:10]


# =========================================================
# 콘텐츠용 TOP 3
# 쇼츠 / 릴스 소재 후보
# =========================================================

content_products = sorted(
    products,
    key=lambda x: (
        x.get("_content_score", 0),
        x.get("_deal_score", 0)
    ),
    reverse=True
)

content_products = [
    product
    for product in content_products
    if product.get("_content_score", 0) > 0
][:3]


print()
print("=== 프로필 핫딜 TOP 10 ===")

for i, product in enumerate(selected_products, start=1):

    print(
        f"{i}. "
        f"판매 {product.get('_deal_score', 0)} "
        f"| 콘텐츠 {product.get('_content_score', 0)} "
        f"| {product.get('productName')} "
        f"| {product.get('productPrice')}원"
    )


print()
print("=== 오늘 콘텐츠 후보 TOP 3 ===")

for i, product in enumerate(content_products, start=1):

    print(
        f"{i}. "
        f"콘텐츠 {product.get('_content_score', 0)} "
        f"| 판매 {product.get('_deal_score', 0)} "
        f"| {product.get('productName')} "
        f"| {product.get('productPrice')}원"
    )

print()
cards = ""
for product in selected_products:

    name = html.escape(str(product.get("productName", "")))
    category = html.escape(str(product.get("categoryName", "")))

    price = product.get("productPrice", 0)

    try:
        price = f"{int(float(price)):,}"
    except:
        price = str(price)

    image = product.get("productImage", "")
    url = product.get("productUrl", "")

    rocket = product.get("isRocket", False)
    free_shipping = product.get("isFreeShipping", False)

    badges = ""

    if rocket:
        badges += '<span class="badge">로켓배송</span>'

    if free_shipping:
        badges += '<span class="badge">무료배송</span>'

    cards += f"""
    <div class="card">

        <img
            src="{image}"
            class="product-image"
            alt="{name}"
        >

        <div class="product-info">

            <div class="category">
                {category}
            </div>

            <div class="product-name">
                {name}
            </div>

            <div class="badges">
                {badges}
            </div>

            <div class="price">
                {price}원
            </div>

            <a
                class="buy-button"
                href="{url}"
                target="_blank"
                rel="nofollow sponsored"
            >
                쿠팡에서 보기
            </a>

        </div>

    </div>
    """


# =========================================================
# 6. 전체 웹페이지 만들기
# =========================================================

today = datetime.now().strftime("%Y.%m.%d")

page = f"""
<!DOCTYPE html>

<html lang="ko">

<head>

<meta charset="UTF-8">

<meta name="viewport"
content="width=device-width, initial-scale=1.0">

<title>오늘의 쓸모 핫딜</title>

<style>

body {{
    margin: 0;
    background: #f5f5f5;
    font-family:
        Arial,
        "Apple SD Gothic Neo",
        "Malgun Gothic",
        sans-serif;
}}

.container {{
    max-width: 600px;
    margin: auto;
    padding: 20px;
}}

.header {{
    margin-bottom: 22px;
}}

.title {{
    font-size: 28px;
    font-weight: 800;
    margin-bottom: 7px;
}}

.date {{
    color: #777;
    font-size: 14px;
}}

.notice {{
    background: #ffffff;
    padding: 12px;
    border-radius: 10px;
    font-size: 12px;
    color: #666;
    line-height: 1.5;
    margin-bottom: 18px;
}}

.card {{
    background: white;
    border-radius: 16px;
    overflow: hidden;
    margin-bottom: 18px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.07);
}}

.product-image {{
    width: 100%;
    display: block;
}}

.product-info {{
    padding: 16px;
}}

.category {{
    font-size: 12px;
    color: #888;
    margin-bottom: 7px;
}}

.product-name {{
    font-size: 17px;
    font-weight: 700;
    line-height: 1.4;
}}

.badges {{
    margin-top: 10px;
}}

.badge {{
    display: inline-block;
    background: #eeeeee;
    border-radius: 6px;
    padding: 5px 8px;
    font-size: 11px;
    margin-right: 5px;
}}

.price {{
    font-size: 23px;
    font-weight: 800;
    margin-top: 13px;
    margin-bottom: 13px;
}}

.buy-button {{
    display: block;
    text-align: center;
    text-decoration: none;
    background: #111;
    color: white;
    padding: 15px;
    border-radius: 10px;
    font-weight: 700;
}}

.footer {{
    text-align: center;
    color: #999;
    font-size: 12px;
    padding: 20px 0 40px;
}}

</style>

</head>


<body>

<div class="container">

    <div class="header">

        <div class="title">
            🔥 오늘의 쓸모 핫딜
        </div>

        <div class="date">
            {today} 업데이트
        </div>

    </div>


    <div class="notice">

        쿠팡파트너스 활동을 통해
        일정액의 수수료를 제공받을 수 있습니다.

        <br><br>

        상품 가격과 재고는 쿠팡에서
        실시간으로 변경될 수 있습니다.

    </div>


    {cards}


    <div class="footer">

        오늘의 핫딜은 매일 업데이트됩니다.

    </div>

</div>

</body>

</html>
"""


# =========================================================
# 7. hotdeal.html 파일로 저장
# =========================================================

with open(
    "hotdeal.html",
    "w",
    encoding="utf-8"
) as file:

    file.write(page)


print()
print("완료!")
print("hotdeal.html 파일이 생성되었습니다.")