import streamlit as st
import os
import gspread
import psutil
import telebot
import time as t
from telebot import types
import datetime
from tokens import production_mode as tokens
from tokens import gc_service_account as gs_credit_nails
import random

st.write("running")
token = tokens["bot_tg_token"]
bot = telebot.TeleBot(token)
group_id = tokens["group_tg_id"]
gc = gspread.service_account_from_dict(gs_credit_nails)
sh = gc.open(tokens["google_table_name"])

extended_menu_keys = ["Приход",
                      "Расход",
                      "Приход на счет",
                      "Расход со счета",
                      "Фонд клуба",
                      "Мой подотчет",
                      "Подотчет членов клуба",
                      "Выдать в подотчет",
                      "Принять в подотчет",
                      "Списание подотчета",
                      "Добавить члена клуба",
                      "Передать должность казначея",
                      "Подотчетный пулемет"]

base_menu_keys = ["Приход",
                  "Расход",
                  "Фонд клуба",
                  "Мой подотчет",
                  "Подотчет членов клуба",
                  "Выдать в подотчет"]


def how_much():
    process = psutil.Process()
    memory_usage = process.memory_info().rss
    memory_usage_mb = memory_usage / (1024 * 1024)
    return f"Использование оперативной памяти: {memory_usage_mb} МБ"


def load_user_ids():
    worksheet = sh.worksheet("Сочлены")
    tg_ids = [elem for elem in worksheet.col_values(2) if elem != ""][1::]
    numbers = [elem for elem in worksheet.col_values(3) if elem != ""][1::]
    is_bot_admin = [elem for elem in worksheet.col_values(4) if elem != ""][1::]
    names = [elem for elem in worksheet.col_values(5) if elem != ""][1::]
    user_list = {int(tg_id): {"number": number, "name": name, "bot_admin": int(bot_admin)}
                 for tg_id, number, bot_admin, name in zip(tg_ids, numbers, is_bot_admin, names)}
    return user_list


def restruct(data):
    return {value["name"]: {"gt_number": value["number"], "tg_id": key, "bot_admin": value["bot_admin"]} for key, value
            in data.items()}


def can_see_extended_menu(data):
    lebowski_name = who_is_lebowski()
    name_can_see = {key: ((key == lebowski_name) or (value["bot_admin"] == 1)) for key, value in data.items()}
    return {data[key]["tg_id"]: main_menu() if value else common_menu() for key, value in name_can_see.items()}


def load_receipts_types():
    worksheet = sh.worksheet("Типы")
    receipts = [elem for elem in worksheet.col_values(1) if elem != ""][1::]
    return receipts


def load_expenses_types():
    worksheet = sh.worksheet("Типы")
    expenses = [elem for elem in worksheet.col_values(2) if elem != ""][1::]
    return expenses


def make_menu(buttons, backtrack=True):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for button in buttons:
        markup.add(types.KeyboardButton(button))
    if backtrack:
        markup.add(types.KeyboardButton("Назад"))
        markup.add(types.KeyboardButton("Отмена"))
    return markup


def main_menu():
    return make_menu(extended_menu_keys, backtrack=False)


def common_menu():
    return make_menu(base_menu_keys, backtrack=False)


def cancel_menu():
    return make_menu([])


def yes_no_menu():
    return make_menu(("Да", "Нет"))


def request_money():
    worksheet = sh.worksheet("Казна")
    data = worksheet.get_all_values()
    strings = [x[0] + " " + x[1] for x in data]
    msg_text = "{}\n{} р.\n{} р.\n{} р.\n{} р.".format(
        strings[0], strings[1], strings[2], strings[3], strings[4])
    return msg_text


def who_is_lebowski():
    worksheet = sh.worksheet("Казна")
    this_guy = worksheet.cell(1, 2).value
    return this_guy


def delete_transaction_from_table(transaction_id):
    if "M" in transaction_id:
        worksheet_name = "Сочлены"
    elif "R" in transaction_id:
        worksheet_name = "Приходы"
    elif "E" in transaction_id:
        worksheet_name = "Расходы"
    elif "C" in transaction_id:
        worksheet_name = "Подотчеты"
    elif "G" in transaction_id:
        worksheet_name = "Подотчеты"
    else:
        worksheet_name = "Не распознан ID операции"
    worksheet = sh.worksheet(worksheet_name)
    cell = worksheet.find(transaction_id)
    row = cell.row
    worksheet.delete_rows(row)


def members_commitment():
    worksheet = sh.worksheet("Сочлены")
    names = [elem for elem in worksheet.col_values(5)][1::]
    commitments = [elem for elem in worksheet.col_values(7)][1::]
    message = "\n".join(["{}: {}".format(name, commitment) for name, commitment in sorted(zip(names, commitments))])
    return message


Users = load_user_ids()
Usernames_codes = restruct(Users)
Spectators = can_see_extended_menu(Usernames_codes)
Lebowski = who_is_lebowski()
Receipt_types = load_receipts_types()
Expense_types = load_expenses_types()
Total_pay = 0


class Operations:
    initiated = {}
    chat_id = group_id


class Member:
    sheet = "Сочлены"

    def __init__(self,
                 operator_tg_id: str = "default_operator_tg_id",
                 time: str = "default_time",
                 member_tg_id: str = "default_member_tg_id",
                 member_num: str = "default_member_num",
                 member_fio: str = "default_member_fio",
                 member_position: str = "member_position",
                 operation_id: str = "default_operation_id",
                 message_text: str = "default_message_text"):
        self.operator_tg_id = operator_tg_id
        self.time = time
        self.member_tg_id = member_tg_id
        self.member_num = member_num
        self.member_fio = member_fio
        self.member_position = member_position
        self.operation_id = operation_id
        self.message_text = message_text

        self.operator_name = Users[self.operator_tg_id]["name"]
        self.operator_gt_number = Users[self.operator_tg_id]["number"]

    def __str__(self):
        return ("{}:\nЧлен клуба {} добавлен в таблицу под номером {}\nID:{}".
                format(self.operator_name, self.member_fio, self.member_num, self.operation_id))

    def generate_id(self):
        self.time = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        self.operation_id = "".join(a for a in self.time if a.isdigit()) + str(self.operator_gt_number)
        self.operation_id = "M" + self.operation_id
        self.message_text = str(self).replace("\n", " ")

    def operate(self):
        global Users, Usernames_codes, Spectators
        worksheet = sh.worksheet(Member.sheet)
        worksheet.append_row([self.time,
                              self.member_tg_id,
                              self.member_num,
                              0,
                              self.member_fio,
                              self.member_position,
                              "",
                              self.operation_id],
                             value_input_option='USER_ENTERED')
        Users = load_user_ids()
        Usernames_codes = restruct(Users)
        Spectators = can_see_extended_menu(Usernames_codes)

    def report(self):
        bot.send_message(Operations.chat_id, str(self))


