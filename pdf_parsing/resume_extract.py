from langchain_community.llms import HuggingFacePipeline
from langchain_community.document_loaders import PyMuPDFLoader
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
import fitz


# fitz를 이용해 PDF → 텍스트 추출
doc = fitz.open("코딩몬스터-표준이력서.pdf")
text = "\n".join([page.get_text() for page in doc])

# 모델 불러오기 (로그인 필요 시 Hugging Face 토큰 포함)
model_name = "mistralai/Mistral-7B-Instruct-v0.3"

tokenizer = AutoTokenizer.from_pretrained(model_name, use_auth_token=True)
model = AutoModelForCausalLM.from_pretrained(
    model_name, device_map="auto", torch_dtype="auto", use_auth_token=True
)

# HF 파이프라인 생성
mistral_pipeline = pipeline(
    "text-generation",
    model=model,
    tokenizer=tokenizer,
    max_new_tokens=512,
    do_sample=False,
)


# LangChain의 HuggingFacePipeline로 래핑
llm = HuggingFacePipeline(pipeline=mistral_pipeline)


# PromptTemplate 구성
template = """
다음은 이력서 텍스트야. 이 텍스트를 바탕으로 다음 정보를 JSON 형식으로 추출해줘:

- 이메일 주소 (없으면 null)
- 프로젝트 개수
- 자격증 개수
- 총 경력 기간 (개월 단위, 없으면 0)

아래 이력서를 분석해줘:
-------------------------
{text}
-------------------------
"""

prompt = PromptTemplate(input_variables=["text"], template=template)
chain = LLMChain(llm=llm, prompt=prompt)

# 실행
result = chain.run(text=text)
print("🔍 추출 결과:")
print(result)
