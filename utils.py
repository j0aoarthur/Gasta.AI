import dateparser
from datetime import datetime, timezone, timedelta
from dateutil.relativedelta import relativedelta

def parse_data_hora_inferida(data_hora_texto: str | None, current_time_utc: datetime) -> datetime:
    """
    Tenta parsear a string de data/hora inferida pelo LLM.
    Se for None ou não puder ser parseada, retorna o timestamp atual em UTC.
    """
    if not data_hora_texto:
        return current_time_utc

    try:
        dt_parsed = dateparser.parse(
            data_hora_texto,
            settings={
                'PREFER_DATES_FROM': 'past',
                'RETURN_AS_TIMEZONE_AWARE': False,
                'RELATIVE_BASE': current_time_utc
            }
        )

        if dt_parsed:
            return dt_parsed
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
        try:
            parsed_dt = dateparser.parse(texto_periodo, languages=['pt'], settings={'RELATIVE_BASE': data_referencia.replace(tzinfo=None)})
            if parsed_dt:
                inicio_periodo = parsed_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                fim_periodo = (inicio_periodo + relativedelta(months=1)) - timedelta(microseconds=1)
                if inicio_periodo.tzinfo is None:
                    inicio_periodo = inicio_periodo.replace(tzinfo=timezone.utc)
                if fim_periodo.tzinfo is None:
                    fim_periodo = fim_periodo.replace(tzinfo=timezone.utc)
        except Exception:
            pass

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