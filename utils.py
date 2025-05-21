# telegram_financial_bot/utils.py
import dateparser
from datetime import datetime, timezone, timedelta
from dateutil.relativedelta import relativedelta # pip install python-dateutil

def parse_data_hora_inferida(data_hora_texto: str | None, current_time_utc: datetime) -> datetime:
    """
    Tenta parsear a string de data/hora inferida pelo LLM.
    Se for None ou não puder ser parseada, retorna o timestamp atual em UTC.
    """
    if not data_hora_texto:
        return current_time_utc

    try:
        # dateparser pode retornar um objeto datetime com ou sem timezone.
        # Para consistência, vamos garantir que seja timezone-aware (UTC) ou naive (representando UTC).
        # Settings para dar preferência a datas no passado e considerar o fuso horário de Brasília
        # como referência se a string for ambígua, mas converter para UTC no final.
        # ATENÇÃO: dateparser é poderoso mas pode ser complexo. Ajuste settings conforme necessidade.
        # 'RELATIVE_BASE' ajuda a interpretar "hoje", "ontem" corretamente.
        # Para o exemplo, vamos assumir que se não houver timezone explícito na string,
        # interpretamos como se fosse no contexto local e depois convertemos para UTC.
        # Porém, para simplicidade e consistência no BD, é melhor que o LLM não tente adivinhar fusos
        # e Python sempre normalize para UTC.

        # Se a string não tiver informação de fuso, dateparser a tratará como naive.
        # Vamos assumir que essa data naive está no contexto do usuário (ex: São Paulo)
        # e depois converter para UTC para armazenamento.
        # Se o LLM fornecer algo como "2024-05-09 08:00:00 BRT", dateparser pode lidar com isso.
        # Por simplicidade, vamos apenas parsear. Se o resultado for naive, assumimos UTC.
        # Se tiver timezone, convertemos para UTC.

        dt_parsed = dateparser.parse(
            data_hora_texto,
            settings={
                'PREFER_DATES_FROM': 'past',
                'RETURN_AS_TIMEZONE_AWARE': False, # Começamos com naive
                'RELATIVE_BASE': current_time_utc #  Para "hoje", "ontem"
            }
        )

        if dt_parsed:
            # Se for naive, consideramos que já é UTC ou que o LLM deu um horário "absoluto"
            # Se quiséssemos tratar como local e converter:
            # from_zone = tz.gettz('America/Sao_Paulo') # Exemplo
            # dt_parsed = dt_parsed.replace(tzinfo=from_zone)
            # return dt_parsed.astimezone(timezone.utc)
            return dt_parsed # Para o LLM, esperamos que ele dê um timestamp completo se possível
        else:
            return current_time_utc
    except Exception:
        return current_time_utc

