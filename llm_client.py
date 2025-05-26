
import os
import json
from datetime import datetime, timezone, timedelta

import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "gemini-1.5-flash-latest") # Modelo Gemini

if not GEMINI_API_KEY:
    raise ValueError("API Key do Gemini não configurada. Verifique seu arquivo .env.")

genai.configure(api_key=GEMINI_API_KEY)

generation_config_json = genai.GenerationConfig(response_mime_type="application/json")
generation_config_text = genai.GenerationConfig(response_mime_type="text/plain")

model_json = genai.GenerativeModel(LLM_MODEL_NAME, generation_config=generation_config_json)
model_text = genai.GenerativeModel(LLM_MODEL_NAME, generation_config=generation_config_text)

def get_financial_details_from_llm(text_message: str) -> dict | None:
    """
    Envia a mensagem para a API Gemini e tenta extrair detalhes financeiros.
    Inclui a lógica para interpretar a data/hora diretamente no LLM.
    Retorna um dicionário estruturado ou None em caso de falha.
    """
    current_utc_time_for_llm_context = datetime.now(timezone.utc)
    current_date_for_llm_context_str = current_utc_time_for_llm_context.strftime("%Y-%m-%d")
    current_utc_iso = current_utc_time_for_llm_context.isoformat()

    try:
        yesterday_utc_date = (current_utc_time_for_llm_context.date() - timedelta(days=1)).strftime('%Y-%m-%d')
    except Exception as e:
        print(f"Erro calculando data para exemplo (yesterday): {e}")
        yesterday_utc_date = "YYYY-MM-DD"

    try:
         current_month_day_5_utc_date = current_utc_time_for_llm_context.replace(day=5).strftime('%Y-%m-%d')
    except ValueError:
         print("Erro calculando data para exemplo (dia 5 do mês).")
         current_month_day_5_utc_date = "YYYY-MM-05"
    except Exception as e:
        print(f"Erro inesperado calculando data para exemplo (dia 5): {e}")
        current_month_day_5_utc_date = "YYYY-MM-05"


    prompt = f"""
    Você é um assistente especialista em finanças pessoais e processamento de linguagem natural.
    Sua tarefa é analisar a mensagem do usuário e extrair informações financeiras de forma estruturada, incluindo a data e hora inferidas.
    A mensagem pode ser informal, conter erros de digitação ou ter a ordem das palavras livre.

    Retorne a informação como um objeto JSON com as seguintes chaves:
    - "tipo": string, deve ser "entrada" ou "saída".
    - "valor": float, o valor numérico da transação (ex: 15.0, 50.0, 100.75). Deve ser sempre positivo.
    - "categoria": string, uma categoria para a transação (ex: "alimentação", "transporte", "lazer", "moradia", "saúde", "educação", "salário", "presente", "investimentos", "compras", "contas", "outros"). Se não conseguir inferir, use "outros".
    - "descricao": string, uma descrição concisa da transação (ex: "mc donalds", "gasolina", "poker com amigos", "presente de aniversário").
    - "data_hora_inferida": string ou null. Se o usuário mencionar explicitamente uma data ou hora (ex: "hoje de manhã", "ontem 10pm", "25/12/2023", "dia 5 às 14h", "amanhã 8 da manhã"), interprete essa menção baseando-se na data e hora atuais UTC ({current_utc_iso}) e retorne a data e hora inferidas no formato ISO 8601 (YYYY-MM-DDTHH:MM:SS). Use o ano atual se apenas dia e mês forem dados e fizer sentido no contexto. Se apenas a data for dada, use 12:00:00 como hora padrão. Se apenas a hora for dada, use a data atual UTC. Se nenhuma data/hora específica for mencionada, retorne null.

    Contexto da data atual (UTC) para sua referência ao interpretar "hoje", "ontem", etc.: {current_date_for_llm_context_str}

    Exemplos de extração (siga este formato RIGOROSAMENTE):

    1. Mensagem do usuário: "Paguei 15 reais no Mc Donalds"
       Data atual (UTC) para contexto: {current_date_for_llm_context_str}
       JSON Output:
       {{
         "tipo": "saída",
         "valor": 15.0,
         "categoria": "alimentação",
         "descricao": "Mc Donalds",
         "data_hora_inferida": null
       }}

    2. Mensagem do usuário: "Recebi 50 reais no poker com amigos ontem à noite"
       Data atual (UTC) para contexto: {current_utc_iso}
       JSON Output (assumindo ontem foi {yesterday_utc_date} e "noite" é 20:00:00):
       {{
         "tipo": "entrada",
         "valor": 50.0,
         "categoria": "lazer",
         "descricao": "poker com amigos",
         "data_hora_inferida": "{yesterday_utc_date}T20:00:00"
       }}

    3. Mensagem do usuário: "Gastei R$ 33,50 em um lanche na padaria"
       Data atual (UTC) para contexto: {current_date_for_llm_context_str}
       JSON Output:
       {{
         "tipo": "saída",
         "valor": 33.50,
         "categoria": "alimentação",
         "descricao": "lanche na padaria",
         "data_hora_inferida": null
       }}

    4. Mensagem do usuário: "Paguei a conta de luz do dia 5 às 14h"
       Data atual (UTC) para contexto: {current_utc_iso}
       JSON Output (assumindo o dia 5 do mês atual):
       {{
         "tipo": "saída",
         "valor": 100.0,
         "categoria": "contas",
         "descricao": "conta de luz",
         "data_hora_inferida": "{current_month_day_5_utc_date}T14:00:00"
       }}
    
    Agora, analise a seguinte mensagem do usuário:
    Mensagem do usuário: "{text_message}"
    Data atual (UTC) para contexto: {current_utc_iso}
    JSON Output:
    """


    try:
        response = model_json.generate_content(prompt)
        cleaned_response_text = response.text.strip().removeprefix("```json").removesuffix("```").strip()
        parsed_json = json.loads(cleaned_response_text)
        
        # Validação básica do formato ISO 8601 se data_hora_inferida não for null
        if parsed_json.get("data_hora_inferida") is not None:
            try:
                datetime.fromisoformat(parsed_json["data_hora_inferida"])
            except ValueError:
                print(f"AVISO: LLM retornou data_hora_inferida em formato inválido: {parsed_json.get('data_hora_inferida')}. Definindo como null.")
                parsed_json["data_hora_inferida"] = None

        return parsed_json
    except json.JSONDecodeError as e:
        print(f"Erro ao decodificar JSON do Gemini (detalhes financeiros): {e}")
        response_text = response.text if 'response' in locals() and hasattr(response, 'text') else 'N/A'
        print(f"Resposta recebida: {response_text}")
        return None
    except Exception as e:
        print(f"Erro na chamada da API Gemini (detalhes financeiros): {e}")
        return None

