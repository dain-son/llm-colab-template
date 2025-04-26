from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import time
import pandas as pd
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 크롬 옵션 설정
options = Options()
#options.add_argument("--headless")  # 브라우저 창을 띄우지 않음
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

# 크롬드라이버 경로 지정
service = Service(
    "/opt/homebrew/Caskroom/chromedriver/135.0.7049.97/chromedriver-mac-arm64/chromedriver"
)  # 👈 ChromeDriver 경로로 수정

# 드라이버 시작
driver = webdriver.Chrome(service=service, options=options)
wait = WebDriverWait(driver, 10)  # 최대 10초까지 기다림
url = "https://www.catch.co.kr/Comp/CompMajor/SearchPage"  # 필터링된 URL

driver.get(url)
time.sleep(3)  # 페이지 로딩 대기

# ✅ 업종 선택: IT・통신
# 업종 필터 열기
# 업종 버튼 클릭 (드롭다운 열기)
industry_btn = wait.until(
    EC.element_to_be_clickable(
        (By.CSS_SELECTOR, "#contents2 > div.corp_fav_category2 > div.filter_search > div > div:nth-child(2) > button")
    )
)
industry_btn.click()
time.sleep(1.5)  # 드롭다운 애니메이션 시간 고려

# IT・통신 클릭 (정확한 li 위치 기반)
it_btn = wait.until(
    EC.element_to_be_clickable(
        (By.CSS_SELECTOR, "#contents2 > div.corp_fav_category2 > div.filter_search > div > div:nth-child(2) > ul > li:nth-child(5) > button")
    )
)
it_btn.click()
time.sleep(1)

# 'IT・통신 전체' 체크박스 라벨 클릭
it_total_label = wait.until(
    EC.element_to_be_clickable(
        (By.CSS_SELECTOR, "#contents2 > div.corp_fav_category2 > div.filter_search > div > div:nth-child(2) > ul > li:nth-child(5) > div > span:nth-child(1) > label")
    )
)
it_total_label.click()
time.sleep(1)


# ✅ 결과 반영될 때까지 기업 리스트가 최소 1개 이상 생기기를 기다림
wait.until(
    EC.presence_of_element_located(
        (By.CSS_SELECTOR, "#contents2 > div.corp_sch_result2 > ul > li")
    )
)

area_btn = wait.until(
    EC.element_to_be_clickable((By.CSS_SELECTOR, "#contents2 > div.corp_fav_category2 > div.filter_search > div > div:nth-child(3) > button"))
)
area_btn.click()
time.sleep(0.5)

# ✅ '경기' 클릭
gyeonggi_btn = WebDriverWait(driver, 10).until(
    EC.element_to_be_clickable(
        (By.CSS_SELECTOR, "#contents2 > div.corp_fav_category2 > div.filter_search > div > div:nth-child(3) > ul > li:nth-child(9) > button")
    )
)
gyeonggi_btn.click()
time.sleep(0.5)

# ✅ '성남시' 클릭
# ✅ '성남시' 체크박스 라벨 클릭
seongnam_label = WebDriverWait(driver, 10).until(
    EC.element_to_be_clickable(
        (By.CSS_SELECTOR, "#contents2 > div.corp_fav_category2 > div.filter_search > div > div:nth-child(3) > ul > li:nth-child(9) > div > span:nth-child(12) > label")
    )
)
seongnam_label.click()
time.sleep(1)


# ✅ 규모 선택: 대기업, 중견기업, 중소기업1
# ✅ 규모형태 필터 열기
# ✅ 규모형태 필터 열기
size_btn = wait.until(
    EC.element_to_be_clickable(
        (By.CSS_SELECTOR, "#contents2 > div.corp_fav_category2 > div.filter_search > div > div:nth-child(4) > button")
    )
)
size_btn.click()
time.sleep(1.0)

# ✅ 라벨 클릭 방식으로 안정화
wait.until(EC.element_to_be_clickable((By.XPATH, '//label[@for="sizeSub_0"]'))).click()
wait.until(EC.element_to_be_clickable((By.XPATH, '//label[@for="sizeSub_1"]'))).click()
wait.until(EC.element_to_be_clickable((By.XPATH, '//label[@for="sizeSub_2"]'))).click()
time.sleep(2)


companies = []
page = 1
prev_company_names = set()

while True:
    print(f"📄 페이지 {page} 수집 중...")

    # 기업 카드 수집
    cards = driver.find_elements(
        By.CSS_SELECTOR, "#contents2 > div.corp_sch_result2 > ul > li"
    )

    current_page_names = set()
    for card in cards:
        try:
            name = card.find_element(By.CSS_SELECTOR, "div.txt > p.name > a").text
            detail_link = card.find_element(
                By.CSS_SELECTOR, "div.txt > p.name > a"
            ).get_attribute("href")
            companies.append({"기업명": name, "링크": detail_link})
            current_page_names.add(name)
        except:
            continue

    # 다음 페이지 이동 시도
    try:
        next_btn = driver.find_element(
            By.CSS_SELECTOR, "#contents2 > div.corp_sch_result2 > p > a.ico.next"
        )

        # ✅ 종료 조건: 다음 페이지의 기업들이 이전과 같다면 마지막 페이지로 판단
        if current_page_names == prev_company_names:
            print("✅ 마지막 페이지 도달 (데이터 중복 감지). 수집 완료.")
            break

        prev_company_names = current_page_names

        driver.execute_script("arguments[0].click();", next_btn)
        page += 1

        # 다음 페이지 로딩 대기
        wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "#contents2 > div.corp_sch_result2 > ul > li")
            )
        )
        time.sleep(1)

    except Exception as e:
        print("🚫 다음 버튼 클릭 실패 - 종료")
        print(f"에러 메시지: {e}")
        break

# 데이터프레임으로 변환
pd.DataFrame(companies).to_csv("catch_companies.csv", index=False, encoding="utf-8-sig")

driver.quit()
print("✅ 크롤링 완료. catch_companies.csv 파일로 저장되었습니다.")