def format_currency(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def parse_periodo_descricao(texto_periodo: str | None, data_referencia: datetime) -> tuple[datetime | None, datetime | None]:
    """
    Tenta converter uma descrição textual de período em datas de início e fim (UTC).
    Retorna (None, None) se não conseguir parsear.
    `data_referencia` deve ser timezone-aware (UTC).
    """
    if not texto_periodo:
        return None, None

    texto_periodo = texto_periodo.lower()
    inicio_periodo = None
    fim_periodo = None

    # Garantir que data_referencia está em UTC e é naive para alguns cálculos
    # ou usar relativedelta que lida bem com tz-aware.
    # Para simplicidade, vamos assumir que data_referencia já é o "agora" em UTC.

    # Casos simples primeiro
    if "hoje" in texto_periodo:
        inicio_periodo = data_referencia.replace(hour=0, minute=0, second=0, microsecond=0)
        fim_periodo = data_referencia.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif "ontem" in texto_periodo:
        ontem = data_referencia - timedelta(days=1)
        inicio_periodo = ontem.replace(hour=0, minute=0, second=0, microsecond=0)
        fim_periodo = ontem.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif "este mês" in texto_periodo or "mês atual" in texto_periodo:
        inicio_periodo = data_referencia.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        fim_periodo = (inicio_periodo + relativedelta(months=1)) - timedelta(microseconds=1)
    elif "mês passado" in texto_periodo:
        primeiro_dia_mes_atual = data_referencia.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        fim_periodo = primeiro_dia_mes_atual - timedelta(microseconds=1)
        inicio_periodo = fim_periodo.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif "este ano" in texto_periodo or "ano atual" in texto_periodo:
        inicio_periodo = data_referencia.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        fim_periodo = (inicio_periodo + relativedelta(years=1)) - timedelta(microseconds=1)
    elif "ano passado" in texto_periodo:
        primeiro_dia_ano_atual = data_referencia.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        fim_periodo = primeiro_dia_ano_atual - timedelta(microseconds=1)
        inicio_periodo = fim_periodo.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        # Tentativa mais genérica com dateparser para frases como "mês 04", "abril", "mês 04 de 2023"
        # Isso é complexo porque dateparser pode retornar uma data específica, não um intervalo.
        # Ex: "mês 04" -> dateparser pode dar 01/04/data_referencia.ano
        # Ex: "ultimo mês 04" -> pode significar abril do ano corrente ou passado.
        # Precisamos de uma lógica mais robusta ou um prompt mais específico para o LLM
        # pedir datas de início e fim se possível.

        # Simplificação: se o LLM passar algo como "mês 04 [do ano YYYY]",
        # tentamos parsear com dateparser e assumimos o mês inteiro.
        try:
            # Tenta identificar se é um mês específico
            parsed_dt = dateparser.parse(texto_periodo, languages=['pt'], settings={'RELATIVE_BASE': data_referencia.replace(tzinfo=None)}) # dateparser prefere naive
            if parsed_dt:
                # Se conseguiu parsear para uma data, consideramos o mês inteiro dessa data
                inicio_periodo = parsed_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                fim_periodo = (inicio_periodo + relativedelta(months=1)) - timedelta(microseconds=1)
                # Converter para UTC se for naive
                if inicio_periodo.tzinfo is None:
                    inicio_periodo = inicio_periodo.replace(tzinfo=timezone.utc)
                if fim_periodo.tzinfo is None:
                    fim_periodo = fim_periodo.replace(tzinfo=timezone.utc)
        except Exception:
            pass # Falha no parse, inicio_periodo e fim_periodo continuam None

    # Se foram parseados, garantir que são timezone-aware UTC
    if inicio_periodo and inicio_periodo.tzinfo is None:
        inicio_periodo = inicio_periodo.replace(tzinfo=timezone.utc)
    if fim_periodo and fim_periodo.tzinfo is None:
        fim_periodo = fim_periodo.replace(tzinfo=timezone.utc)
        
    return inicio_periodo, fim_periodo


if __name__ == '__main__':

    now_utc = datetime.now(timezone.utc)
    print(f"Agora (UTC): {now_utc}")
    print(parse_data_hora_inferida("hoje de manhã", now_utc))
    print(parse_data_hora_inferida("ontem às 10 da noite", now_utc))
    print(parse_data_hora_inferida("25 de dezembro de 2023", now_utc))
    print(parse_data_hora_inferida(None, now_utc))
    print(parse_data_hora_inferida("dia 5 do mês passado às 15h", now_utc))

    print("\n--- Testes de Período ---")
    now_utc = datetime.now(timezone.utc)
    print(f"Referência: {now_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    tests_periodo = [
        "hoje", "ontem", "este mês", "mês passado", "este ano", "ano passado",
        "mês 04", "abril", "mês 03 de 2024", "mês de fevereiro"
    ]
    for t in tests_periodo:
        start, end = parse_periodo_descricao(t, now_utc)
        if start and end:
            print(f"'{t}': {start.strftime('%Y-%m-%d %H:%M')} a {end.strftime('%Y-%m-%d %H:%M')}")
        else:
            print(f"'{t}': Não foi possível parsear.")

if __name__ == '__main__':
    now_utc = datetime.now(timezone.utc)
    print(f"Agora (UTC): {now_utc}")
    print(parse_data_hora_inferida("hoje de manhã", now_utc))
    print(parse_data_hora_inferida("ontem às 10 da noite", now_utc))
    print(parse_data_hora_inferida("25 de dezembro de 2023", now_utc))
    print(parse_data_hora_inferida(None, now_utc))
    print(parse_data_hora_inferida("dia 5 do mês passado às 15h", now_utc))