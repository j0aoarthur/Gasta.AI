import os
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, Integer, REAL, DateTime, Text, func, desc, asc
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime, timedelta, timezone
import calendar

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///transacoes.db")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Transacao(Base):
    __tablename__ = "transacoes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    usuario_id = Column(Text, nullable=False)
    tipo = Column(Text, nullable=False)
    valor = Column(REAL, nullable=False)
    categoria = Column(Text, nullable=True)
    descricao = Column(Text, nullable=True)
    data_hora = Column(DateTime, default=datetime.utcnow, nullable=False)


def init_db():
    Base.metadata.create_all(bind=engine)

def add_transaction(db_session, usuario_id: str, tipo: str, valor: float, categoria: str, descricao: str, data_hora: datetime):
    """
    Adiciona uma nova transação ao banco de dados.
    Garante que data_hora é um objeto datetime com timezone (UTC).
    """
    if data_hora.tzinfo is None:
        data_hora_utc = data_hora.replace(tzinfo=timezone.utc)
    else:
        data_hora_utc = data_hora.astimezone(timezone.utc)

    try:
        transacao_db = Transacao(
            usuario_id=str(usuario_id),
            tipo=tipo,
            valor=valor,
            categoria=categoria,
            descricao=descricao,
            data_hora=data_hora_utc
        )
        db_session.add(transacao_db)
        db_session.commit()
        db_session.refresh(transacao_db)
        return transacao_db
    except Exception as e:
        db_session.rollback()
        print(f"Erro ao adicionar transação ao banco: {e}")
        raise
    finally:
        db_session.close()

# Funções para os comandos extras (opcional)
def get_saldo(db_session, usuario_id: str):
    try:
        entradas = db_session.query(func.sum(Transacao.valor)).filter(Transacao.usuario_id == str(usuario_id), Transacao.tipo == "entrada").scalar() or 0.0
        saidas = db_session.query(func.sum(Transacao.valor)).filter(Transacao.usuario_id == str(usuario_id), Transacao.tipo == "saída").scalar() or 0.0
        return entradas - saidas
    except Exception as e:
        print(f"Erro ao obter saldo do banco: {e}")
        raise
    finally:
        db_session.close()


def get_transacoes_por_tipo(db_session, usuario_id: str, tipo_transacao: str, limit: int = 10):
    try:
        transacoes = db_session.query(Transacao).filter(
            Transacao.usuario_id == str(usuario_id),
            Transacao.tipo == tipo_transacao
        ).order_by(Transacao.data_hora.desc()).limit(limit).all()
        return transacoes
    except Exception as e:
        print(f"Erro ao obter transações por tipo do banco: {e}")
        raise
    finally:
        db_session.close()

def query_dynamic_transactions(db_session, usuario_id: str, params: dict):
    """
    Executa uma consulta dinâmica baseada nos parâmetros extraídos pelo LLM.
    params: dicionário contendo 'operacao', 'tipo_transacao', 'categorias', etc.
    data_inicio e data_fim são esperados como strings ISO 8601 ou null.
    """
    query = db_session.query(Transacao).filter(Transacao.usuario_id == str(usuario_id))

    if params.get("tipo_transacao"):
        query = query.filter(Transacao.tipo == params["tipo_transacao"])

    if params.get("categorias"):
        categorias_list = params["categorias"]
        if isinstance(categorias_list, list) and categorias_list:
            query = query.filter(Transacao.categoria.in_(categorias_list))

    if params.get("descricao_contem"):
        desc_list = params["descricao_contem"]
        if isinstance(desc_list, list) and desc_list:
            for palavra in desc_list:
                query = query.filter(Transacao.descricao.ilike(f"%{palavra}%"))

    # --- Processamento de período - AGORA PARSANDO STRINGS ISO 8601 DO LLM ---
    data_inicio_dt = None
    if params.get("data_inicio") and isinstance(params["data_inicio"], str) and params["data_inicio"].strip():
        try:
            data_inicio_dt = datetime.fromisoformat(params["data_inicio"])
            if data_inicio_dt.tzinfo is None:
                data_inicio_dt = data_inicio_dt.replace(tzinfo=timezone.utc)
            else:
                 data_inicio_dt = data_inicio_dt.astimezone(timezone.utc)

        except ValueError as e:
            print(f"AVISO: Erro ao parsear data_inicio ISO 8601 '{params['data_inicio']}': {e}. Ignorando filtro de data de início.")
            data_inicio_dt = None
        except Exception as e:
             print(f"AVISO: Erro inesperado ao parsear data_inicio '{params['data_inicio']}': {e}. Ignorando filtro de data de início.")
             data_inicio_dt = None


    data_fim_dt = None
    if params.get("data_fim") and isinstance(params["data_fim"], str) and params["data_fim"].strip():
        try:
            data_fim_dt = datetime.fromisoformat(params["data_fim"])
            if data_fim_dt.tzinfo is None:
                data_fim_dt = data_fim_dt.replace(tzinfo=timezone.utc)
            else:
                 data_fim_dt = data_fim_dt.astimezone(timezone.utc)
        except ValueError as e:
            print(f"AVISO: Erro ao parsear data_fim ISO 8601 '{params['data_fim']}': {e}. Ignorando filtro de data de fim.")
            data_fim_dt = None
        except Exception as e:
             print(f"AVISO: Erro inesperado ao parsear data_fim '{params['data_fim']}': {e}. Ignorando filtro de data de fim.")
             data_fim_dt = None

    if data_inicio_dt:
        query = query.filter(Transacao.data_hora >= data_inicio_dt)
    if data_fim_dt:
        query = query.filter(Transacao.data_hora <= data_fim_dt)

    operacao = params.get("operacao", "listar_transacoes")

    if operacao == "soma_valor":
        query_sum = query.with_entities(func.sum(Transacao.valor).label("total"))
        result = query_sum.scalar() or 0.0
        db_session.close()
        return {"total": result}
    elif operacao == "contar_transacoes":
        query_count = query.with_entities(func.count(Transacao.id).label("contagem"))
        result = query_count.scalar() or 0
        db_session.close()
        return {"contagem": result}
    elif operacao == "media_valor":
        query_avg = query.with_entities(func.avg(Transacao.valor).label("media"))
        result = query_avg.scalar() or 0.0
        db_session.close()
        return {"media": result}
    else: 
        order_by_field = params.get("ordenar_por", "data_hora")
        order_direction = params.get("ordem", "desc")

        if hasattr(Transacao, order_by_field):
            field_to_order = getattr(Transacao, order_by_field)
            if order_direction == "asc":
                query = query.order_by(asc(field_to_order))
            else:
                query = query.order_by(desc(field_to_order))
        else:
            print(f"AVISO: Campo de ordenação inválido '{order_by_field}'. Usando 'data_hora' descendente.")
            query = query.order_by(desc(Transacao.data_hora))


        if params.get("limite_resultados"):
            try:
                limite = int(params["limite_resultados"])
                if limite > 0:
                     query = query.limit(limite)
                else:
                    print(f"AVISO: Limite de resultados inválido '{params['limite_resultados']}'. Ignorando limite.")
            except ValueError:
                print(f"AVISO: Limite de resultados não numérico '{params['limite_resultados']}'. Ignorando limite.")
                pass
            except Exception as e:
                print(f"AVISO: Erro inesperado ao processar limite de resultados '{params.get('limite_resultados')}': {e}. Ignorando limite.")


        transacoes = query.all()
        db_session.close() 
        return {"transacoes": transacoes}