def get_query_params_from_natural_language(user_query: str) -> dict | None:
    """
    Envia a pergunta do usuário para a API Gemini para extrair parâmetros de consulta,
    incluindo a interpretação do período diretamente no LLM.
    """

    current_utc_time_for_llm_context = datetime.now(timezone.utc)
    current_date_for_llm_context_str = current_utc_time_for_llm_context.strftime("%Y-%m-%d")
    current_utc_iso = current_utc_time_for_llm_context.isoformat()

    try:
        april_of_current_year_start_date = current_utc_time_for_llm_context.replace(month=4, day=1).strftime('%Y-%m-%d')
        try:
             next_month = current_utc_time_for_llm_context.replace(month=4).date().replace(day=28) + timedelta(days=4)
             april_of_current_year_end_date = (next_month - timedelta(days=next_month.day)).strftime('%Y-%m-%d')
        except ValueError: 
             print("Erro calculando fim do mês para exemplo (Abril).")
             april_of_current_year_end_date = "YYYY-04-30" 
        except Exception as e:
             print(f"Erro inesperado calculando fim do mês para exemplo (Abril): {e}")
             april_of_current_year_end_date = "YYYY-04-30"



        last_year_start_date = current_utc_time_for_llm_context.replace(year=current_utc_time_for_llm_context.year - 1, month=1, day=1).strftime('%Y-%m-%d')
        last_year_end_date = current_utc_time_for_llm_context.replace(year=current_utc_time_for_llm_context.year - 1, month=12, day=31).strftime('%Y-%m-%d')

    except Exception as e:
        print(f"Erro calculando datas para exemplos de query: {e}")
        april_of_current_year_start_date = "YYYY-04-01"
        april_of_current_year_end_date = "YYYY-04-30"
        last_year_start_date = "YYYY-01-01"
        last_year_end_date = "YYYY-12-31"


    prompt = f"""
    Você é um especialista em analisar perguntas de usuários sobre dados financeiros e traduzi-las em parâmetros de consulta estruturados.
    Analise a pergunta do usuário e extraia os seguintes parâmetros em formato JSON.
    Se um parâmetro não for mencionado ou não puder ser inferido, use `null` para seu valor ou omita-o (exceto para data_inicio e data_fim que devem ser null se não houver período).

    Parâmetros a extrair:
    - "operacao": string - Qual é o objetivo principal? Valores possíveis: "soma_valor", "listar_transacoes", "contar_transacoes", "media_valor". Se não especificado, assuma "listar_transacoes".
    - "tipo_transacao": string - "entrada", "saída", ou null se não especificado (significando ambos os tipos).
    - "categorias": array de strings - Lista de categorias mencionadas (ex: ["alimentação", "transporte"]). Null se não houver menção explícita.
    - "descricao_contem": array de strings - Lista de palavras-chave que devem estar na descrição da transação (ex: ["uber", "cinema", "ifood"]). Null se não houver.
    - "data_inicio": string ou null. Se o usuário especificar um período (ex: "este mês", "ano passado", "últimos 7 dias", "de 10/01 a 15/01"), interprete o *início* desse período com base na data e hora atuais UTC ({current_utc_iso}) e retorne no formato ISO 8601 (YYYY-MM-DDTHH:MM:SS). Para início de períodos, use 00:00:00 como hora padrão. Retorne null se nenhum período for especificado.
    - "data_fim": string ou null. Se o usuário especificar um período, interprete o *fim* desse período com base na data e hora atuais UTC ({current_utc_iso}) e retorne no formato ISO 8601 (YYYY-MM-DDTHH:MM:SS). Para fim de períodos, use 23:59:59 como hora padrão. Retorne null se nenhum período for especificado.
    - "ordenar_por": string - Campo para ordenação (ex: "data_hora", "valor"). Default: "data_hora".
    - "ordem": string - "asc" para ascendente, "desc" para descendente. Default: "desc" para listas, irrelevante para somas/contagens.
    - "limite_resultados": integer - Número máximo de resultados a serem retornados (ex: para "top 5", "ultimos 10"). Null se não especificado.

    Contexto da data atual (UTC) para sua referência ao interpretar "este mês", "mês passado", etc.: {current_date_for_llm_context_str}

    Exemplos de Pergunta e Output (siga este formato RIGOROSAMENTE):

    1. Pergunta: "quanto gastei com uber esse ultimo mês 04"
       Data atual (UTC): {current_utc_iso}
       JSON Output (assumindo último mês 04 foi Abril do ano atual):
       {{
           "operacao": "soma_valor",
           "tipo_transacao": "saída",
           "categorias": null,
           "descricao_contem": ["uber"],
           "data_inicio": "{april_of_current_year_start_date}T00:00:00",
           "data_fim": "{april_of_current_year_end_date}T23:59:59"
       }}

    2. Pergunta: "Minhas 5 maiores receitas no ano passado"
       Data atual (UTC): {current_utc_iso}
       JSON Output (assumindo ano passado foi {current_utc_time_for_llm_context.year - 1}):
       {{
           "operacao": "listar_transacoes",
           "tipo_transacao": "entrada",
           "categorias": null,
           "descricao_contem": null,
           "data_inicio": "{last_year_start_date}T00:00:00",
           "data_fim": "{last_year_end_date}T23:59:59",
           "ordenar_por": "valor",
           "ordem": "desc",
           "limite_resultados": 5
       }}

    3. Pergunta: "entradas de 10/01/2024 a 15/01/2024"
       Data atual (UTC): {current_utc_iso}
       JSON Output:
       {{
           "operacao": "listar_transacoes",
           "tipo_transacao": "entrada",
           "categorias": null,
           "descricao_contem": null,
           "data_inicio": "2024-01-10T00:00:00",
           "data_fim": "2024-01-15T23:59:59"
       }}

    4. Pergunta: "total gasto em alimentação"
       Data atual (UTC): {current_utc_iso}
       JSON Output:
       {{
           "operacao": "soma_valor",
           "tipo_transacao": "saída",
           "categorias": ["alimentação"],
           "descricao_contem": null,
           "data_inicio": null,
           "data_fim": null
       }}

    Agora, analise a seguinte pergunta do usuário:
    Pergunta: "{user_query}"
    Data atual (UTC) para contexto: {current_utc_iso}
    JSON Output:
    """


    try:
        response = model_json.generate_content(prompt)
        cleaned_response_text = response.text.strip().removeprefix("```json").removesuffix("```").strip()
        parsed_json = json.loads(cleaned_response_text)

        # Validação básica do formato ISO 8601 para data_inicio e data_fim
        for key in ["data_inicio", "data_fim"]:
            if key in parsed_json and parsed_json.get(key) is not None:
                try:
                    datetime.fromisoformat(parsed_json[key])
                except ValueError:
                    print(f"AVISO: LLM retornou '{key}' em formato inválido: {parsed_json.get(key)}. Definindo como null.")
                    parsed_json[key] = None


        return parsed_json
    except json.JSONDecodeError as e:
        print(f"Erro ao decodificar JSON do Gemini (parâmetros de query): {e}")
        response_text = response.text if 'response' in locals() and hasattr(response, 'text') else 'N/A'
        print(f"Resposta recebida: {response_text}")
        return None
    except Exception as e:
        print(f"Erro na chamada da API Gemini (parâmetros de query): {e}")
        return None

