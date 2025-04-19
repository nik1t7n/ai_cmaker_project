from aiogram.fsm.state import StatesGroup, State

class VideoCreation(StatesGroup):
    choosing_avatar = State()
    choosing_script_method = State()
    ai_script_input = State()        # Ожидание ввода концепции для ИИ
    user_script_input = State()      # ожидание ввода пользовательского сценария
    script_confirm = State()         # Ожидание подтверждения/редактирования сгенерированного сценария
    video_editing = State()
    create_music = State()
    combine_music_and_video = State()


class PaymentForm(StatesGroup):
    waiting_for_phone = State()
    waiting_for_email = State()
    confirmation = State()
