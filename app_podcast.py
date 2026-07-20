import json
import time

import streamlit as st
from google import genai
from google.genai import types
from google.genai.errors import ServerError

# ---------------------------------------------------------------------------
# Configuração da página
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Roteirizador de Podcast", page_icon="🎙️")

st.title("🎙️ Roteirizador de Podcast")
st.caption("Disciplina Inteligência Artificial e Automação nas Redações")

PALAVRAS_POR_MINUTO = 150  # ritmo médio de locução em português


def montar_system_instruction(duracao_alvo_min: float) -> str:
    palavras_alvo = int(duracao_alvo_min * PALAVRAS_POR_MINUTO)
    return (
        "Aja como um roteirista experiente de podcasts jornalísticos e rádio "
        "digital. A partir do texto de uma notícia, transforme-o em um roteiro "
        "sonoro pronto para narração em áudio — não é um resumo, é uma "
        "adaptação para o ouvido: frases mais curtas, ritmo falado, transições "
        "claras entre blocos. "
        f"RESTRIÇÃO IMPORTANTE DE TAMANHO: o roteiro completo (soma de todos os "
        f"campos 'texto', mais o gancho de abertura e o encerramento) deve ter "
        f"aproximadamente {palavras_alvo} palavras no total, para caber em "
        f"cerca de {duracao_alvo_min:.0f} minuto(s) de locução a um ritmo de "
        f"{PALAVRAS_POR_MINUTO} palavras por minuto. Não ultrapasse esse limite "
        "de forma significativa. "
        "Responda SOMENTE em JSON válido, sem markdown, sem texto fora do JSON, "
        "seguindo exatamente este formato:\n"
        "{\n"
        '  "titulo_episodio": "string, curto e atrativo",\n'
        '  "gancho_abertura": "string, os primeiros 10-15 segundos falados, '
        'pensados para prender atenção imediata",\n'
        '  "roteiro": [\n'
        "    {\n"
        '      "secao": "string, ex: Abertura / Contexto / Desenvolvimento / Encerramento",\n'
        '      "texto": "string, o texto a ser narrado nesta seção",\n'
        '      "indicacao_tom": "string curta, ex: \'tom sério, pausa de 2s '
        'antes desta frase\' ou \'ritmo mais leve aqui\'"\n'
        "    }\n"
        "  ],\n"
        '  "cta_encerramento": "string, uma chamada final para o próximo '
        'episódio ou para a audiência comentar/seguir"\n'
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


def chamar_gemini_com_retry(client, news_text, duracao_alvo_min, max_tentativas=5):
    """Chama a API com nova tentativa automática em caso de sobrecarga (503)."""
    espera = 5  # segundos, dobra a cada tentativa
    system_instruction = montar_system_instruction(duracao_alvo_min)

    for tentativa in range(1, max_tentativas + 1):
        try:
            return client.models.generate_content(
                # gemini-3.1-flash-lite: modelo GA (não-preview) da família
                # Gemini 3, otimizado para tarefas de alto volume e baixo
                # custo/latência.
                model="gemini-3.1-flash-lite",
                contents=news_text,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.4,
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


def calcular_duracao_real(kit: dict) -> float:
    """Calcula a duração estimada em minutos a partir da contagem real de palavras."""
    textos = [kit.get("gancho_abertura", ""), kit.get("cta_encerramento", "")]
    textos += [bloco.get("texto", "") for bloco in kit.get("roteiro", [])]
    total_palavras = sum(len(t.split()) for t in textos)
    return total_palavras / PALAVRAS_POR_MINUTO


def render_roteiro(roteiro: list):
    """Renderiza cada seção do roteiro como um cartão estilo 'script'."""
    for bloco in roteiro:
        secao = bloco.get("secao", "")
        texto = bloco.get("texto", "")
        tom = bloco.get("indicacao_tom", "")

        html = f"""
        <div style="
            border-left: 4px solid #6200ee;
            background-color: #f7f5fb;
            padding: 12px 16px;
            margin-bottom: 12px;
            border-radius: 6px;
        ">
            <div style="font-size: 12px; font-weight: bold; color: #6200ee; text-transform: uppercase;">
                {secao}
            </div>
            <div style="font-size: 16px; color: #202124; margin: 6px 0;">
                {texto}
            </div>
            <div style="font-size: 12px; color: #5f6368; font-style: italic;">
                🎚️ {tom}
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

duracao_alvo = st.select_slider(
    "Duração-alvo do episódio:",
    options=[1, 2, 3, 4, 5],
    value=2,
    format_func=lambda x: f"{x} minuto{'s' if x > 1 else ''}",
)

gerar = st.button("Gerar roteiro de podcast", type="primary")

if gerar:
    if not news_text.strip():
        st.warning("Cole o texto de uma notícia antes de gerar o roteiro.")
    else:
        client = carregar_cliente()
        with st.spinner("Adaptando o texto para áudio..."):
            try:
                resposta = chamar_gemini_com_retry(client, news_text, duracao_alvo)

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
                    st.success("Roteiro gerado com sucesso!")

                    duracao_real = calcular_duracao_real(kit)

                    st.markdown(f"## {kit.get('titulo_episodio', '')}")
                    if duracao_real > duracao_alvo * 1.3:
                        st.caption(
                            f"⏱️ Duração calculada: ~{duracao_real:.1f} min "
                            f"(alvo era {duracao_alvo} min — o modelo passou do "
                            "combinado; considere gerar de novo ou editar o texto)"
                        )
                    else:
                        st.caption(
                            f"⏱️ Duração calculada: ~{duracao_real:.1f} min "
                            f"(alvo: {duracao_alvo} min)"
                        )

                    st.markdown("### 🎯 Gancho de abertura")
                    st.info(kit.get("gancho_abertura", ""))

                    st.markdown("### 📜 Roteiro")
                    render_roteiro(kit.get("roteiro", []))

                    st.markdown("### 👋 Encerramento")
                    st.success(kit.get("cta_encerramento", ""))

            except ServerError:
                st.error(
                    "O modelo continua sobrecarregado depois de várias tentativas. "
                    "Aguarde alguns minutos e tente novamente."
                )
            except Exception as e:
                st.error(f"Ocorreu um erro durante a comunicação com a API: {e}")