class Receipt:
    sheet = "Приходы"

    def __init__(self,
                 operator_tg_id: str = "default_operator_tg_id",
                 time: str = "default_time",
                 operation_id: str = "default_operation_id",
                 message_text: str = "default_message_text",
                 receipt_type: str = "default_receipt_type",
                 receipt_comment: str = "default_receipt_comment",
                 receipt_issued: str = "default_receipt_issued",
                 receipt_sum: str = "default_receipt_sum",
                 card: bool = False):
        self.operator_tg_id = operator_tg_id
        self.time = time
        self.operation_id = operation_id
        self.message_text = message_text
        self.receipt_type = receipt_type
        self.receipt_comment = receipt_comment
        self.receipt_issued = receipt_issued
        self.receipt_sum = receipt_sum
        self.card = card

        self.operator_name = Users[self.operator_tg_id]["name"]
        if not self.card:
            self.operator_gt_number = Users[self.operator_tg_id]["number"]
        else:
            self.operator_gt_number = 707
        

    def __str__(self):
        if not self.card:
            return ("{}:\nПринял за {} ({}) от {} {} р.\nID:{}".
                    format(self.operator_name, self.receipt_type, self.receipt_comment,self.receipt_issued, self.receipt_sum,
                           self.operation_id))
        else:
            return ("{}:\nНа счет поступило {} ({}) от {} {} р.\nID:{}".
                    format(self.operator_name, self.receipt_type, self.receipt_comment,self.receipt_issued, self.receipt_sum,
                           self.operation_id))
            

    def generate_id(self):
        self.time = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        self.operation_id = "".join(a for a in self.time if a.isdigit()) + str(self.operator_gt_number)
        self.operation_id = "R" + self.operation_id
        self.message_text = str(self).replace("\n", " ")

    def operate(self):
        worksheet = sh.worksheet(Receipt.sheet)
        worksheet.append_row([self.time,
                              self.operator_name,
                              self.receipt_type,
                              self.receipt_comment,
                              self.receipt_sum,
                              self.operator_gt_number,
                              self.message_text,
                              self.operation_id],
                             value_input_option='USER_ENTERED')

    def report(self):
        if self.operator_gt_number != '404':
            bot.send_message(Operations.chat_id, str(self))


class Expense:
    sheet = "Расходы"

    def __init__(self,
                 operator_tg_id: str = "default_operator_tg_id",
                 time: str = "default_time",
                 operation_id: str = "default_operation_id",
                 message_text: str = "default_message_text",
                 expense_type: str = "default_expense_type",
                 expense_comment: str = "default_expense_comment",
                 expense_sum: str = "default_expense_sum",
                 merge_commitment: bool = False,
                 card: bool = False):
        self.operator_tg_id = operator_tg_id
        self.time = time
        self.operation_id = operation_id
        self.message_text = message_text
        self.expense_type = expense_type,
        self.expense_comment = expense_comment
        self.expense_sum = expense_sum
        self.merge_commitment = merge_commitment
        self.card = card

        self.operator_name = Users[self.operator_tg_id]["name"]
        if not self.card:
            self.operator_gt_number = Users[self.operator_tg_id]["number"]
        else:
            self.operator_gt_number = 707

    def __str__(self):
        if not self.card:
            return ("{}:\nПотратил {} р. на {} {}\nID:{}".
                    format(self.operator_name, self.expense_sum, self.expense_type, self.expense_comment,
                           self.operation_id))
        else:
            return ("{}:\nРасход со счета {} р. на {} {}\nID:{}".
                    format(self.operator_name, self.expense_sum, self.expense_type, self.expense_comment,
                           self.operation_id))
            

    def generate_id(self):
        self.time = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        self.operation_id = "".join(a for a in self.time if a.isdigit()) + str(self.operator_gt_number)
        self.operation_id = "E" + self.operation_id
        self.message_text = str(self).replace("\n", " ")

    def operate(self):
        worksheet = sh.worksheet(Expense.sheet)
        worksheet.append_row([self.time,
                              self.operator_name,
                              self.expense_type,
                              self.expense_comment,
                              self.expense_sum,
                              self.operator_gt_number,
                              self.message_text,
                              self.operation_id],
                             value_input_option='USER_ENTERED')

    def report(self):
        if self.operator_gt_number != '404':
            bot.send_message(Operations.chat_id, str(self))


