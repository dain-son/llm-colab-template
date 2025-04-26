# 키워드 (있는 것 모두) #contents2 > div.corp_info_baseinfo > div.corp_info_base2 > p > span:nth-child(1)
# 로고 #contents2 > div:nth-child(1) > div.corp_info_top > div > div.info > div.logo > img
# 신입연봉 #contents2 > div.corp_info_baseinfo > div.corp_info_base2 > div > div.btns > p:nth-child(1) > a
# 평균연봉 #contents2 > div.corp_info_baseinfo > div.corp_info_base2 > div > div.btns > p:nth-child(2) > a
# 기업 위치 주소 #contents2 > div.corp_info_baseinfo > div.corp_info_base2 > div > div.tbl > table > tbody > tr:nth-child(4) > td
# 사원수 #contents2 > div.corp_info_baseinfo > div.corp_info_base1 > div.item.type2 > div > div > p.t1
# 기업홈페이지 #contents2 > div:nth-child(1) > div.corp_info_top > div > div.info > div.txt > div > a
# 기업 형태 #contents2 > div.corp_info_baseinfo > div.corp_info_base1 > div.item.type1 > div > p
# 매출액_별도 #contents2 > div.corp_info_baseinfo > div.corp_info_base1 > div.item.type3 > div:nth-child(2) > div > p.t1
# 매출액_연결 #contents2 > div.corp_info_baseinfo > div.corp_info_base1 > div.item.type3 > div:nth-child(3) > div > p.t1
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

import pandas as pd
import time
from dotenv import load_dotenv
import os

load_dotenv()
CATCH_ID = os.getenv("CATCH_ID")
CATCH_PW = os.getenv("CATCH_PW")
print("🧪 ID/PW 확인:", CATCH_ID, CATCH_PW)


df = pd.read_csv("catch_companies.csv")

# 크롬 드라이버 설정
options = Options()
# options.add_argument("--headless")  # 창 숨기고 싶을 경우
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
service = Service(
    "/opt/homebrew/Caskroom/chromedriver/135.0.7049.97/chromedriver-mac-arm64/chromedriver"
)

driver = webdriver.Chrome(service=service, options=options)
wait = WebDriverWait(driver, 10)

# 로그인 페이지로 이동
driver.get("https://www.catch.co.kr/Member/Login")
time.sleep(2)  # 페이지 로딩 기다리기

id_input = wait.until(EC.presence_of_element_located((By.ID, "id_login")))
pw_input = driver.find_element(By.ID, "pw_login")

id_input.clear()
pw_input.clear()
time.sleep(0.5)

id_input.send_keys(CATCH_ID)
pw_input.send_keys(CATCH_PW)
pw_input.send_keys(Keys.ENTER)  # 🔥 클릭 대신 엔터로 로그인

time.sleep(3)
print("🚀 로그인 후 현재 URL:", driver.current_url)

results = []

for index, row in df.iterrows():
    try:
        url = row["링크"]
        name = row["기업명"]

        print(f"▶️ 크롤링 중: {name}")
        driver.get(url)
        time.sleep(2)

        def safe_get(selector, attr="text", multi=False):
            try:
                if multi:
                    elems = driver.find_elements(By.CSS_SELECTOR, selector)
                    return [e.text.strip() for e in elems if e.text.strip()]
                elem = driver.find_element(By.CSS_SELECTOR, selector)
                return elem.get_attribute(attr) if attr != "text" else elem.text.strip()
            except:
                return "" if not multi else []

        results.append(
            {
                "기업명": name,
                "키워드": ", ".join(
                    [
                        kw.text.strip()
                        for kw in driver.find_elements(
                            By.CSS_SELECTOR,
                            "#contents2 > div.corp_info_baseinfo > div.corp_info_base2 > p > span",
                        )
                        if kw.text.strip()
                    ]
                ),
                "로고": safe_get(
                    "#contents2 > div:nth-child(1) > div.corp_info_top > div > div.info > div.logo > img",
                    attr="src",
                ),
                "카테고리": safe_get(
                    "#contents2 > div:nth-child(1) > div.corp_info_top > div > div.info > div.txt > p > span:nth-child(2)",
                    attr="text",
                ),
                "신입연봉": safe_get(
                    "#contents2 > div.corp_info_baseinfo > div.corp_info_base2 > div > div.btns > p:nth-child(1) > a"
                ),
                "평균연봉": safe_get(
                    "#contents2 > div.corp_info_baseinfo > div.corp_info_base2 > div > div.btns > p:nth-child(2) > a"
                ),
                "주소": safe_get(
                    "#contents2 > div.corp_info_baseinfo > div.corp_info_base2 > div > div.tbl > table > tbody > tr:nth-child(4) > td"
                ),
                "사원수": safe_get(
                    "#contents2 > div.corp_info_baseinfo > div.corp_info_base1 > div.item.type2 > div > div > p.t1"
                ),
                "홈페이지": safe_get(
                    "#contents2 > div:nth-child(1) > div.corp_info_top > div > div.info > div.txt > div > a",
                    attr="href",
                ),
                "기업형태": safe_get(
                    "#contents2 > div.corp_info_baseinfo > div.corp_info_base1 > div.item.type1 > div > p"
                ),
                "매출액_별도": safe_get(
                    "#contents2 > div.corp_info_baseinfo > div.corp_info_base1 > div.item.type3 > div:nth-child(2) > div > p.t1"
                ),
                "매출액_연결": safe_get(
                    "#contents2 > div.corp_info_baseinfo > div.corp_info_base1 > div.item.type3 > div:nth-child(3) > div > p.t1"
                ),
                "사업현황": safe_get(
                    "#contents2 > div:nth-child(3) > div:nth-child(1) > div.corp_info_introduce > div > p"
                ),
            }
        )
    except Exception as e:
        print(f"❌ {row['기업명']} 에서 오류 발생: {e}")
        continue

# 종료 및 저장
driver.quit()

output_df = pd.DataFrame(results)
output_df.to_csv("catch_company_details.csv", index=False, encoding="utf-8-sig")
print("✅ 크롤링 완료: catch_company_details.csv 저장됨")
