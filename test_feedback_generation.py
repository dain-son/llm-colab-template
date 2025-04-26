import json
import time
import pandas as pd
import pathlib
import google.generativeai as genai
from google.api_core import exceptions # 예외 처리를 위해 추가

# --- 설정 ---
# !!! 중요: 실제 발급받은 API 키로 교체하세요 !!!
# Google AI Studio (https://aistudio.google.com/app/apikey) 에서 API 키를 발급받으세요.
API_KEY = "AIzaSyBD65dxtd4SvxIrxbu4Fnp2dtyFioHNPLs" # 본인의 API 키 입력

CSV_FILEPATH = '/Users/sondain/careerbee/cs_question.csv' # 질문 CSV 파일 경로 확인
OUTPUT_JSON_FILEPATH = '/Users/sondain/careerbee/cs_feedback_data.json' # 저장할 JSON 파일 경로
MODEL_NAME_FOR_ANSWER = "gemini-1.5-flash-latest" # 사용자 답변 생성 모델 (무료 티어 모델 권장)
MODEL_NAME_FOR_FEEDBACK = "gemini-1.5-flash-latest" # 피드백 생성 모델 (무료 티어 모델 권장)
REQUEST_DELAY_SECONDS = 2 # API 요청 간 지연 시간 (Rate Limit 방지)
TARGET_SAMPLE_COUNT = 1000 # 생성 및 출력할 샘플 개수 지정
NUM_ANSWERS_PER_QUESTION = 5 # 각 질문당 생성할 답변 개수

# --- Gemini API 설정 ---
try:
    genai.configure(api_key=API_KEY)
except Exception as e:
    print(f"API 키 설정 중 오류 발생: {e}")
    print("Google AI Studio에서 API 키를 발급받아 YOUR_API_KEY 부분을 교체해주세요.")
    exit() # API 키 설정 실패 시 종료

# --- 데이터 로드 ---
try:
    df = pd.read_csv(CSV_FILEPATH, encoding="utf-8")
    # 질문 목록을 섞어서 매번 다른 질문으로 테스트 가능 (선택 사항)
    # questions_list = df["문제"].sample(frac=1).tolist()
    questions_list = df["문제"].tolist()
    print(f"총 {len(questions_list)}개의 질문을 로드했습니다.")
    if len(questions_list) * NUM_ANSWERS_PER_QUESTION < TARGET_SAMPLE_COUNT:
        print(f"경고: 로드된 질문 개수({len(questions_list) * NUM_ANSWERS_PER_QUESTION})가 목표 샘플 개수({TARGET_SAMPLE_COUNT})보다 적습니다.")
        TARGET_SAMPLE_COUNT = len(questions_list) * NUM_ANSWERS_PER_QUESTION # 목표 개수를 질문 개수로 조정
except FileNotFoundError:
    print(f"오류: CSV 파일을 찾을 수 없습니다. 경로를 확인하세요: {CSV_FILEPATH}")
    exit()
except Exception as e:
    print(f"CSV 파일 로드 중 오류 발생: {e}")
    exit()


