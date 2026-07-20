import json
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
    "e um resumo de 3 frases para o GEO. "
    "Responda SOMENTE em JSON válido, sem markdown, sem texto fora do JSON, "
    "seguindo exatamente este formato:\n"
    "{\n"
    '  "titulo": "string, até 60 caracteres",\n'
    '  "linha_fina": "string, até 140 caracteres",\n'
    '  "meta_descricao": "string para o Yoast SEO",\n'
    '  "palavra_chave": "string, a palavra-chave principal",\n'
    '  "tags": ["até 10 strings"],\n'
    '  "resumo_geo": ["frase 1", "frase 2", "frase 3"]\n'
    "}"
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
                    response_mime_type="application/json",
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


def contador_caracteres(texto: str, limite: int) -> str:
    """Retorna um texto de contagem colorido (verde/amarelo/vermelho)."""
    n = len(texto)
    if n <= limite:
        cor = "#188038"  # verde
    elif n <= limite * 1.1:
        cor = "#b06000"  # amarelo/laranja
    else:
        cor = "#c5221f"  # vermelho
    return f'<span style="color:{cor}; font-size:13px;">{n}/{limite} caracteres</span>'


def render_google_preview(titulo: str, url_exibida: str, meta_descricao: str):
    """Renderiza um card que imita o snippet de resultado do Google."""
    html = f"""
    <div style="
        font-family: Arial, sans-serif;
        border: 1px solid #dfe1e5;
        border-radius: 8px;
        padding: 16px 20px;
        max-width: 600px;
        background-color: #ffffff;
    ">
        <div style="color: #202124; font-size: 14px; margin-bottom: 3px;">
            {url_exibida}
        </div>
        <div style="color: #1a0dab; font-size: 20px; line-height: 1.3; margin-bottom: 3px;">
            {titulo}
        </div>
        <div style="color: #4d5156; font-size: 14px; line-height: 1.4;">
            {meta_descricao}
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------
news_text = st.text_area(
    "Cole o texto da notícia:",
    height=300,
    placeholder="Cole aqui o texto completo da matéria...",
)

url_site = st.text_input(
    "URL do site (opcional, só para o preview do Google):",
    value="www.seusite.com.br › noticia",
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

                try:
                    kit = json.loads(resposta.text)
                except json.JSONDecodeError:
                    st.warning(
                        "O modelo não devolveu um JSON válido desta vez. "
                        "Mostrando a resposta bruta abaixo."
                    )
                    st.markdown(resposta.text)
                    kit = None

                if kit:
                    st.success("Kit gerado com sucesso!")

                    # ---- Preview visual do Google ----
                    st.markdown("### 🔍 Preview no Google")
                    render_google_preview(
                        kit.get("titulo", ""),
                        url_site,
                        kit.get("meta_descricao", ""),
                    )
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(
                            "**Título:** " + contador_caracteres(kit.get("titulo", ""), 60),
                            unsafe_allow_html=True,
                        )
                    with col2:
                        st.markdown(
                            "**Metadescrição:** "
                            + contador_caracteres(kit.get("meta_descricao", ""), 160),
                            unsafe_allow_html=True,
                        )

                    st.divider()

                    # ---- Demais elementos do kit ----
                    st.markdown("### 📋 Kit completo")

                    st.markdown(
                        f"**Título** {contador_caracteres(kit.get('titulo', ''), 60)}",
                        unsafe_allow_html=True,
                    )
                    st.write(kit.get("titulo", ""))

                    st.markdown(
                        f"**Linha-fina** {contador_caracteres(kit.get('linha_fina', ''), 140)}",
                        unsafe_allow_html=True,
                    )
                    st.write(kit.get("linha_fina", ""))

                    st.markdown("**Metadescrição (Yoast SEO)**")
                    st.write(kit.get("meta_descricao", ""))

                    st.markdown("**Palavra-chave principal**")
                    st.write(kit.get("palavra_chave", ""))

                    st.markdown("**Tags**")
                    st.write(", ".join(kit.get("tags", [])))

                    st.markdown("**Resumo para o GEO**")
                    for frase in kit.get("resumo_geo", []):
                        st.markdown(f"- {frase}")

            except ServerError:
                st.error(
                    "O modelo continua sobrecarregado depois de várias tentativas. "
                    "Aguarde alguns minutos e tente novamente."
                )
            except Exception as e:
                st.error(f"Ocorreu um erro durante a comunicação com a API: {e}")
