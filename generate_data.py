import requests
import json
import random
import time
import pandas as pd
import csv
import pathlib
import textwrap
import google.generativeai as genai
from google.api_core import exceptions

from dotenv import load_dotenv
import os

# .env 파일 로드
load_dotenv()

# 환경변수에서 API 키 읽기
API_KEY = os.getenv("API_KEY")

CSV_FILEPATH = "/Users/sondain/careerbee/cs_question.csv"
OUTPUT_JSON_FILEPATH = "cs_data_generated.json"

MODEL_NAME_FOR_ANSWER = "gemini-1.5-flash-latest"  # 사용자 답변 생성에 사용할 모델
MODEL_NAME_FOR_FEEDBACK = (
    "gemini-1.5-flash-latest"  # 피드백 생성에 사용할 모델 (필요시 변경)
)
PER_QUESTION_COUNT = 5  # 질문당 생성할 답변/피드백 개수
REQUEST_DELAY_SECONDS = 2  # API 요청 간 지연 시간 (Rate Limit 방지)

# --- Gemini API 설정 ---
try:
    genai.configure(api_key=API_KEY)
except Exception as e:
    print(f"API 키 설정 중 오류 발생: {e}")
    print("Google AI Studio에서 API 키를 발급받아 YOUR_API_KEY 부분을 교체해주세요.")
    exit()


# 사용 가능한 모델 확인 (선택 사항)
# print("사용 가능한 모델:")
# for m in genai.list_models():
#   if 'generateContent' in m.supported_generation_methods:
#     print(m.name)

# --- 데이터 로드 ---
try:
    df = pd.read_csv(CSV_FILEPATH, encoding="utf-8")
    questions_list = df["문제"].tolist()
    print(f"총 {len(questions_list)}개의 질문을 로드했습니다.")
except FileNotFoundError:
    print(f"오류: CSV 파일을 찾을 수 없습니다. 경로를 확인하세요: {CSV_FILEPATH}")
    exit()
except Exception as e:
    print(f"CSV 파일 로드 중 오류 발생: {e}")
    exit()

# fields = ["DevOps", "프론트엔드", "백엔드", "AI"]


# --- 함수 정의 ---
def generate_with_gemini(model_name: str, prompt: str, max_retries=3) -> str:
    """Gemini API를 호출하여 텍스트를 생성하는 함수 (재시도 로직 포함)"""
    model = genai.GenerativeModel(model_name)
    generation_config = genai.types.GenerationConfig(
        # candidate_count=1, # 기본값 1
        # stop_sequences=['...'], # 특정 시퀀스에서 생성 중단
        max_output_tokens=500,  # 최대 출력 토큰 수 조정
        temperature=0.7,  # 창의성 조절 (0.0 ~ 1.0)
        # top_p=0.9, # 단어 선택 다양성 조절
        # top_k=40 # 단어 선택 다양성 조절
    )
    # 안전 설정 (필요에 따라 조정)
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
            # response.text 접근 전에 response.parts가 비어있는지 확인
            if response.parts:
                # response.candidates[0].content.parts[0].text 와 동일
                return response.text.strip()
            else:
                # 응답이 비어있거나, 안전 설정 등에 의해 차단된 경우
                print(
                    f"Warning: 모델로부터 빈 응답을 받았습니다. 프롬프트: {prompt[:100]}..."
                )
                print(f"차단 이유: {response.prompt_feedback}")  # 차단 이유 확인
                return ""  # 빈 문자열 반환 또는 다른 처리

        except exceptions.ResourceExhausted as e:  # Rate limit 에러 처리
            print(
                f"Rate limit 에러 발생: {e}. {REQUEST_DELAY_SECONDS * (retries + 2)}초 후 재시도합니다..."
            )
            time.sleep(REQUEST_DELAY_SECONDS * (retries + 2))  # 대기 시간 점진적 증가
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


