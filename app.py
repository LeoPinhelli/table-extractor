"""Interface opcional: streamlit run app.py."""

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from table_extractor.core import ExtractionError, ValidationProfile, build_document, load_json
from table_extractor.demo import demo_image, demo_payload
from table_extractor.exporters import document_json, table_csv, table_excel
from table_extractor.provider import OpenAIExtractor, prepare_image

load_dotenv(Path.cwd() / ".env", override=False)
st.set_page_config(page_title="Table Extractor", page_icon="📋", layout="wide")
st.title("Table Extractor")
st.write("Transforme uma imagem de tabela em JSON, CSV e Excel, com verificações de consistência.")

with st.sidebar:
    st.header("Extração")
    mode = st.radio("Modo", ["Demonstração offline", "Extrair minha imagem"])
    model = st.text_input("Modelo", value=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
    key = st.text_input("Chave OpenAI (opcional se configurada no ambiente)", type="password")
    st.caption("A chave é usada apenas na sessão e não é incluída nos downloads.")
    profile_file = st.file_uploader("Perfil de validação (JSON, opcional)", type=["json"])

upload = None
if mode == "Demonstração offline":
    st.info("Dados sintéticos e resposta predefinida. Este modo não chama nem avalia um modelo de IA.")
    st.image(demo_image(), caption="Exemplo sintético", width=760)
else:
    upload = st.file_uploader("Imagem da tabela", type=["png", "jpg", "jpeg", "webp"])
    st.caption(
        "Uma tabela por imagem, até 15 MiB e 20 megapixels. Recorte a tabela para facilitar a leitura."
    )
    st.info("Ao extrair, a imagem será enviada à API da OpenAI e poderá gerar cobrança na sua conta.")

if st.button("Executar demonstração" if mode == "Demonstração offline" else "Extrair tabela", type="primary"):
    try:
        profile = (
            ValidationProfile.from_dict(load_json(profile_file.getvalue().decode("utf-8")))
            if profile_file
            else None
        )
        if mode == "Demonstração offline":
            image = prepare_image(demo_image())
            document = build_document(
                demo_payload(), image, model="offline-fixture", mode="demo", profile=profile
            )
        else:
            if upload is None:
                raise ExtractionError("Selecione uma imagem para continuar.")
            image = prepare_image(upload.getvalue())
            try:
                timeout = int(os.getenv("OPENAI_TIMEOUT", "120"))
            except ValueError:
                raise ExtractionError("OPENAI_TIMEOUT deve ser um inteiro positivo.") from None
            with st.spinner("Lendo a tabela e verificando o resultado…"):
                payload, metadata = OpenAIExtractor(
                    key or os.getenv("OPENAI_API_KEY", ""), model, timeout
                ).extract(image)
                document = build_document(payload, image, profile=profile, **metadata)
        # Sem cache compartilhado entre usuarios e sem gravacao de arquivos no servidor.
        st.session_state["extraction_result"] = (document, image)
    except (ExtractionError, UnicodeError, OSError) as error:
        st.session_state.pop("extraction_result", None)
        st.error(str(error))

if "extraction_result" in st.session_state:
    document, image = st.session_state["extraction_result"]
    st.subheader("Último resultado")
    st.caption(f"Modo: {document['metadata']['mode']} · {document['metadata']['created_at']}")
    left, right = st.columns(2)
    with left:
        st.image(image, caption="Imagem correspondente ao resultado")
    with right:
        if document["status"] == "needs_review":
            st.warning("Revisão necessária. Os arquivos incluem os avisos encontrados.")
        else:
            st.success("Verificações aprovadas. Confira a transcrição antes de usar os dados.")
        for issue in document["validation_issues"]:
            st.write(f"• {issue}")
        table = document["table"]
        # Mantem linhas incompletas e cabecalhos duplicados visiveis para revisao.
        st.table([table["columns"], *table["rows"]])
    for column, label, content, filename, mime in zip(
        st.columns(3),
        ["Baixar JSON", "Baixar CSV", "Baixar Excel"],
        [document_json(document), table_csv(document), table_excel(document)],
        ["result.json", "table.csv", "table.xlsx"],
        ["application/json", "text/csv", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"],
    ):
        column.download_button(label, content, filename, mime=mime)
    st.caption(
        "O CSV neutraliza células que poderiam ser interpretadas como fórmulas. O JSON preserva o texto original."
    )
