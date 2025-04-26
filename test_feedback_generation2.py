import json
import time
import pandas as pd
import pathlib
import google.generativeai as genai
from google.api_core import exceptions  # 예외 처리를 위해 추가
import random
import os

# --- 설정 ---
# !!! 중요: 실제 발급받은 API 키로 교체하세요 !!!
# Google AI Studio (https://aistudio.google.com/app/apikey) 에서 API 키를 발급받으세요.
API_KEY = os.getenv("GOOLE_API_KEY")  # 본인의 API 키 입력

CSV_FILEPATH = "/Users/sondain/careerbee/cs_question.csv"  # 질문 CSV 파일 경로 확인
OUTPUT_DIR = "/Users/sondain/careerbee/feedback_data"  # 분할 저장할 디렉토리 경로
MODEL_NAME_FOR_ANSWER = (
    "gemini-1.5-flash-latest"  # 사용자 답변 생성 모델 (무료 티어 모델 권장)
)
MODEL_NAME_FOR_FEEDBACK = (
    "gemini-1.5-flash-latest"  # 피드백 생성 모델 (무료 티어 모델 권장)
)
REQUEST_DELAY_SECONDS = 2  # API 요청 간 지연 시간 (Rate Limit 방지)
NUM_QUESTIONS = 274  # 실제 질문 개수
NUM_ANSWERS_PER_QUESTION = 4  # 각 질문당 생성할 답변 개수 (4구간)
TARGET_SAMPLE_COUNT = NUM_QUESTIONS * NUM_ANSWERS_PER_QUESTION  # 총 목표 샘플 개수
FEEDBACK_MAX_LENGTH = 480  # 피드백 최대 길이 (더욱 엄격하게 제한)
SAVE_BATCH_SIZE = 200  # 저장 단위

# --- Gemini API 설정 ---
try:
    genai.configure(api_key=API_KEY)
except Exception as e:
    print(f"API 키 설정 중 오류 발생: {e}")
    print("Google AI Studio에서 API 키를 발급받아 YOUR_API_KEY 부분을 교체해주세요.")
    exit()  # API 키 설정 실패 시 종료

# --- 데이터 로드 ---
try:
    df = pd.read_csv(CSV_FILEPATH, encoding="utf-8")
    questions_list = df["문제"].tolist()
    print(f"총 {len(questions_list)}개의 질문을 로드했습니다.")
    if len(questions_list) != NUM_QUESTIONS:
        print(
            f"경고: 로드된 질문 개수({len(questions_list)})가 설정된 질문 개수({NUM_QUESTIONS})와 다릅니다. 설정값을 확인해주세요."
        )
        if len(questions_list) < TARGET_SAMPLE_COUNT:
            TARGET_SAMPLE_COUNT = len(questions_list) * NUM_ANSWERS_PER_QUESTION
except FileNotFoundError:
    print(f"오류: CSV 파일을 찾을 수 없습니다. 경로를 확인하세요: {CSV_FILEPATH}")
    exit()
except Exception as e:
    print(f"CSV 파일 로드 중 오류 발생: {e}")
    exit()