class Merge_commitment:
    sheet = "Расходы"

    def __init__(self,
                 operator_tg_id: str = "default_operator_tg_id",
                 time: str = "default_time",
                 operation_id: str = "default_operation_id",
                 message_text: str = "default_message_text",
                 expense_type: str = "default_expense_type",
                 expense_comment: str = "default_expense_comment",
                 expense_sum: str = "default_expense_sum",
                 merger_name: str = "default_merger_name",
                 merger_gt_number: str = "default_merger_gt_number",
                 merge_commitment: bool = True):
        self.operator_tg_id = operator_tg_id
        self.time = time
        self.operation_id = operation_id
        self.message_text = message_text
        self.expense_type = expense_type,
        self.expense_comment = expense_comment
        self.expense_sum = expense_sum
        self.merger_name = merger_name
        self.merge_commitment = merge_commitment
        self.merger_gt_number = merger_gt_number

        self.operator_name = Users[self.operator_tg_id]["name"]
        self.operator_gt_number = Users[self.operator_tg_id]["number"]

    def __str__(self):
        return ("{}:\nСписал с подотчета {} {} за {} {}\nID:{}".
                format(self.operator_name,
                       self.merger_name, self.expense_sum, self.expense_type, self.expense_comment, self.operation_id))

    def generate_id(self):
        self.time = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        self.operation_id = "".join(a for a in self.time if a.isdigit()) + str(self.operator_gt_number)
        self.operation_id = "E" + self.operation_id
        self.message_text = str(self).replace("\n", " ")

    def operate(self):
        worksheet = sh.worksheet(Expense.sheet)
        worksheet.append_row([self.time,
                              self.operator_name,
                              self.expense_type,
                              self.expense_comment,
                              self.expense_sum,
                              self.merger_gt_number,
                              self.message_text,
                              self.operation_id],
                             value_input_option='USER_ENTERED')

    def report(self):
        bot.send_message(Operations.chat_id, str(self))


class Commitment:
    sheet = "Подотчеты"

    def __init__(self,
                 mode,
                 operator_tg_id: str = "default_operator_tg_id",
                 time: str = "default_time",
                 operation_id: str = "default_operation_id",
                 message_text: str = "default_message_text",
                 commitment_sum: str = "default_expense_sum",
                 recipient_name: str = "default_recipient_name",
                 recipient_gt_number: str = "default_recipient_gt_number"
                 ):
        self.mode = mode,
        self.operator_tg_id = operator_tg_id
        self.time = time
        self.operation_id = operation_id
        self.message_text = message_text
        self.commitment_sum = commitment_sum
        self.recipient_name = recipient_name
        self.recipient_gt_number = recipient_gt_number

        self.operator_name = Users[self.operator_tg_id]["name"]
        self.operator_gt_number = Users[self.operator_tg_id]["number"]
        if "out" in self.mode:
            self.input_message = "Кому выдаем в подотчет? Выберите из списка:"
        else:
            self.input_message = "От кого принимаем в подотчет? Выберите из списка:"
        self.alert_message = "Некорректные данные. {}".format(self.input_message)

    def __str__(self):
        if "out" in self.mode:
            return ("{}:\nВыдал в подотчет {} {} р.\nID:{}".
                    format(self.operator_name, self.recipient_name, self.commitment_sum, self.operation_id))
        else:
            return ("{}:\nПринял в подотчет от {} {} р.\nID:{}".
                    format(self.operator_name, self.recipient_name, self.commitment_sum, self.operation_id))

    def generate_id(self):
        self.time = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        self.operation_id = "".join(a for a in self.time if a.isdigit()) + str(self.operator_gt_number)
        self.operation_id = "C" + self.operation_id
        self.message_text = str(self).replace("\n", " ")

    def operate(self):
        worksheet = sh.worksheet(Commitment.sheet)
        if "out" in self.mode:
            worksheet.append_row([self.time,
                                  self.operator_name,
                                  self.recipient_name,
                                  self.commitment_sum,
                                  self.operator_gt_number,
                                  self.recipient_gt_number,
                                  self.message_text,
                                  self.operation_id],
                                 value_input_option='USER_ENTERED')
        else:
            worksheet.append_row([self.time,
                                  self.recipient_name,
                                  self.operator_name,
                                  self.commitment_sum,
                                  self.recipient_gt_number,
                                  self.operator_gt_number,
                                  self.message_text,
                                  self.operation_id],
                                 value_input_option='USER_ENTERED')

    def report(self):
        bot.send_message(Operations.chat_id, str(self))


class Change_lebowski:
    def __init__(self,
                 operator_tg_id: str = "default",
                 new_lebowski_name: str = "default_new_lebowski_name"):
        self.operator_tg_id = operator_tg_id
        self.operator_name = Users[self.operator_tg_id]["name"]
        self.new_lebowski_name = new_lebowski_name

    def __str__(self):
        return "{} передал должность казначея Клуба.\nНовый казначей клуба - {}".format(
            self.operator_name, self.new_lebowski_name)

    def operate(self):
        global Users, Usernames_codes, Spectators, Lebowski
        worksheet = sh.worksheet("Казна")
        worksheet.update_cell(1, 2, self.new_lebowski_name)
        Users = load_user_ids()
        Usernames_codes = restruct(Users)
        Spectators = can_see_extended_menu(Usernames_codes)
        Lebowski = who_is_lebowski()

    def report(self):
        bot.send_message(Operations.chat_id, str(self))


@bot.message_handler(content_types='text')
def start(message):
    chat = message.chat.id
    if chat != Operations.chat_id:
        user_tg_id = message.from_user.id
        if user_tg_id in Users.keys():
            bot.send_message(user_tg_id, "Выберите тип операции: ", reply_markup=Spectators[user_tg_id])
            bot.register_next_step_handler(message, check_operation)
        else:
            bot.send_message(user_tg_id, "Для продолжения работы обратитесь к администратору бота")
            data = {"id": message.from_user.id,
                    "bot": message.from_user.is_bot,
                    "first_name": message.from_user.first_name,
                    "username": message.from_user.username,
                    "last_name": message.from_user.last_name}
            bot.send_message(423891946, "Какой-то чорт лезет в бота. Вот данные:\n{}".format(data))
    else:
        if message.text.title() == "Отклонить":
            user_tg_id = message.from_user.id
            username = Users[user_tg_id]["name"]
            if username == Lebowski or Users[user_tg_id]["bot_admin"] == 1:
                text = ""
                if message.reply_to_message.content_type == 'text':
                    text = message.reply_to_message.text
                elif message.reply_to_message.content_type == 'photo':
                    text = message.reply_to_message.caption
                data = text.split("\n")
                initiator_name = data[0].split(":")[0]
                transaction_id = data[-1].split("ID:")[-1]
                initiator_tg_id = Usernames_codes[initiator_name]["tg_id"]
                try:
                    delete_transaction_from_table(transaction_id)
                    bot.send_message(initiator_tg_id, "{} отклонил вашу транзакцию.\n"
                                                      "\nТекст транзакции:\n{}"
                                                      "\n\nСвяжитесь с ним для выяснения".format(username, text))
                    bot.send_message(user_tg_id, "Транзакция отклонена.\n"
                                                 "\nТекст транзакции\n{}".format(text))
                    bot.delete_message(Operations.chat_id, message.reply_to_message.id)
                except:
                    bot.send_message(user_tg_id, "При попытке отклонения транзакции возникла ошибка. Возможно транзакция отсутствует в таблице\n"
                                                 "\nТекст транзакции\n{}".format(text))
            else:
                bot.reply_to(message, "Отклонять транзакции может только {}\n"
                                      "Свяжитесь с ним для отклонения транзакции".format(Lebowski))