if __name__ == "__main__":
    # Para criar o banco de dados e a tabela se eles não existiremx
    print("Inicializando o banco de dados...")
    init_db()
    print("Banco de dados inicializado.")

    # --- Exemplos de como usar (para teste local) ---
    session = SessionLocal()
    try:
        add_transaction(session, "test_user_stats", "saída", 40.0, "alimentação", "Restaurante X", datetime.now(timezone.utc))
        add_transaction(session, "test_user_stats", "entrada", 1500.0, "salário", "Salário do mês", datetime.now(timezone.utc))
        add_transaction(session, "test_user_stats", "saída", 15.0, "transporte", "Uber para casa", datetime.now(timezone.utc) - timedelta(days=1))
        add_transaction(session, "test_user_stats", "saída", 60.0, "lazer", "Cinema", datetime.now(timezone.utc).replace(day=15, hour=10, minute=0, second=0))

        print("Transações de teste para estatísticas adicionadas.")

        # Exemplo de consulta: Total gasto em alimentação este mês
        now_utc = datetime.now(timezone.utc)
        start_of_month_utc = now_utc.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_day_of_month = calendar.monthrange(now_utc.year, now_utc.month)[1]
        end_of_month_utc = now_utc.replace(day=last_day_of_month, hour=23, minute=59, second=59, microsecond=999999)


        params_exemplo_soma_mes = {
            "operacao": "soma_valor",
            "tipo_transacao": "saída",
            "categorias": ["alimentação"],
            "data_inicio": start_of_month_utc.isoformat(),
            "data_fim": end_of_month_utc.isoformat()
        }

        print(f"\nConsultando total gasto em alimentação este mês para test_user_stats...")
        results_soma_mes = query_dynamic_transactions(SessionLocal(), "test_user_stats", params_exemplo_soma_mes)
        print(f"Resultado: {results_soma_mes}")


        # Exemplo de consulta: Listar todas as transações de saída
        params_exemplo_lista_saida = {
            "operacao": "listar_transacoes",
            "tipo_transacao": "saída",
            "ordenar_por": "data_hora",
            "ordem": "desc",
            "limite_resultados": 10
        }
        print(f"\nConsultando últimas 10 transações de saída para test_user_stats...")
        results_lista_saida = query_dynamic_transactions(SessionLocal(), "test_user_stats", params_exemplo_lista_saida)
        print(f"Resultado (primeiras 3): {results_lista_saida.get('transacoes', [])[:3]}")

        # Exemplo de consulta: Contar transações do dia 15 deste mês
        day_15_utc = now_utc.replace(day=15)
        start_of_day_15_utc = day_15_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day_15_utc = day_15_utc.replace(hour=23, minute=59, second=59, microsecond=999999)

        params_exemplo_contar_dia15 = {
            "operacao": "contar_transacoes",
            "data_inicio": start_of_day_15_utc.isoformat(),
            "data_fim": end_of_day_15_utc.isoformat()
        }
        print(f"\nConsultando quantas transações houveram no dia 15 deste mês para test_user_stats...")
        results_contar_dia15 = query_dynamic_transactions(SessionLocal(), "test_user_stats", params_exemplo_contar_dia15)
        print(f"Resultado: {results_contar_dia15}")


    except Exception as e:
        print(f"Erro durante os testes locais: {e}")
    finally:
         pass