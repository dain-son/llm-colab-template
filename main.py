



from langchain_docling import DoclingLoader

FILE_PATH = "/Users/sondain/careerbee/이력서예시.pdf"

loader = DoclingLoader(file_path=FILE_PATH)

docs = loader.load()

for d in docs[:]:
    print(f"- {d.page_content=}")