def check_operation(message):
    user_tg_id = message.from_user.id
    operation = message.text
    memory = how_much()
    bot.send_message(423891946, memory)

    if operation not in extended_menu_keys:
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Неизвестный тип операци", reply_markup=Spectators[user_tg_id]),
            start)
    elif operation == "Добавить члена клуба":
        if Users[user_tg_id]["bot_admin"] == 1:
            Operations.initiated[user_tg_id] = Member(operator_tg_id=user_tg_id)
            bot.register_next_step_handler(
                bot.send_message(user_tg_id,
                                 "Перешлите боту любое сообщение от участника, которого хотитие добавить",
                                 reply_markup=cancel_menu()),
                add_member_tg_id)
        else:
            bot.register_next_step_handler(
                bot.send_message(user_tg_id, "Данная функция доступна только администраторам",
                                 reply_markup=Spectators[user_tg_id]),
                start)
    elif operation == "Приход":
        Operations.initiated[user_tg_id] = Receipt(operator_tg_id=user_tg_id)
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Выберите тип прихода", reply_markup=make_menu(Receipt_types)),
            receipt_choose_type)
    elif operation == "Приход на счет":
        Operations.initiated[user_tg_id] = Receipt(operator_tg_id=user_tg_id, card=True)
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Выберите тип прихода", reply_markup=make_menu(Receipt_types)),
            receipt_choose_type)
    elif operation == "Расход":
        Operations.initiated[user_tg_id] = Expense(operator_tg_id=user_tg_id)
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Выберите тип расхода", reply_markup=make_menu(Expense_types)),
            expense_choose_type)
    elif operation == "Расход со счета":
        Operations.initiated[user_tg_id] = Expense(operator_tg_id=user_tg_id, card=True)
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Выберите тип расхода", reply_markup=make_menu(Expense_types)),
            expense_choose_type)
    elif operation == "Выдать в подотчет":
        Operations.initiated[user_tg_id] = Commitment(operator_tg_id=user_tg_id, mode="out")
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, Operations.initiated[user_tg_id].input_message,
                             reply_markup=make_menu(sorted(Usernames_codes.keys()))),
            commitment_set_issue)
    elif operation == "Принять в подотчет":
        Operations.initiated[user_tg_id] = Commitment(operator_tg_id=user_tg_id, mode="in")
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, Operations.initiated[user_tg_id].input_message,
                             reply_markup=make_menu(sorted(Usernames_codes.keys()))),
            commitment_set_issue)
    elif operation == "Списание подотчета":
        username = Users[user_tg_id]["name"]
        if username == Lebowski:
            Operations.initiated[user_tg_id] = Merge_commitment(operator_tg_id=user_tg_id)
            bot.register_next_step_handler(
                bot.send_message(user_tg_id, "С кого списываем подотчет? Выберите из списка:",
                                 reply_markup=make_menu(sorted(Usernames_codes.keys()))),
                merge_commitment_set_merger)
        else:
            bot.register_next_step_handler(
                bot.send_message(user_tg_id, "Данная функция доступна только казанчею",
                                 reply_markup=Spectators[user_tg_id]),
                start)
    elif operation == "Мой подотчет":
        worksheet = sh.worksheet("Сочлены")
        cell = worksheet.find(str(user_tg_id))
        my_commitment = worksheet.cell(cell.row, cell.col + 5).value
        bot.send_message(user_tg_id, "У вас в подотчете: {} р.".format(my_commitment),
                         reply_markup=Spectators[user_tg_id])
        start(message)
    elif operation == "Фонд клуба":
        money = request_money()
        bot.send_message(user_tg_id, money, reply_markup=Spectators[user_tg_id])
        start(message)
    elif operation == "Передать должность казначея":
        if Users[user_tg_id]["name"] == Lebowski:
            Operations.initiated[user_tg_id] = Change_lebowski(operator_tg_id=user_tg_id)
            bot.register_next_step_handler(
                bot.send_message(user_tg_id, "Кому передаем должность казначея? Выберите из списка",
                                 reply_markup=make_menu(sorted(Usernames_codes.keys()))),
                new_lebowski)
        else:
            bot.send_message(user_tg_id, "Данная функция доступна только для действующего казначея клуба",
                             reply_markup=Spectators[user_tg_id])
            start(message)
    elif operation == "Подотчет членов клуба":
        report = members_commitment()
        bot.send_message(user_tg_id, report, reply_markup=Spectators[user_tg_id])
        start(message)
    elif operation == "Подотчетный пулемет":
        if Users[user_tg_id]["name"] == Lebowski:
            bot.register_next_step_handler(
                bot.send_message(user_tg_id, "Введите сумму", reply_markup=cancel_menu()),
                total_pay_get_sum)
        else:
            bot.send_message(user_tg_id, "Данная функция доступна только для действующего казначея клуба",
                             reply_markup=Spectators[user_tg_id])


