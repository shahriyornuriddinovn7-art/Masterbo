"""FSM holatlari."""
from aiogram.fsm.state import State, StatesGroup


class AdminSt(StatesGroup):
    add_channel = State()
    bc_msg = State()
    bc_btn = State()


class MakerSt(StatesGroup):
    token = State()
    ad_text = State()
    limit = State()
    premium = State()


class ChildSt(StatesGroup):
    api_key = State()
    welcome = State()
    movie_file = State()
    movie_code = State()
    pdf_file = State()


class EduSt(StatesGroup):
    sch_add = State()
    rem_add = State()
    gen_topic = State()
    quiz_topic = State()
    stu_add = State()
    plan_topic = State()


class LogoSt(StatesGroup):
    style = State()