# --- 함수 정의 (이전 코드와 동일) ---
def generate_with_gemini(model_name: str, prompt: str, max_retries=3) -> str:
    """Gemini API를 호출하여 텍스트를 생성하는 함수 (재시도 로직 포함)"""
    model = genai.GenerativeModel(model_name)
    generation_config = genai.types.GenerationConfig(
        max_output_tokens=500, # 최대 출력 토큰 수 조정
        temperature=0.7, # 창의성 조절 (0.0 ~ 1.0)
    )
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    ]

    retries = 0
    while retries < max_retries:
        try:
            response = model.generate_content(
                prompt,
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            if response.parts:
                return response.text.strip()
            else:
                print(f"Warning: 모델로부터 빈 응답을 받았습니다. 프롬프트: {prompt[:100]}...")
                print(f"차단 이유: {response.prompt_feedback}")
                return ""
        except exceptions.ResourceExhausted as e: # Rate limit 에러 처리
            wait_time = REQUEST_DELAY_SECONDS * (2 ** retries) # 지수 백오프
            print(f"Rate limit 에러 발생. {wait_time:.1f}초 후 재시도합니다... (시도 {retries + 1}/{max_retries})")
            time.sleep(wait_time)
            retries += 1
        except exceptions.GoogleAPIError as e: # 기타 Google API 에러
             print(f"Gemini API 호출 중 오류 발생 (GoogleAPIError): {e}")
             print(f"프롬프트: {prompt[:100]}...")
             return "" # 오류 시 빈 문자열 반환
        except Exception as e: # 기타 예상치 못한 에러
            print(f"Gemini API 호출 중 예상치 못한 오류 발생: {e}")
            print(f"프롬프트: {prompt[:100]}...")
            return "" # 오류 시 빈 문자열 반환

    print(f"최대 재시도 횟수({max_retries}) 초과. 생성 실패.")
    return ""


def generate_user_answer_gemini(question: str) -> str:
    """(1) '질문'을 보고, 사용자가 '텍스트로 입력'했을 법한 답변을 생성하도록 Gemini API 호출"""
    prompt = f"""주어진 Computer Science 질문에 대한 사용자 답변을 생성해주세요.
    이 답변은 사용자가 웹사이트나 앱의 텍스트 입력 필드에 직접 작성하는 상황을 가정합니다.
    답변은 반드시 문어체로 작성되어야 하며, 구어체(말하는 듯한 말투, 예: "~했는데요", "~죠?")는 사용하지 않아야 합니다.
    답변의 길이는 400자로 제한하며, 최대 3문장으로 작성해주세요.
    답변의 완성도는 다양해도 좋습니다. 약간 부족하거나, 핵심만 간략하게 설명하거나, 때로는 약간의 오류가 있는 답변도 괜찮습니다.

질문: {question}
사용자 답변 예시:"""
    user_answer = generate_with_gemini(MODEL_NAME_FOR_ANSWER, prompt)
    return user_answer


def generate_feedback_gemini(question: str, user_answer: str) -> str:
    """(2) '질문 + 사용자 답변'을 보고, '피드백'을 생성하도록 Gemini API 호출"""
    prompt = f"""당신은 Computer Science 문제 출제자이며, 사용자가 입력한 답변에 대해 피드백을 해주는 역할입니다.
다음 질문과 사용자의 답변을 보고, 구체적인 피드백(칭찬할 점, 아쉬운 점, 보완하면 좋을 내용 등)을 한국어로 작성해주세요. 친절하게 설명하되, **피드백의 길이는 500자를 넘지 않도록 간결하고 요약하여 작성해주세요.**

질문: {question}
사용자 답변: {user_answer}

피드백:"""
    feedback = generate_with_gemini(MODEL_NAME_FOR_FEEDBACK, prompt)
    return feedback


# --- 메인 실행 로직 (샘플 생성 및 출력) ---
def main():
    print(f"--- {TARGET_SAMPLE_COUNT}개의 샘플 데이터 생성 시작 ---")
    generated_data= []
    generated_count = 0

    # 질문 리스트에서 순서대로 또는 무작위로 가져와서 생성
    for q_idx, question in enumerate(questions_list):
        if generated_count >= TARGET_SAMPLE_COUNT:
            print(f"\n목표 샘플 개수({TARGET_SAMPLE_COUNT}) 생성을 완료했습니다.")
            break # 목표 개수에 도달하면 루프 종료

        print(f"\n--- 샘플 {generated_count + 1}/{TARGET_SAMPLE_COUNT} 생성 시도 ---")
        print(f"[질문] {question}")

        # 1) 질문에 대한 "사용자 답변" 생성
        user_answer = generate_user_answer_gemini(question)
        if not user_answer: # 답변 생성 실패 시 다음 질문으로 넘어감
            print("  -> 사용자 답변 생성 실패. 다음 질문으로 넘어갑니다.")
            time.sleep(REQUEST_DELAY_SECONDS) # 실패 시에도 잠시 대기
            continue

        print(f"\n[생성된 사용자 답변]\n{user_answer}")
        time.sleep(REQUEST_DELAY_SECONDS) # API 호출 간 지연

        # 2) 생성된 "질문+사용자답변"으로부터 피드백 생성
        feedback = generate_feedback_gemini(question, user_answer)
        if not feedback: # 피드백 생성 실패 시 다음 질문으로 넘어감
            print("\n  -> 피드백 생성 실패. 다음 질문으로 넘어갑니다.")
            time.sleep(REQUEST_DELAY_SECONDS) # 실패 시에도 잠시 대기
            continue

        print(f"\n[생성된 피드백]\n{feedback}")
        
        generated_data.append({
            "질문": question,
            "사용자 답변": user_answer, 
            "피드백": feedback
        })
        generated_count += 1 # 성공적으로 생성된 경우 카운트 증가

        # 다음 요청 전 잠시 대기
        time.sleep(REQUEST_DELAY_SECONDS)
    
    # --- JSON 파일로 저장 ---
    try:
        with open(OUTPUT_JSON_FILEPATH, 'w', encoding='utf-8') as f:
            json.dump(generated_data, f, ensure_ascii=False, indent=4)
        print(f"\n--- {len(generated_data)}개의 샘플 데이터를 '{OUTPUT_JSON_FILEPATH}'에 저장했습니다. ---")
    except Exception as e:
        print(f"\n오류: JSON 파일 저장 중 오류 발생: {e}")

    if generated_count < TARGET_SAMPLE_COUNT:
        print(f"\n경고: 목표했던 {TARGET_SAMPLE_COUNT}개 중 {generated_count}개의 샘플만 생성되었습니다.")
    print("\n--- 데이터 생성 및 저장 종료 ---")


if __name__ == "__main__":
    main()