def total_pay_get_sum(message):
    user_tg_id = message.from_user.id
    debt_summa = message.text
    if debt_summa == "Назад":
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Выберите тип операции: ", reply_markup=Spectators[user_tg_id]),
            check_operation)
    elif debt_summa == "Отмена":
        bot.send_message(user_tg_id, "Операция сброшена", reply_markup=Spectators[user_tg_id])
        start(message)
    else:
        try:
            if float(debt_summa) > 0:
                global Total_pay
                Total_pay = debt_summa
                bot.register_next_step_handler(
                    bot.send_message(user_tg_id,
                                     "Выдать каждому члену клуба {} р. в подотчет?".format(debt_summa),
                                     reply_markup=yes_no_menu()), total_pay_confirmation)
            else:
                bot.register_next_step_handler(
                    bot.send_message(user_tg_id, "Сумма не может быть отрицательной. Введите сумму: ",
                                     reply_markup=cancel_menu()), total_pay_get_sum)
        except ValueError:
            bot.register_next_step_handler(
                bot.send_message(user_tg_id, "Сумма не может вводиться буквами. Введите сумму: ",
                                 reply_markup=cancel_menu()), total_pay_get_sum)


def total_pay_confirmation(message):
    user_tg_id = message.from_user.id
    confirmation = message.text
    if confirmation == "Назад":
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Введите сумму", reply_markup=cancel_menu()),
            total_pay_get_sum)
    elif confirmation == "Отмена":
        bot.send_message(user_tg_id, "Операция сброшена", reply_markup=Spectators[user_tg_id])
        start(message)
    elif confirmation not in ("Да", "Нет"):
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Команда подтверждения не распознана. Подтвердите операцию",
                             reply_markup=yes_no_menu()), total_pay_confirmation)
    elif confirmation == "Да":
        time = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        operation_id = "".join(a for a in time if a.isdigit()) + str(user_tg_id)
        operation_id = "G" + operation_id
        counter = 1
        not_members = ["Меха Александр (техподдержка)", "Директор Мария Филюшина"]
        list_to_go = {key: value for key, value in Usernames_codes.items() if key not in not_members}
        total = len(list_to_go)
        bot.send_message(user_tg_id, "Поехали")
        for name, data in list_to_go.items():
            bot.send_message(user_tg_id, "Выполняется транзакция {} из {}".format(counter, total))
            counter += 1
            op_id = operation_id + str(counter)
            Operations.initiated[user_tg_id] = Commitment(
                operator_tg_id=user_tg_id,
                mode="out",
                operation_id=op_id,
                recipient_name=name,
                recipient_gt_number=data["gt_number"],
                commitment_sum=str(Total_pay),
                time=time)
            Operations.initiated[user_tg_id].message_text = str(Operations.initiated[user_tg_id]).replace("\n", " ")
            Operations.initiated[user_tg_id].operate()
            Operations.initiated[user_tg_id].report()
            t.sleep(random.randint(3, 5))
        bot.send_message(user_tg_id, "Все транзакции проведены")
        start(message)
    else:
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Введите сумму", reply_markup=cancel_menu()),
            total_pay_get_sum)


def merge_commitment_set_merger(message):
    user_tg_id = message.from_user.id
    merger_name = message.text
    if merger_name == "Назад":
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Выберите тип операции: ", reply_markup=Spectators[user_tg_id]),
            check_operation)
    elif merger_name == "Отмена":
        bot.send_message(user_tg_id, "Операция сброшена", reply_markup=Spectators[user_tg_id])
        start(message)
    elif merger_name not in Usernames_codes.keys():
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Некорректные данные. С кого списываем подотчет? Выберите из списка:",
                             reply_markup=make_menu(sorted(Usernames_codes.keys()))),
            merger_name)
    else:
        Operations.initiated[user_tg_id].merger_name = merger_name
        Operations.initiated[user_tg_id].merger_gt_number = Usernames_codes[merger_name]["gt_number"]
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "За что списываем подотчет? Выберите тип расхода:",
                             reply_markup=make_menu(Expense_types)),
            expense_choose_type)


def new_lebowski(message):
    user_tg_id = message.from_user.id
    new_lebowski_name = message.text
    if new_lebowski_name == "Назад":
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Выберите тип операции: ", reply_markup=Spectators[user_tg_id]),
            check_operation)
    elif new_lebowski_name == "Отмена":
        bot.send_message(user_tg_id, "Операция сброшена", reply_markup=Spectators[user_tg_id])
        start(message)
    elif new_lebowski_name not in Usernames_codes.keys():
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Некорректные данные. Кому передаем должность? Выберите из списка",
                             reply_markup=make_menu(sorted(Usernames_codes.keys()))),
            new_lebowski)
    else:
        Operations.initiated[user_tg_id].new_lebowski_name = new_lebowski_name
        bot.register_next_step_handler(
            bot.send_message(user_tg_id,
                             "Подтвердите операцию: {}".format(Operations.initiated[user_tg_id]),
                             reply_markup=yes_no_menu()), new_lebowski_confirmation)


def new_lebowski_confirmation(message):
    user_tg_id = message.from_user.id
    confirmation = message.text
    if confirmation == "Назад":
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Кому передаем должность казначея? Выберите из списка",
                             reply_markup=make_menu(sorted(Usernames_codes.keys()))),
            new_lebowski)
    elif confirmation == "Отмена":
        bot.send_message(user_tg_id, "Операция сброшена", reply_markup=Spectators[user_tg_id])
        start(message)
    elif confirmation not in ("Да", "Нет"):
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Команда подтверждения не распознана. Подтвердите операцию",
                             reply_markup=yes_no_menu()), new_lebowski_confirmation)
    elif confirmation == "Да":
        Operations.initiated[user_tg_id].operate()
        Operations.initiated[user_tg_id].report()
        bot.send_message(user_tg_id, "Операция проведена")
        start(message)
    else:
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Кому передаем должность казначея? Выберите из списка",
                             reply_markup=make_menu(sorted(Usernames_codes.keys()))),
            new_lebowski)