def generate_conversational_response(original_query: str, data_summary: str) -> str:
    """
    Gera uma resposta conversacional baseada na pergunta original e nos dados sumarizados.
    """
    prompt = f"""
    Você é um assistente financeiro gente boa e que adora ajudar!
    O usuário te perguntou: "{original_query}"

    E você descobriu o seguinte nos dados dele: "{data_summary}"

    Agora, crie uma resposta bem natural e amigável para ele, como se estivesse conversando.
    Se não encontrou nada, diga isso de forma leve. Não invente dados!

    Exemplos de como você poderia responder:

    1. Pergunta: "quanto gastei com uber mês passado?"
       Dados: "A soma total encontrada foi de R$ 75,50."
       Resposta: "Olha só, no mês passado seus gastos com Uber foram de R$ 75,50. Anotado! 😉"

    2. Pergunta: "gastos com cinema este mês"
       Dados: "Nenhuma transação encontrada para esses critérios."
       Resposta: "Dei uma olhada aqui e parece que você não teve gastos com cinema este mês. Que tal um filminho no próximo? 🍿"

    3. Pergunta: "o que comi em maio?"
       Dados: "Encontrei 2 transação(ões). 1. Saída de R$ 20,00 em 'alimentação' (Lanche) no dia 01/05. 2. Saída de R$ 30,00 em 'alimentação' (Café) no dia 02/05."
       Resposta: "Em maio, vi que você mandou ver num lanche de R$ 20,00 no dia 01 e um café de R$ 30,00 no dia 02. Bom apetite! 😋"
    
    4. Pergunta: "qual o total de entradas este mes?"
       Dados: "A soma total encontrada foi de R$ 0,00." (Implica que não houve entradas)
       Resposta: "Pelo que vi, este mês ainda não pintou nenhuma entrada por aqui. Bora fazer acontecer! 💪"


    Agora, crie a resposta para a situação atual:
    """
    try:
        response = model_text.generate_content(prompt) # Usando o modelo para texto puro
        return response.text.strip()
    except Exception as e:
        print(f"Erro na chamada da API Gemini (resposta conversacional): {e}")
        return "Puxa, não consegui pensar numa resposta legal agora. Mas os dados são: " + data_summary