# --- 함수 정의 (수준별 답변 생성을 위한 temperature 조절) ---
def generate_with_gemini(
    model_name: str, prompt: str, temperature: float = 0.7, max_retries=3
) -> str:
    """Gemini API를 호출하여 텍스트를 생성하는 함수 (재시도 로직 포함)"""
    model = genai.GenerativeModel(model_name)
    generation_config = genai.types.GenerationConfig(
        max_output_tokens=550,  # 피드백 최대 길이 고려하여 약간 여유 있게 설정
        temperature=temperature,  # 창의성 조절 (0.0 ~ 1.0) - 답변 수준 조절
    )
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {
            "category": "HARM_CATEGORY_HATE_SPEECH",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE",
        },
        {
            "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE",
        },
        {
            "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE",
        },
    ]

    retries = 0
    while retries < max_retries:
        try:
            response = model.generate_content(
                prompt,
                generation_config=generation_config,
                safety_settings=safety_settings,
            )
            if response.parts:
                return response.text.strip()
            else:
                print(
                    f"Warning: 모델로부터 빈 응답을 받았습니다. 프롬프트: {prompt[:100]}..."
                )
                print(f"차단 이유: {response.prompt_feedback}")
                return ""
        except exceptions.ResourceExhausted as e:  # Rate limit 에러 처리
            wait_time = REQUEST_DELAY_SECONDS * (2**retries)  # 지수 백오프
            print(
                f"Rate limit 에러 발생. {wait_time:.1f}초 후 재시도합니다... (시도 {retries + 1}/{max_retries})"
            )
            time.sleep(wait_time)
            retries += 1
        except exceptions.GoogleAPIError as e:  # 기타 Google API 에러
            print(f"Gemini API 호출 중 오류 발생 (GoogleAPIError): {e}")
            print(f"프롬프트: {prompt[:100]}...")
            return ""  # 오류 시 빈 문자열 반환
        except Exception as e:  # 기타 예상치 못한 에러
            print(f"Gemini API 호출 중 예상치 못한 오류 발생: {e}")
            print(f"프롬프트: {prompt[:100]}...")
            return ""  # 오류 시 빈 문자열 반환

    print(f"최대 재시도 횟수({max_retries}) 초과. 생성 실패.")
    return ""


def generate_user_answer_gemini(question: str, level: int) -> str:
    """(1) '질문'을 보고, 수준별로 다른 사용자 답변을 생성하도록 Gemini API 호출"""
    if level == 1:  # 틀렸거나 부족한 답변
        prompt = f"""주어진 Computer Science 질문에 대해 **부족하거나 약간 틀린** 사용자 답변을 생성해주세요.
        답변은 문어체로 작성하며, 최대 2문장으로 짧게 작성해주세요.
        질문: {question}
        부족하거나 틀린 답변 예시:"""
        temperature = 0.3  # 낮은 temperature로 덜 창의적인 답변 유도
    elif level == 2:  # 약간 부족한 답변
        prompt = f"""주어진 Computer Science 질문에 대해 **핵심 내용을 일부 놓치거나 설명이 부족한** 사용자 답변을 생성해주세요.
        답변은 문어체로 작성하며, 최대 3문장으로 작성해주세요.
        질문: {question}
        약간 부족한 답변 예시:"""
        temperature = 0.5
    elif level == 3:  # 비교적 정확한 답변
        prompt = f"""주어진 Computer Science 질문에 대해 **비교적 정확하게 설명하는** 사용자 답변을 생성해주세요.
        답변은 문어체로 작성하며, 3~4문장으로 작성해주세요.
        질문: {question}
        정확한 답변 예시:"""
        temperature = 0.7  # 기본 temperature
    elif level == 4:  # 정확하고 완벽한 답변
        prompt = f"""주어진 Computer Science 질문에 대해 **정확하고 완벽하게 설명하는** 사용자 답변을 생성해주세요.
        답변은 문어체로 작성하며, 3~5문장으로 자세하게 작성해주세요.
        질문: {question}
        정확하고 완벽한 답변 예시:"""
        temperature = 0.9  # 높은 temperature로 더 자세하고 창의적인 답변 유도
    else:
        raise ValueError("level은 1에서 4 사이의 값이어야 합니다.")

    user_answer = generate_with_gemini(
        MODEL_NAME_FOR_ANSWER, prompt, temperature=temperature
    )
    return user_answer


def generate_feedback_gemini(question: str, user_answer: str) -> str:
    """(2) '질문 + 사용자 답변'을 보고, '피드백'을 생성하도록 Gemini API 호출"""
    prompt = f"""당신은 Computer Science 문제 출제자이며, 사용자가 입력한 답변에 대해 피드백을 해주는 역할입니다.
다음 질문과 사용자의 답변을 보고, 구체적인 피드백(칭찬할 점, 아쉬운 점, 보완하면 좋을 내용 등)을 한국어로 작성해주세요. **핵심 내용을 압축적으로 요약하여 최대 {FEEDBACK_MAX_LENGTH}자 이내로** 작성해야 합니다. 답변이 부족하거나 틀린 경우, **가장 중요한 핵심 개선 사항**을 명확하고 간결하게 제시해주세요.

질문: {question}
사용자 답변: {user_answer}

피드백:"""
    feedback = generate_with_gemini(
        MODEL_NAME_FOR_FEEDBACK, prompt, temperature=0.5
    )  # temperature 낮춰서 요약 집중
    return feedback


