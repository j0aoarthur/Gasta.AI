import os
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv
from datetime import datetime, timezone

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup 
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler

from llm_client import get_financial_details_from_llm, get_query_params_from_natural_language, generate_conversational_response
from database import SessionLocal, init_db, add_transaction, get_saldo, get_transacoes_por_tipo, query_dynamic_transactions
from utils import format_currency

ASK_STAT_QUERY, PROCESS_STAT_QUERY = range(2)

TRANSACTION_CALLBACK_PREFIX = "trxconfirm"

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

init_db()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    start_message = (
        f"Olá, {user.first_name}! 👋 Seja muito bem-vindo(a) ao seu Bot Financeiro Gasta AI.\n\n"
        "Estou aqui pra te ajudar a organizar suas finanças de um jeito simples e prático. "
        "Você pode me contar sobre suas transações usando linguagem natural, como se estivesse falando com alguém. Por exemplo:\n\n"
        "💸 'Gastei 25 reais no cinema ontem'\n"
        "🤑 'Recebi 1000 de salário'\n"
        "🚗 'Despesa de 50 com Uber hoje'\n\n"
        "Eu vou entender o tipo da transação (entrada ou saída), o valor, a categoria e a data, tudo automaticamente.\n\n"
        "📋 *Comandos que você pode usar:*\n"
        "/saldo - Mostra seu saldo atual\n"
        "/gastos - Lista suas últimas despesas\n"
        "/entradas - Lista suas últimas receitas\n"
        "/estatisticas - Faça perguntas mais detalhadas sobre suas finanças\n"
        "/ajuda - Relembra os comandos e como usar o bot\n\n"
        "Quando quiser, é só me mandar uma transação ou usar um dos comandos acima. Vamos juntos cuidar bem do seu dinheiro! 💰"
    )   
    await update.message.reply_text(start_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message_text = update.message.text
    user_id = str(update.effective_user.id)
    chat_id = update.effective_chat.id
    original_message_id = update.message.message_id

    logger.info(f"Recebida mensagem de {user_id} (Msg ID: {original_message_id}): '{message_text}'")
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    extracted_data = get_financial_details_from_llm(message_text)

    if not extracted_data:
        await update.message.reply_text(
            "Não foi possível processar sua mensagem. Por favor, tente descrever a transação de outra forma. Exemplo: 'Gastei 50 em alimentação'."
        )
        return

    try:
        tipo = extracted_data.get("tipo")
        valor_str = extracted_data.get("valor")
        categoria = extracted_data.get("categoria", "outros")
        descricao = extracted_data.get("descricao", "N/A")
        data_hora_inferida_str = extracted_data.get("data_hora_inferida")

        if not tipo or tipo not in ["entrada", "saída"]:
            await update.message.reply_text(f"Não consegui identificar se a transação é uma entrada ou saída. 🤔\nDados recebidos: {extracted_data}")
            return
        if valor_str is None:
            await update.message.reply_text(f"O valor da transação não foi compreendido. Por favor, informe o valor. 😕\nDados: {extracted_data}")
            return
        
        try:
            valor = float(valor_str)
            if valor <= 0:
                raise ValueError("O valor da transação deve ser positivo.")
        except ValueError as e:
            await update.message.reply_text(f"O valor informado '{valor_str}' não é válido. Por favor, verifique. ({e})")
            return

        data_hora_transacao = None
        if data_hora_inferida_str:
            try:
                data_hora_transacao = datetime.fromisoformat(data_hora_inferida_str)
                if data_hora_transacao.tzinfo is None:
                    data_hora_transacao = data_hora_transacao.replace(tzinfo=timezone.utc)
                else:
                     data_hora_transacao = data_hora_transacao.astimezone(timezone.utc)

            except ValueError as e:
                logger.error(f"Erro ao parsear data_hora_inferida_str '{data_hora_inferida_str}': {e}")
        
        if data_hora_transacao is None:
             data_hora_transacao = datetime.now(timezone.utc)

        data_hora_local_display = None
        try:
            from zoneinfo import ZoneInfo
            try:
                sao_paulo_tz = ZoneInfo("America/Sao_Paulo")
                data_hora_local_display = data_hora_transacao.astimezone(sao_paulo_tz).strftime("%d/%m/%Y às %H:%M")
            except Exception:
                 logger.warning("zoneinfo.ZoneInfo não disponível ou timezone inválida, usando UTC para exibição na confirmação.")
                 data_hora_local_display = data_hora_transacao.strftime("%d/%m/%Y às %H:%M (UTC)")
        except ImportError:
            logger.warning("Módulo 'zoneinfo' não encontrado, usando UTC para exibição na confirmação.")
            data_hora_local_display = data_hora_transacao.strftime("%d/%m/%Y às %H:%M (UTC)")


        confirmation_message_text = (
            f"Por favor, confirme os detalhes da transação: 🤔\n\n"
            f"Tipo: **{tipo.capitalize()}**\n"
            f"Valor: **{format_currency(valor)}**\n"
            f"Categoria: **{categoria.capitalize()}** ({descricao})\n"
            f"Data/Hora: {data_hora_local_display}"
        )

        stored_data_key = f"{TRANSACTION_CALLBACK_PREFIX}_data_{original_message_id}"
        context.user_data.pop(stored_data_key, None) 

        context.user_data[stored_data_key] = {
            "user_id": user_id,
            "tipo": tipo,
            "valor": valor,
            "categoria": categoria,
            "descricao": descricao,
            "data_hora": data_hora_transacao
        }
        logger.info(f"Dados da transação armazenados temporariamente para confirmação (key: {stored_data_key})")

        keyboard = [
            [
                InlineKeyboardButton("✅ Salvar", callback_data=f"{TRANSACTION_CALLBACK_PREFIX}_save_{original_message_id}"),
                InlineKeyboardButton("❌ Tentar Novamente", callback_data=f"{TRANSACTION_CALLBACK_PREFIX}_retry_{original_message_id}"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            confirmation_message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown',
            reply_to_message_id=original_message_id
        )


    except Exception as e:
        logger.error(f"Erro ao preparar confirmação da transação: {e}", exc_info=True)
        await update.message.reply_text(f"Ocorreu um erro interno ao processar sua transação. Por favor, tente novamente mais tarde: {str(e)}")
    finally:
        pass

async def handle_transaction_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Processa o callback dos botões de confirmação da transação."""
    query = update.callback_query
    await query.answer()

    callback_data = query.data
    user_id = str(query.from_user.id)
    chat_id = query.message.chat_id 
    confirmation_message_id = query.message.message_id


    logger.info(f"Callback de confirmação recebido de {user_id}: {callback_data}")

    parts = callback_data.split('_')

    if len(parts) != 3 or parts[0] != TRANSACTION_CALLBACK_PREFIX or parts[1] not in ['save', 'retry']:
        logger.error(f"Callback data inesperado ou formato inválido: {callback_data}")
        try:
            await context.bot.send_message(chat_id=chat_id, text="Erro ao processar a confirmação. Formato do callback data inválido.")
        except Exception as e_send:
             logger.error(f"Erro ao enviar mensagem de erro para callback data inválido: {e_send}")
        return

    action = parts[1]
    try:
        original_message_id = int(parts[2])
    except ValueError:
         logger.error(f"Callback data inválido: ID da mensagem original não é um número: {callback_data}")
         try:
             await context.bot.send_message(chat_id=chat_id, text="Erro ao processar a confirmação. ID da mensagem original inválido.")
         except Exception as e_send:
              logger.error(f"Erro ao enviar mensagem de erro para callback data com ID inválido: {e_send}")
         return

    stored_data_key = f"{TRANSACTION_CALLBACK_PREFIX}_data_{original_message_id}"
    transaction_data = context.user_data.pop(stored_data_key, None)


    if transaction_data is None:
        logger.warning(f"Dados da transação não encontrados para a chave {stored_data_key}. Possivelmente expirou ou bot reiniciou.")

        try:
             await query.edit_message_text(
                 text="Esta confirmação expirou. Por favor, envie a transação novamente.",
                 reply_markup=None
             )
        except Exception as e:
             logger.error(f"Erro ao editar mensagem de confirmação expirada: {e}")

             await context.bot.send_message(chat_id=chat_id, text="Esta confirmação expirou. Por favor, envie a transação novamente.")
        return


    tipo = transaction_data["tipo"]
    valor = transaction_data["valor"]
    categoria = transaction_data["categoria"]
    descricao = transaction_data["descricao"]
    data_hora = transaction_data["data_hora"]

    if action == "save":

        db_session = SessionLocal()
        try:
            add_transaction(
                db_session=db_session,
                usuario_id=user_id,
                tipo=tipo,
                valor=valor,
                categoria=categoria,
                descricao=descricao,
                data_hora=data_hora
            )

            try:
                data_hora_local_display = None
                try:
                    from zoneinfo import ZoneInfo
                    try:
                        sao_paulo_tz = ZoneInfo("America/Sao_Paulo")
                        data_hora_local_display = data_hora.astimezone(sao_paulo_tz).strftime("%d/%m/%Y às %H:%M")
                    except Exception:
                         data_hora_local_display = data_hora.strftime("%d/%m/%Y às %H:%M (UTC)")
                except ImportError:
                     data_hora_local_display = data_hora.strftime("%d/%m/%Y às %H:%M (UTC)")


                await query.edit_message_text(
                    text=(
                        f"✅ Transação Salva! ✅\n\n"
                        f"Tipo: {tipo.capitalize()}\n"
                        f"Valor: {format_currency(valor)}\n"
                        f"Categoria: {categoria.capitalize()} ({descricao})\n"
                        f"Data/Hora: {data_hora_local_display}"
                    ),
                    parse_mode='Markdown',
                    reply_markup=None
                )
                logger.info(f"Transação salva para usuário {user_id}.")
            except Exception as e:
                 logger.error(f"Erro ao editar mensagem de confirmação salva: {e}")
                 await context.bot.send_message(chat_id=chat_id, text="✅ Transação Salva!")

        except Exception as e:
            logger.error(f"Erro ao salvar transação no DB para {user_id}: {e}", exc_info=True)
            try:
                 await query.edit_message_text(
                     text=f"❌ Ocorreu um erro ao tentar salvar a transação: {str(e)}\nPor favor, tente registrar novamente.",
                     reply_markup=None
                 )
            except Exception as e_edit:
                 logger.error(f"Erro ao editar mensagem de erro ao salvar: {e_edit}")
                 await context.bot.send_message(chat_id=chat_id, text=f"❌ Ocorreu um erro ao tentar salvar a transação: {str(e)}")

        finally:
            if db_session.is_active:
                db_session.close()

    elif action == "retry":
        try:
            await query.edit_message_text(
                text="❌ Transação Cancelada. Por favor, descreva a transação novamente para tentar registrar.",
                reply_markup=None
            )
            logger.info(f"Transação cancelada pelo usuário {user_id}.")
        except Exception as e:
             logger.error(f"Erro ao editar mensagem de confirmação retry: {e}")
             await context.bot.send_message(chat_id=chat_id, text="❌ Transação Cancelada. Por favor, descreva a transação novamente.")


async def saldo_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.effective_user.id)
    db_session = SessionLocal()
    try:
        saldo_atual = get_saldo(db_session, user_id)
        await update.message.reply_text(f"Seu saldo atual é: **{format_currency(saldo_atual)}**", parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Erro ao buscar saldo para {user_id}: {e}")
        await update.message.reply_text("Não foi possível consultar seu saldo no momento. Por favor, tente novamente mais tarde.")

async def listar_transacoes(update: Update, context: ContextTypes.DEFAULT_TYPE, tipo_transacao: str) -> None:
    user_id = str(update.effective_user.id)
    db_session = SessionLocal()
    try:
        transacoes = get_transacoes_por_tipo(db_session, user_id, tipo_transacao, limit=5)

        tipo_str_plural = "transações"
        emoji = "🧐"
        if tipo_transacao == "saída":
            tipo_str_plural = "despesas recentes"
            emoji = "💸"
        elif tipo_transacao == "entrada":
            tipo_str_plural = "receitas recentes"
            emoji = "🤑"

        if not transacoes:
            await update.message.reply_text(f"Nenhuma {tipo_str_plural} encontrada para seu usuário. {emoji}")
            return

        resposta = f"Suas últimas {len(transacoes)} {tipo_str_plural}:\n\n"

        for t in transacoes:
            try:
                from zoneinfo import ZoneInfo
                try:
                    sao_paulo_tz = ZoneInfo("America/Sao_Paulo")
                    data_hora_local_display = t.data_hora.astimezone(sao_paulo_tz).strftime("%d/%m às %H:%M")
                except Exception:
                    logger.warning("zoneinfo.ZoneInfo não disponível ou timezone inválida para exibição de lista, usando UTC.")
                    data_hora_local_display = t.data_hora.strftime("%d/%m às %H:%M (UTC)")
            except ImportError:
                 logger.warning("Módulo 'zoneinfo' não encontrado para exibição de lista, usando UTC.")
                 data_hora_local_display = t.data_hora.strftime("%d/%m às %H:%M (UTC)")

            resposta += f"- {t.categoria.capitalize()}: {t.descricao} - {format_currency(t.valor)} - {data_hora_local_display}\n"

        await update.message.reply_text(resposta)

    except Exception as e:
        logger.error(f"Erro ao listar {tipo_transacao}s para {user_id}: {e}")
        await update.message.reply_text(f"Não foi possível listar suas {tipo_str_plural} no momento.")
    finally:
        pass


async def gastos_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await listar_transacoes(update, context, "saída")

async def entradas_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await listar_transacoes(update, context, "entrada")

async def estatisticas_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Você pode me perguntar sobre as suas entradas e gastos de forma bem natural! Aqui vão alguns exemplos do que você pode escrever:\n\n"
        " - Quanto eu ganhei nos últimos 30 dias?\n"
        " - Me mostra meus gastos com comida em março\n\n"
        "Se quiser sair da consulta a qualquer momento, utilize /cancelar_estatisticas."
    )
    return PROCESS_STAT_QUERY

async def handle_stat_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_query = update.message.text
    user_id = str(update.effective_user.id)
    chat_id = update.effective_chat.id
    
    logger.info(f"Recebida query de estatísticas de {user_id}: '{user_query}'")
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    params_from_llm = get_query_params_from_natural_language(user_query)

    if not params_from_llm:
        await update.message.reply_text(
            "Não foi possível interpretar sua solicitação de estatística. Por favor, reformule sua pergunta ou utilize /cancelar_estatisticas."
        )
        return PROCESS_STAT_QUERY 

    db_session = SessionLocal()
    data_summary_for_llm = "Nenhuma informação encontrada."
    try:
        results = query_dynamic_transactions(db_session, user_id, params_from_llm)
        
        operacao = params_from_llm.get("operacao", "listar_transacoes")

        if operacao == "soma_valor":
            total = results.get('total', 0.0)
            data_summary_for_llm = f"A soma total encontrada foi de {format_currency(total)}."
            if total == 0.0:
                 if params_from_llm.get("tipo_transacao") == "saída" or "gastei" in user_query.lower() or "despesa" in user_query.lower():
                      data_summary_for_llm = "Não foram encontrados gastos para os critérios informados."
                 elif params_from_llm.get("tipo_transacao") == "entrada" or "recebi" in user_query.lower() or "receita" in user_query.lower():
                      data_summary_for_llm = "Não foram encontradas entradas para os critérios informados."
                 else:
                      data_summary_for_llm = "Nenhuma transação com valor foi encontrada para os critérios informados."


        elif operacao == "contar_transacoes":
            contagem = results.get('contagem', 0)
            data_summary_for_llm = f"Foram encontradas {contagem} transações."
            if contagem == 0:
                data_summary_for_llm = "Nenhuma transação encontrada para os critérios informados."

        elif operacao == "media_valor":
            media = results.get('media', 0.0)
            data_summary_for_llm = f"A média de valor para as transações encontradas é de {format_currency(media)}."
            if media == 0.0:
                data_summary_for_llm = "Não foi possível calcular uma média, pois não há transações com valor para os critérios informados."
        
        elif operacao == "listar_transacoes":
            transacoes = results.get("transacoes", [])
            if not transacoes:
                data_summary_for_llm = "Nenhuma transação encontrada para os critérios informados."
            else:
                data_summary_for_llm = f"Encontrei {len(transacoes)} transação(ões). "
                preview_limit = 3 
                for i, t in enumerate(transacoes[:preview_limit]):
                    try:
                        from zoneinfo import ZoneInfo
                        try:
                            sao_paulo_tz = ZoneInfo("America/Sao_Paulo")
                            data_hora_local_display = t.data_hora.astimezone(sao_paulo_tz).strftime("%d/%m")
                        except Exception:
                            data_hora_local_display = t.data_hora.strftime("%d/%m (UTC)")
                    except ImportError:
                         data_hora_local_display = t.data_hora.strftime("%d/%m (UTC)")


                    data_summary_for_llm += f"{i+1}. {t.tipo.capitalize()} de {format_currency(t.valor)} em '{t.categoria}': {t.descricao} ({data_hora_local_display}). "
                if len(transacoes) > preview_limit:
                    data_summary_for_llm += f"E mais {len(transacoes) - preview_limit} outras."
        
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        conversational_reply = generate_conversational_response(user_query, data_summary_for_llm)
        await update.message.reply_text(conversational_reply)

    except Exception as e:
        logger.error(f"Erro ao executar consulta dinâmica ou gerar resposta: {e}", exc_info=True)
        await update.message.reply_text("Ocorreu um erro ao processar sua solicitação de estatística. Por favor, tente novamente mais tarde.")
    finally:
        if db_session.is_active:
            db_session.close()
    
    return ConversationHandler.END

async def cancelar_estatisticas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancela a conversa de estatísticas."""
    await update.message.reply_text("Consulta de estatísticas cancelada.")
    return ConversationHandler.END


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Loga os erros causados por Updates."""
    logger.error(f"Update {update} causou erro {context.error}", exc_info=context.error)
    if isinstance(update, Update) and update.message:
        try:
            await update.message.reply_text("Ocorreu um erro interno. A equipe de desenvolvimento foi notificada. Por favor, tente novamente mais tarde.")
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem de erro para o usuário: {e}")


def main() -> None:
    """Inicia o bot."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("Token do Telegram não configurado. Por favor, verifique o arquivo .env.")
        return
    if not os.getenv("GEMINI_API_KEY"):
        logger.error("API Key do Gemini não configurada. Por favor, verifique o arquivo .env.")
        return

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()


    stats_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("estatisticas", estatisticas_command)],
        states={
            PROCESS_STAT_QUERY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_stat_query)],
        },
        fallbacks=[CommandHandler("cancelar_estatisticas", cancelar_estatisticas)],
    )
    application.add_handler(stats_conv_handler)

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.add_handler(CallbackQueryHandler(handle_transaction_confirmation, pattern=f"^{TRANSACTION_CALLBACK_PREFIX}_(save|retry)_\\d+$"))

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("ajuda", help_command))
    application.add_handler(CommandHandler("saldo", saldo_command))
    application.add_handler(CommandHandler("gastos", gastos_command))
    application.add_handler(CommandHandler("entradas", entradas_command))

    application.add_error_handler(error_handler)

    logger.info("Bot iniciado com sucesso e pronto para receber comandos.")
    application.run_polling()

if __name__ == "__main__":
    main()