if __name__ == '__main__':
    print("--- Teste Detalhes Financeiros (LLM) ---")
    test_msg = "Comprei um livro por R$35,50 na terça-feira passada"
    details = get_financial_details_from_llm(test_msg)
    if details:  print(json.dumps(details, indent=2, ensure_ascii=False))
    else: print("Falha ao extrair detalhes financeiros.")

    print("\n--- Teste Parâmetros de Query (LLM) ---")
    test_q = "quanto gastei com ifood este mês?"
    params = get_query_params_from_natural_language(test_q)
    if params: print(json.dumps(params, indent=2, ensure_ascii=False))
    else: print("Falha ao extrair parâmetros de query.")

    print("\n--- Teste Resposta Conversacional (LLM) ---")
    query_orig = "quanto gastei com ifood este mês?"
    data_simples = "A soma total encontrada foi de R$ 125,70."
    convo_resp = generate_conversational_response(query_orig, data_simples)
    print(f"Resposta Gerada: {convo_resp}")

    query_orig_2 = "viagem para a praia em janeiro"
    data_simples_2 = "Nenhuma transação encontrada para esses critérios."
    convo_resp_2 = generate_conversational_response(query_orig_2, data_simples_2)
    print(f"Resposta Gerada 2: {convo_resp_2}")