def generate_user_answer_gemini(question: str) -> str:
    """(1) '질문'을 보고, '사용자 답변'을 생성하도록 Gemini API 호출"""
    prompt = f"""당신은 주어진 CS 질문에 대해 사용자가 답했을 법한 답변을 생성하는 역할입니다.
답변은 완벽하지 않아도 괜찮습니다. 약간 부족하거나, 핵심만 간략하게 언급하는 수준으로 작성해주세요.

질문: {question}
사용자 답변 예시:"""  # 예시 포맷을 명확히 제시

    user_answer = generate_with_gemini(MODEL_NAME_FOR_ANSWER, prompt)
    return user_answer


def generate_feedback_gemini(question: str, user_answer: str) -> str:
    """(2) '질문 + 사용자 답변'을 보고, '피드백'을 생성하도록 Gemini API 호출"""
    prompt = f"""당신은 CS 면접관이며, 사용자의 답변에 대해 피드백을 작성해주는 역할입니다.
다음 질문과 사용자의 답변을 보고, 구체적인 피드백(칭찬할 점, 아쉬운 점, 보완하면 좋을 내용 등)을 한국어로 작성해주세요. 친절하고 상세하게 설명하되, 너무 길지 않게 핵심 위주로 작성해주세요.

질문: {question}
사용자 답변: {user_answer}

피드백:"""  # 피드백 시작 부분 명시

    feedback = generate_with_gemini(MODEL_NAME_FOR_FEEDBACK, prompt)
    return feedback


def main():
    results = []
    total_questions = len(questions_list)
    total_generations = total_questions * PER_QUESTION_COUNT

    print(f"총 {total_generations}개의 데이터 생성을 시작합니다...")

    generation_count = 0
    for q_idx, question in enumerate(questions_list):
        print(
            f"\n--- 질문 {q_idx + 1}/{total_questions} 처리 중: {question[:50]}... ---"
        )
        generated_for_this_question = 0
        while generated_for_this_question < PER_QUESTION_COUNT:
            current_attempt = generated_for_this_question + 1
            print(f"  답변/피드백 생성 시도: {current_attempt}/{PER_QUESTION_COUNT}")

            # 1) 질문에 대한 "사용자 답변" 생성
            user_answer = generate_user_answer_gemini(question)
            if not user_answer:  # 답변 생성 실패 시 다음 시도
                print("  사용자 답변 생성 실패. 다음 시도를 진행합니다.")
                time.sleep(REQUEST_DELAY_SECONDS)  # 실패 시에도 잠시 대기
                continue  # 다음 루프 반복 (while)

            time.sleep(REQUEST_DELAY_SECONDS)  # API 호출 간 지연

            # 2) 생성된 "질문+사용자답변"으로부터 피드백 생성
            feedback = generate_feedback_gemini(question, user_answer)
            if not feedback:  # 피드백 생성 실패 시 다음 시도
                print("  피드백 생성 실패. 다음 시도를 진행합니다.")
                time.sleep(REQUEST_DELAY_SECONDS)  # 실패 시에도 잠시 대기
                continue  # 다음 루프 반복 (while)

            # 3) instruction, input, output 구성
            record = {
                "instruction": "다음 질문에 대한 사용자의 답변을 보고 피드백을 작성해주세요. 사용자의 답변 수준에 맞춰 칭찬할 부분과 개선할 부분을 구체적으로 언급하고, 친절한 말투로 설명해주세요. 피드백 길이는 500자 이내로 해주세요.",
                "input": f"질문: {question}\n답변: {user_answer}",
                "output": feedback,
            }
            results.append(record)
            generation_count += 1
            generated_for_this_question += 1
            print(f"  성공: {generation_count}/{total_generations} 데이터 생성 완료.")

            # Rate limit 대비 잠시 대기
            time.sleep(REQUEST_DELAY_SECONDS)

    # 결과를 JSON 파일로 저장
    try:
        with open(OUTPUT_JSON_FILEPATH, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(
            f"\n총 {len(results)}개의 (질문, 사용자답변, 피드백) 데이터가 {OUTPUT_JSON_FILEPATH}에 저장되었습니다."
        )
    except Exception as e:
        print(f"JSON 파일 저장 중 오류 발생: {e}")


if __name__ == "__main__":
    main()