def commitment_set_issue(message):
    user_tg_id = message.from_user.id
    commitment_issue = message.text
    if commitment_issue == "Назад":
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Выберите тип операции: ", reply_markup=Spectators[user_tg_id]),
            check_operation)
    elif commitment_issue == "Отмена":
        bot.send_message(user_tg_id, "Операция сброшена", reply_markup=Spectators[user_tg_id])
        start(message)
    elif commitment_issue not in Usernames_codes.keys():
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, Operations.initiated[user_tg_id].alert_message,
                             reply_markup=make_menu(sorted(Usernames_codes.keys()))),
            commitment_set_issue)
    else:
        Operations.initiated[user_tg_id].recipient_name = commitment_issue
        Operations.initiated[user_tg_id].recipient_gt_number = Usernames_codes[commitment_issue]["gt_number"]
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Введите сумму подотчета", reply_markup=cancel_menu()),
            commitment_set_summa)


def commitment_set_summa(message):
    user_tg_id = message.from_user.id
    commitment_summa = message.text
    if commitment_summa == "Назад":
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, Operations.initiated[user_tg_id].input_message,
                             reply_markup=make_menu(sorted(Usernames_codes.keys()))),
            commitment_set_issue)
    elif commitment_summa == "Отмена":
        bot.send_message(user_tg_id, "Операция сброшена", reply_markup=Spectators[user_tg_id])
        start(message)
    else:
        try:
            if float(commitment_summa) > 0:
                Operations.initiated[user_tg_id].commitment_sum = round(float(commitment_summa), 2)
                Operations.initiated[user_tg_id].generate_id()
                bot.register_next_step_handler(
                    bot.send_message(user_tg_id,
                                     "Подтвердите операцию: {}".format(Operations.initiated[user_tg_id]),
                                     reply_markup=yes_no_menu()), commitment_confirmation)
            else:
                bot.register_next_step_handler(
                    bot.send_message(user_tg_id, "Сумма не может быть отрицательной. Введите сумму: ",
                                     reply_markup=cancel_menu()), commitment_set_summa)
        except ValueError:
            bot.register_next_step_handler(
                bot.send_message(user_tg_id, "Сумма не может вводиться буквами. Введите сумму: ",
                                 reply_markup=cancel_menu()), commitment_set_summa)


def commitment_confirmation(message):
    user_tg_id = message.from_user.id
    confirmation = message.text
    if confirmation == "Назад":
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Введите сумму подотчета", reply_markup=cancel_menu()),
            commitment_set_summa)
    elif confirmation == "Отмена":
        bot.send_message(user_tg_id, "Операция сброшена", reply_markup=Spectators[user_tg_id])
        start(message)
    elif confirmation not in ("Да", "Нет"):
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Команда подтверждения не распознана. Подтвердите операцию",
                             reply_markup=yes_no_menu()), commitment_confirmation)
    elif confirmation == "Да":
        Operations.initiated[user_tg_id].operate()
        Operations.initiated[user_tg_id].report()
        bot.send_message(user_tg_id, "Операция проведена")
        start(message)
    else:
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Введите сумму подотчета", reply_markup=cancel_menu()),
            commitment_set_summa)


def expense_choose_type(message):
    user_tg_id = message.from_user.id
    expense_type = message.text
    if expense_type == "Назад":
        if Operations.initiated[user_tg_id].merge_commitment:
            bot.register_next_step_handler(
                bot.send_message(user_tg_id, "С кого списываем подотчет? Выберите из списка:",
                                 reply_markup=make_menu(sorted(Usernames_codes.keys()))),
                merge_commitment_set_merger)
        else:
            bot.register_next_step_handler(
                bot.send_message(user_tg_id, "Выберите тип операции: ", reply_markup=Spectators[user_tg_id]),
                check_operation)
    elif expense_type == "Отмена":
        bot.send_message(user_tg_id, "Операция сброшена", reply_markup=Spectators[user_tg_id])
        start(message)
    elif expense_type not in Expense_types:
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Неизвестный тип расхода. Выберите тип из списка",
                             reply_markup=make_menu(Expense_types)),
            expense_choose_type)
    else:
        Operations.initiated[user_tg_id].expense_type = expense_type
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Введите сумму расхода:",
                             reply_markup=cancel_menu()),
            expense_set_summa)


def expense_set_summa(message):
    user_tg_id = message.from_user.id
    expense_summa = message.text
    if expense_summa == "Назад":
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Выберите тип из расхода:",
                             reply_markup=make_menu(Expense_types)),
            expense_choose_type)
    elif expense_summa == "Отмена":
        bot.send_message(user_tg_id, "Операция сброшена", reply_markup=Spectators[user_tg_id])
        start(message)
    else:
        try:
            if float(expense_summa) > 0:
                Operations.initiated[user_tg_id].expense_sum = round(float(expense_summa), 2)
                bot.register_next_step_handler(
                    bot.send_message(user_tg_id, "Введите комментарий:",
                                     reply_markup=cancel_menu()), expense_set_comment)
            else:
                bot.register_next_step_handler(
                    bot.send_message(user_tg_id, "Сумма не может быть отрицательной. Введите сумму: ",
                                     reply_markup=cancel_menu()), expense_set_summa)
        except ValueError:
            bot.register_next_step_handler(
                bot.send_message(user_tg_id, "Сумма не может вводиться буквами. Введите сумму: ",
                                 reply_markup=cancel_menu()), expense_set_summa)


def expense_set_comment(message):
    user_tg_id = message.from_user.id
    expense_comment = message.text
    if expense_comment == "Назад":
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Введите сумму расхода:",
                             reply_markup=cancel_menu()),
            expense_set_summa)
    elif expense_comment == "Отмена":
        bot.send_message(user_tg_id, "Операция сброшена", reply_markup=Spectators[user_tg_id])
        start(message)
    else:
        Operations.initiated[user_tg_id].expense_comment = expense_comment
        Operations.initiated[user_tg_id].generate_id()
        bot.register_next_step_handler(
            bot.send_message(user_tg_id,
                             "Подтвердите операцию: {}".format(Operations.initiated[user_tg_id]),
                             reply_markup=yes_no_menu()), expense_confirmation)