# --- 메인 실행 로직 (수준별 답변 생성 및 분할 저장) ---
def main():
    print(f"--- {TARGET_SAMPLE_COUNT}개의 샘플 데이터 생성 시작 ---")
    generated_data = []
    generated_count = 0
    batch_number = 1

    # 출력 디렉토리 생성
    pathlib.Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    for question in questions_list:
        for level in range(1, NUM_ANSWERS_PER_QUESTION + 1):
            if generated_count >= TARGET_SAMPLE_COUNT:
                print(f"\n목표 샘플 개수({TARGET_SAMPLE_COUNT}) 생성을 완료했습니다.")
                break

            print(
                f"\n--- 샘플 {generated_count + 1}/{TARGET_SAMPLE_COUNT} 생성 시도 (질문: '{question[:30]}...', 수준: {level}) ---"
            )

            # 1) 질문에 대한 수준별 "사용자 답변" 생성
            user_answer = generate_user_answer_gemini(question, level)
            if not user_answer:
                print(
                    f"  -> 수준 {level} 사용자 답변 생성 실패. 다음 시도로 넘어갑니다."
                )
                time.sleep(REQUEST_DELAY_SECONDS)
                continue

            print(f"\n[생성된 사용자 답변 (수준 {level})]\n{user_answer}")
            time.sleep(REQUEST_DELAY_SECONDS)

            # 2) 생성된 "질문+사용자답변"으로부터 피드백 생성
            feedback = generate_feedback_gemini(question, user_answer)
            if not feedback:
                print("\n  -> 피드백 생성 실패. 다음 시도로 넘어갑니다.")
                time.sleep(REQUEST_DELAY_SECONDS)
                continue

            print(f"\n[생성된 피드백]\n{feedback}")

            generated_data.append(
                {
                    "질문": question,
                    "사용자 답변": user_answer,
                    "피드백": feedback,
                    "답변 수준": level,
                }
            )
            generated_count += 1
            time.sleep(REQUEST_DELAY_SECONDS)

            # 배치 저장
            if generated_count % SAVE_BATCH_SIZE == 0:
                output_filepath = (
                    pathlib.Path(OUTPUT_DIR)
                    / f"feedback_data_batch_{batch_number}.json"
                )
                try:
                    with open(output_filepath, "w", encoding="utf-8") as f:
                        json.dump(generated_data, f, ensure_ascii=False, indent=4)
                    print(
                        f"\n--- {len(generated_data)}개의 샘플 데이터를 '{output_filepath}'에 저장했습니다. (배치 {batch_number}) ---"
                    )
                    generated_data = []  # 저장 후 초기화
                    batch_number += 1
                except Exception as e:
                    print(
                        f"\n오류: JSON 파일 저장 중 오류 발생 (배치 {batch_number}): {e}"
                    )

        if generated_count >= TARGET_SAMPLE_COUNT:
            break

    # 남은 데이터 저장
    if generated_data:
        output_filepath = (
            pathlib.Path(OUTPUT_DIR) / f"feedback_data_batch_{batch_number}.json"
        )
        try:
            with open(output_filepath, "w", encoding="utf-8") as f:
                json.dump(generated_data, f, ensure_ascii=False, indent=4)
            print(
                f"\n--- 남은 {len(generated_data)}개의 샘플 데이터를 '{output_filepath}'에 저장했습니다. (배치 {batch_number}) ---"
            )
        except Exception as e:
            print(f"\n오류: JSON 파일 저장 중 오류 발생 (남은 데이터): {e}")

    if generated_count < TARGET_SAMPLE_COUNT:
        print(
            f"\n경고: 목표했던 {TARGET_SAMPLE_COUNT}개 중 {generated_count}개의 샘플만 생성되었습니다."
        )
    print("\n--- 데이터 생성 및 저장 종료 ---")


if __name__ == "__main__":
    main()
