import time

import streamlit as st
from google import genai
from google.genai import types
from google.genai.errors import ServerError

# ---------------------------------------------------------------------------
# Configuração da página
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Gerador de Kit SEO/GEO", page_icon="📰")

st.title("📰 Gerador de Kit SEO/GEO")
st.caption("Disciplina Inteligência Artificial e Automação nas Redações")

SYSTEM_INSTRUCTION = (
    "Aja como um editor de SEO experiente. A partir do texto fornecido, "
    "crie um título de até 60 caracteres, uma linha-fina de até 140 caracteres, "
    "uma metadescrição para o YoastSEO, a palavra-chave principal, até 10 tags "
    "separadas por vírgula e um resumo de 3 frases para o GEO."
)


# ---------------------------------------------------------------------------
# Cliente Gemini (chave lida dos Secrets do Streamlit — nunca do código)
# ---------------------------------------------------------------------------
@st.cache_resource
def carregar_cliente():
    chave = st.secrets.get("GEMINI_API_KEY")
    if not chave:
        st.error(
            "GEMINI_API_KEY não encontrada nos Secrets do Streamlit.\n\n"
            "No Streamlit Community Cloud: Settings → Secrets → adicione\n"
            'GEMINI_API_KEY = "sua_chave_aqui"'
        )
        st.stop()
    return genai.Client(api_key=chave)


def chamar_gemini_com_retry(client, news_text, max_tentativas=5):
    """Chama a API com nova tentativa automática em caso de sobrecarga (503)."""
    espera = 5  # segundos, dobra a cada tentativa

    for tentativa in range(1, max_tentativas + 1):
        try:
            return client.models.generate_content(
                # gemini-3.1-flash-lite: modelo GA (não-preview) da família
                # Gemini 3, otimizado para tarefas de alto volume e baixo
                # custo/latência. Mais estável que o alias "latest", que
                # pode apontar para versões em preview com menos capacidade
                # de servidores (mais 503).
                model="gemini-3.1-flash-lite",
                contents=news_text,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    temperature=0.3,
                ),
            )
        except ServerError:
            if tentativa == max_tentativas:
                raise
            st.info(
                f"Modelo sobrecarregado (tentativa {tentativa}/{max_tentativas}). "
                f"Aguardando {espera}s..."
            )
            time.sleep(espera)
            espera *= 2


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------
news_text = st.text_area(
    "Cole o texto da notícia:",
    height=300,
    placeholder="Cole aqui o texto completo da matéria...",
)

gerar = st.button("Gerar kit SEO/GEO", type="primary")

if gerar:
    if not news_text.strip():
        st.warning("Cole o texto de uma notícia antes de gerar o kit.")
    else:
        client = carregar_cliente()
        with st.spinner("Processando com o modelo Gemini..."):
            try:
                resposta = chamar_gemini_com_retry(client, news_text)
                st.success("Kit gerado com sucesso!")
                st.markdown("### Resultado")
                st.markdown(resposta.text)
            except ServerError:
                st.error(
                    "O modelo continua sobrecarregado depois de várias tentativas. "
                    "Aguarde alguns minutos e tente novamente."
                )
            except Exception as e:
                st.error(f"Ocorreu um erro durante a comunicação com a API: {e}")