def expense_confirmation(message):
    user_tg_id = message.from_user.id
    confirmation = message.text
    if confirmation == "Назад":
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Введите комментарий:",
                             reply_markup=cancel_menu()), expense_set_comment)
    elif confirmation == "Отмена":
        bot.send_message(user_tg_id, "Операция сброшена", reply_markup=Spectators[user_tg_id])
        start(message)
    elif confirmation not in ("Да", "Нет"):
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Команда подтверждения не распознана. Подтвердите операцию",
                             reply_markup=yes_no_menu()), expense_confirmation)
    elif confirmation == "Да":
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Чек есть?", reply_markup=yes_no_menu()),
            expense_ask_for_check)
    else:
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Введите комментарий:",
                             reply_markup=cancel_menu()), expense_set_comment)


def expense_ask_for_check(message):
    user_tg_id = message.from_user.id
    check_confirmation = message.text
    if check_confirmation == "Назад":
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Подтвердите операцию: {}".format(Operations.initiated[user_tg_id]),
                             reply_markup=yes_no_menu()), expense_confirmation)
    elif check_confirmation == "Отмена":
        bot.send_message(user_tg_id, "Операция сброшена", reply_markup=Spectators[user_tg_id])
        start(message)
    elif check_confirmation not in ("Да", "Нет"):
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Команда подтверждения не распознана. Чек есть?",
                             reply_markup=yes_no_menu()), expense_ask_for_check)
    elif check_confirmation == "Нет":
        Operations.initiated[user_tg_id].operate()
        Operations.initiated[user_tg_id].report()
        bot.send_message(user_tg_id, "Операция проведена")
        start(message)
    else:
        bot.register_next_step_handler(
            bot.send_message(message.from_user.id, "Загрузите чек:", reply_markup=cancel_menu()),
            expense_load_check)


def expense_load_check(message):
    user_tg_id = message.from_user.id
    check_confirmation = message.text
    if check_confirmation == "Назад":
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Чек есть?", reply_markup=yes_no_menu()),
            expense_ask_for_check)
    elif check_confirmation == "Отмена":
        bot.send_message(user_tg_id, "Операция сброшена", reply_markup=Spectators[user_tg_id])
        start(message)
    else:
        try:
            file_info = bot.get_file(message.photo[len(message.photo) - 1].file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            src = "checks/" + Operations.initiated[user_tg_id].operation_id + ".jpg"
            Operations.initiated[user_tg_id].check = src
            with open(src, 'wb') as new_file:
                new_file.write(downloaded_file)
            bot.send_photo(Operations.chat_id, open(src, "rb"),
                           caption=Operations.initiated[user_tg_id])
            Operations.initiated[user_tg_id].operate()
            os.remove(src)
            bot.send_message(user_tg_id, "Операция проведена")
            start(message)
        except TypeError:
            bot.send_message(user_tg_id, "Что-то пошло не так с загрузкой чека ((")
            bot.register_next_step_handler(
                bot.send_message(user_tg_id, "Загрузите чек", reply_markup=cancel_menu()),
                expense_load_check)


def receipt_choose_type(message):
    user_tg_id = message.from_user.id
    receipt_type = message.text
    if receipt_type == "Назад":
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Выберите тип операции: ", reply_markup=Spectators[user_tg_id]),
            check_operation)
    elif receipt_type == "Отмена":
        bot.send_message(user_tg_id, "Операция сброшена", reply_markup=Spectators[user_tg_id])
        start(message)
    elif receipt_type not in Receipt_types:
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Неизвестный тип прихода. Выберите тип из списка",
                             reply_markup=make_menu(Receipt_types)),
            receipt_choose_type)
    else:
        Operations.initiated[user_tg_id].receipt_type = receipt_type
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "От кого приняли деньги? Напишите или выберите из списка",
                             reply_markup=make_menu(sorted(Usernames_codes.keys()))),
            receipt_set_issue)


def receipt_set_issue(message):
    user_tg_id = message.from_user.id
    receipt_issue = message.text
    if receipt_issue == "Назад":
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Выберите тип операции: ", reply_markup=Spectators[user_tg_id]),
            check_operation)
    elif receipt_issue == "Отмена":
        bot.send_message(user_tg_id, "Операция сброшена", reply_markup=Spectators[user_tg_id])
        start(message)
    else:
        Operations.initiated[user_tg_id].receipt_issued = receipt_issue
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Введите сумму прихода", reply_markup=cancel_menu()),
            receipt_set_summa)


def receipt_set_summa(message):
    user_tg_id = message.from_user.id
    receipt_summa = message.text
    if receipt_summa == "Назад":
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "От кого приняли деньги? Напишите или выберите из списка",
                             reply_markup=make_menu(sorted(Usernames_codes.keys()))),
            receipt_set_issue)
    elif receipt_summa == "Отмена":
        bot.send_message(user_tg_id, "Операция сброшена", reply_markup=Spectators[user_tg_id])
        start(message)
    else:
        try:
            if float(receipt_summa) > 0:
                Operations.initiated[user_tg_id].receipt_sum = round(float(receipt_summa), 2)
                Operations.initiated[user_tg_id].generate_id()
                bot.register_next_step_handler(
                    bot.send_message(user_tg_id,
                                     "Введите комментарий",
                                     reply_markup=cancel_menu()), receipt_set_comment)
            else:
                bot.register_next_step_handler(
                    bot.send_message(user_tg_id, "Сумма не может быть отрицательной. Введите сумму: ",
                                     reply_markup=cancel_menu()), receipt_set_summa)
        except ValueError:
            bot.register_next_step_handler(
                bot.send_message(user_tg_id, "Сумма не может вводиться буквами. Введите сумму: ",
                                 reply_markup=cancel_menu()), receipt_set_summa)


def receipt_set_comment(message):
    user_tg_id = message.from_user.id
    receipt_comment = message.text
    if receipt_comment == "Назад":
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Введите сумму прихода:",
                             reply_markup=cancel_menu()),
            receipt_set_summa)
    elif receipt_comment == "Отмена":
        bot.send_message(user_tg_id, "Операция сброшена", reply_markup=Spectators[user_tg_id])
        start(message)
    else:
        Operations.initiated[user_tg_id].receipt_comment = receipt_comment
        Operations.initiated[user_tg_id].generate_id()
        bot.register_next_step_handler(
            bot.send_message(user_tg_id,
                             "Подтвердите операцию: {}".format(Operations.initiated[user_tg_id]),
                             reply_markup=yes_no_menu()), receipt_confirmation)


def receipt_confirmation(message):
    user_tg_id = message.from_user.id
    confirmation = message.text
    if confirmation == "Назад":
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Введите комментарий", reply_markup=cancel_menu()),
            receipt_set_comment)
    elif confirmation == "Отмена":
        bot.send_message(user_tg_id, "Операция сброшена", reply_markup=Spectators[user_tg_id])
        start(message)
    elif confirmation not in ("Да", "Нет"):
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Команда подтверждения не распознана. Подтвердите операцию",
                             reply_markup=yes_no_menu()), receipt_confirmation)
    elif confirmation == "Да":
        Operations.initiated[user_tg_id].operate()
        Operations.initiated[user_tg_id].report()
        bot.send_message(user_tg_id, "Операция проведена")
        start(message)
    else:
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Введите комментарий", reply_markup=cancel_menu()),
            receipt_set_comment)


def add_member_tg_id(message):
    user_tg_id = message.from_user.id
    member_tg_id = message.text
    if member_tg_id == "Назад":
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Выберите тип операции: ", reply_markup=Spectators[user_tg_id]),
            check_operation)
    elif member_tg_id == "Отмена":
        bot.send_message(user_tg_id, "Операция сброшена", reply_markup=Spectators[user_tg_id])
        start(message)
    else:
        Operations.initiated[user_tg_id].member_tg_id = message.forward_from.id
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Под каким номером добавляем члена клуба?",
                             reply_markup=cancel_menu()),
            add_member_gt_num)


def add_member_gt_num(message):
    user_tg_id = message.from_user.id
    number = message.text
    if number == "Назад":
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Перешлите боту любое сообщение от человека, которого хотитие добавить",
                             reply_markup=cancel_menu()),
            add_member_tg_id)
    elif number == "Отмена":
        bot.send_message(user_tg_id, "Операция сброшена", reply_markup=Spectators[user_tg_id])
        start(message)
    else:
        worksheet = sh.worksheet("Сочлены")
        if number.isdigit():
            # подумать
            if worksheet.find(str(int(number))):
                bot.register_next_step_handler(
                    bot.send_message(user_tg_id, "Номер уже используется. Введите другой номер: ",
                                     reply_markup=cancel_menu()), add_member_gt_num)
            else:
                Operations.initiated[user_tg_id].member_num = number
                bot.register_next_step_handler(
                    bot.send_message(user_tg_id, "Введите ФИО члена клуба: ", reply_markup=cancel_menu()),
                    add_member_get_fio)
        else:
            bot.register_next_step_handler(
                bot.send_message(user_tg_id, "Некорректный номер. Введите целое положительное число: ",
                                 reply_markup=cancel_menu()), add_member_gt_num)


def add_member_get_fio(message):
    user_tg_id = message.from_user.id
    member_fio = message.text
    if member_fio == "Назад":
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Под каким номером добавляем члена клуба?",
                             reply_markup=cancel_menu()),
            add_member_gt_num)
    elif member_fio == "Отмена":
        bot.send_message(user_tg_id, "Операция сброшена", reply_markup=Spectators[user_tg_id])
        start(message)
    else:
        Operations.initiated[user_tg_id].member_fio = member_fio
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Введите должность члена клуба:".format(Operations.initiated[user_tg_id]),
                             reply_markup=cancel_menu()), add_member_position)


def add_member_position(message):
    user_tg_id = message.from_user.id
    member_position = message.text
    if member_position == "Назад":
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Введите ФИО члена клуба: ", reply_markup=cancel_menu()),
            add_member_get_fio)
    elif member_position == "Отмена":
        bot.send_message(user_tg_id, "Операция сброшена", reply_markup=Spectators[user_tg_id])
        start(message)
    else:
        Operations.initiated[user_tg_id].member_position = member_position
        Operations.initiated[user_tg_id].generate_id()
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Подтвердите операцию: {}".format(Operations.initiated[user_tg_id]),
                             reply_markup=yes_no_menu()), add_member_confirmation)


def add_member_confirmation(message):
    user_tg_id = message.from_user.id
    confirmation = message.text
    if confirmation == "Назад":
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Введите должность члена клуба:".format(Operations.initiated[user_tg_id]),
                             reply_markup=cancel_menu()), add_member_position)
    elif confirmation == "Отмена":
        bot.send_message(user_tg_id, "Операция сброшена", reply_markup=Spectators[user_tg_id])
        start(message)
    elif confirmation not in ("Да", "Нет"):
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Команда подтверждения не распознана. Подтвердите операцию",
                             reply_markup=yes_no_menu()), add_member_confirmation)
    elif confirmation == "Да":
        Operations.initiated[user_tg_id].operate()
        Operations.initiated[user_tg_id].report()
        bot.send_message(user_tg_id, "Операция проведена")
        start(message)
    else:
        bot.register_next_step_handler(
            bot.send_message(user_tg_id, "Введите должность члена клуба:".format(Operations.initiated[user_tg_id]),
                             reply_markup=cancel_menu()), add_member_position)


if __name__ == "__main__":
    bot.remove_webhook()
    t.sleep(1)

    while True:
        try:
            bot.infinity_polling(skip_pending=True)
        except Exception as e:
            bot.send_message(423891946, "С ботом что-то не так. Вот ошибка:\n{}".format(e))
            t.sleep(1)  # ВАЖНО: больше задержка
